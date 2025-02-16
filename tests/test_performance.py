import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import psutil
import gc
from app.utils.performance import PerformanceOptimizer
import asyncio

@pytest.fixture
def optimizer():
    """Фикстура для создания оптимизатора"""
    return PerformanceOptimizer()

@pytest.mark.asyncio
async def test_optimize_db_queries(optimizer):
    """Тест оптимизации запросов к БД"""
    # Мокаем подключение к БД
    mock_conn = Mock()
    mock_conn.execute_query = Mock()
    
    # Настраиваем результаты запросов
    index_stats = [
        ("public", "users", "users_pkey", 0),  # Неиспользуемый индекс
        ("public", "records", "records_idx", 1000)
    ]
    
    slow_query_stats = [
        ("SELECT * FROM users", 100, 5000, 50),  # Медленный запрос
        ("SELECT * FROM records", 200, 8000, 40)
    ]
    
    table_stats = [
        ("public", "users", 1000, 200, datetime.now(), datetime.now()),
        ("public", "records", 2000, 500, None, None)
    ]
    
    mock_conn.execute_query.side_effect = [
        index_stats,
        slow_query_stats,
        table_stats
    ]
    
    with patch('tortoise.Tortoise.get_connection', return_value=mock_conn):
        results = await optimizer.optimize_db_queries()
        
        assert isinstance(results, dict)
        assert "unused_indexes" in results
        assert "slow_queries" in results
        assert "tables_need_vacuum" in results
        assert "recommendations" in results
        
        assert results["unused_indexes"] == 1
        assert results["slow_queries"] == 2
        assert len(results["recommendations"]) > 0

def test_optimize_memory(optimizer):
    """Тест оптимизации памяти"""
    # Мокаем psutil.virtual_memory
    mock_memory = Mock()
    mock_memory.percent = 90  # Выше порога
    
    with patch('psutil.virtual_memory', return_value=mock_memory), \
         patch('gc.collect') as mock_collect:
        
        results = optimizer.optimize_memory()
        
        assert isinstance(results, dict)
        assert results["threshold_exceeded"] is True
        assert results["action_taken"] == "garbage_collection"
        mock_collect.assert_called_once()
        
        # Тест нормального использования памяти
        mock_memory.percent = 50  # Ниже порога
        results = optimizer.optimize_memory()
        
        assert isinstance(results, dict)
        assert results["threshold_exceeded"] is False
        assert results["action_taken"] is None

def test_optimize_cpu(optimizer):
    """Тест оптимизации CPU"""
    # Мокаем psutil функции
    with patch('psutil.cpu_percent', return_value=85), \
         patch('psutil.process_iter') as mock_process_iter:
        
        # Создаем тестовые процессы
        mock_processes = [
            Mock(info={'pid': 1, 'name': 'process1', 'cpu_percent': 30}),
            Mock(info={'pid': 2, 'name': 'process2', 'cpu_percent': 20}),
            Mock(info={'pid': 3, 'name': 'process3', 'cpu_percent': 10})
        ]
        mock_process_iter.return_value = mock_processes
        
        results = optimizer.optimize_cpu()
        
        assert isinstance(results, dict)
        assert results["threshold_exceeded"] is True
        assert "high_cpu_processes" in results
        assert len(results["high_cpu_processes"]) > 0
        
        # Тест нормальной загрузки CPU
        with patch('psutil.cpu_percent', return_value=50):
            results = optimizer.optimize_cpu()
            
            assert isinstance(results, dict)
            assert results["threshold_exceeded"] is False
            assert "high_cpu_processes" not in results

def test_optimize_cache(optimizer):
    """Тест оптимизации кэша"""
    # Создаем тестовый кэш
    test_cache = {
        f"key_{i}": (datetime.now() - timedelta(minutes=i), f"value_{i}")
        for i in range(1100)  # Больше лимита
    }
    
    # Добавляем статистику использования
    optimizer.cache_hits = 800
    optimizer.cache_misses = 200
    
    results = optimizer.optimize_cache(test_cache)
    
    assert isinstance(results, dict)
    assert "initial_size" in results
    assert "final_size" in results
    assert "items_removed" in results
    assert "hit_ratio" in results
    
    assert results["initial_size"] > results["final_size"]
    assert results["items_removed"] > 0
    assert 0 <= results["hit_ratio"] <= 1
    
    # Тест кэша нормального размера
    small_cache = {f"key_{i}": (datetime.now(), f"value_{i}") for i in range(10)}
    results = optimizer.optimize_cache(small_cache)
    
    assert isinstance(results, dict)
    assert "current_size" in results
    assert results["current_size"] == 10

@pytest.mark.asyncio
async def test_run_optimization(optimizer):
    """Тест полной оптимизации"""
    # Мокаем все методы оптимизации
    optimizer.optimize_db_queries = Mock(return_value={
        "unused_indexes": 1,
        "recommendations": ["Optimize index"]
    })
    optimizer.optimize_memory = Mock(return_value={
        "threshold_exceeded": True,
        "initial_usage": 90
    })
    optimizer.optimize_cpu = Mock(return_value={
        "threshold_exceeded": False,
        "cpu_usage": 50
    })
    
    results = await optimizer.run_optimization()
    
    assert isinstance(results, dict)
    assert results["status"] == "success"
    assert "timestamp" in results
    assert "database" in results
    assert "memory" in results
    assert "cpu" in results
    assert "recommendations" in results
    
    # Проверяем обработку ошибок
    optimizer.optimize_db_queries = Mock(side_effect=Exception("Test error"))
    
    results = await optimizer.run_optimization()
    assert results["status"] == "error"
    assert "error" in results

@pytest.mark.asyncio
async def test_start_monitoring(optimizer):
    """Тест мониторинга"""
    # Уменьшаем интервал для теста
    optimizer.optimization_interval = 0.1
    
    # Мокаем run_optimization
    optimizer.run_optimization = Mock(return_value={
        "status": "success",
        "recommendations": ["Test recommendation"]
    })
    
    # Запускаем мониторинг
    task = asyncio.create_task(optimizer.start_monitoring())
    
    # Даем время на несколько итераций
    await asyncio.sleep(0.3)
    
    # Проверяем, что run_optimization вызывался
    assert optimizer.run_optimization.call_count >= 2
    
    # Отменяем задачу
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

def test_error_handling(optimizer):
    """Тест обработки ошибок"""
    # Тест ошибки оптимизации памяти
    with patch('psutil.virtual_memory', side_effect=Exception("Test error")):
        results = optimizer.optimize_memory()
        assert isinstance(results, dict)
        assert len(results) == 0
    
    # Тест ошибки оптимизации CPU
    with patch('psutil.cpu_percent', side_effect=Exception("Test error")):
        results = optimizer.optimize_cpu()
        assert isinstance(results, dict)
        assert len(results) == 0
    
    # Тест ошибки оптимизации кэша
    results = optimizer.optimize_cache(None)
    assert isinstance(results, dict)
    assert len(results) == 0 