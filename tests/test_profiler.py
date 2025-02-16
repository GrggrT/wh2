import pytest
import time
import asyncio
from unittest.mock import Mock, patch, mock_open
from app.utils.profiler import Profiler

@pytest.fixture
def profiler():
    """Фикстура для создания профилировщика"""
    with patch.dict('os.environ', {'ENABLE_PROFILING': 'true'}):
        return Profiler()

def test_profiler_initialization(profiler):
    """Тест инициализации профилировщика"""
    assert profiler.enabled is True
    assert profiler.slow_threshold == 1.0
    assert isinstance(profiler.execution_times, dict)
    assert isinstance(profiler.db_queries, dict)

def test_profiler_disabled():
    """Тест отключенного профилировщика"""
    with patch.dict('os.environ', {'ENABLE_PROFILING': 'false'}):
        profiler = Profiler()
        assert profiler.enabled is False
        
        # Проверяем, что декоратор не изменяет функцию
        @profiler.profile
        def test_func():
            return "test"
        
        assert test_func() == "test"

def test_track_db_query(profiler):
    """Тест отслеживания запросов к БД"""
    profiler.track_db_query("SELECT")
    profiler.track_db_query("SELECT")
    profiler.track_db_query("INSERT")
    
    assert profiler.db_queries["SELECT"] == 2
    assert profiler.db_queries["INSERT"] == 1

def test_reset_stats(profiler):
    """Тест сброса статистики"""
    profiler.track_db_query("SELECT")
    profiler.execution_times["test"] = [1.0, 2.0]
    
    profiler.reset_stats()
    
    assert len(profiler.db_queries) == 0
    assert len(profiler.execution_times) == 0

def test_get_stats(profiler):
    """Тест получения статистики"""
    profiler.track_db_query("SELECT")
    profiler.execution_times["test"] = [1.0, 2.0, 3.0]
    
    stats = profiler.get_stats()
    
    assert stats["db_queries"]["SELECT"] == 1
    assert stats["total_db_queries"] == 1
    assert "test" in stats["execution_times"]
    assert stats["execution_times"]["test"]["min"] == 1.0
    assert stats["execution_times"]["test"]["max"] == 3.0
    assert stats["execution_times"]["test"]["avg"] == 2.0
    assert stats["execution_times"]["test"]["count"] == 3

def test_analyze_slow_queries(profiler):
    """Тест анализа медленных запросов"""
    profiler.slow_threshold = 1.0
    profiler.execution_times["fast"] = [0.5, 0.7]
    profiler.execution_times["slow"] = [1.5, 2.0]
    
    slow_queries = profiler.analyze_slow_queries()
    
    assert "fast" not in slow_queries
    assert "slow" in slow_queries
    assert slow_queries["slow"]["count"] == 2
    assert slow_queries["slow"]["avg_time"] == 1.75
    assert slow_queries["slow"]["max_time"] == 2.0

@pytest.mark.asyncio
async def test_profile_async_function(profiler):
    """Тест профилирования асинхронной функции"""
    @profiler.profile
    async def test_async():
        await asyncio.sleep(0.1)
        return "test"
    
    result = await test_async()
    
    assert result == "test"
    assert len(profiler.execution_times["test_async"]) == 1
    assert profiler.execution_times["test_async"][0] >= 0.1

def test_profile_sync_function(profiler):
    """Тест профилирования синхронной функции"""
    @profiler.profile
    def test_sync():
        time.sleep(0.1)
        return "test"
    
    result = test_sync()
    
    assert result == "test"
    assert len(profiler.execution_times["test_sync"]) == 1
    assert profiler.execution_times["test_sync"][0] >= 0.1

@pytest.mark.asyncio
async def test_analyze_db_performance(profiler):
    """Тест анализа производительности БД"""
    # Мокаем подключение к БД
    mock_conn = Mock()
    mock_conn.execute_query = Mock()
    
    # Настраиваем результаты запросов
    index_stats = [
        ("public", "users", "users_pkey", 0),  # Неиспользуемый индекс
        ("public", "records", "records_idx", 1000)
    ]
    
    table_stats = [
        ("public", "users", 150, None, None, 2000),  # Много сканирований и мертвых строк
        ("public", "records", 50, None, None, 100)
    ]
    
    mock_conn.execute_query.side_effect = [index_stats, table_stats]
    
    with patch('tortoise.Tortoise.get_connection', return_value=mock_conn):
        results = await profiler.analyze_db_performance()
        
        assert "indexes" in results
        assert "tables" in results
        assert "recommendations" in results
        
        recommendations = results["recommendations"]
        assert any("Неиспользуемый индекс" in r for r in recommendations)
        assert any("Возможно нужен индекс" in r for r in recommendations)
        assert any("Требуется VACUUM" in r for r in recommendations)

def test_profile_with_error(profiler):
    """Тест профилирования с ошибкой"""
    @profiler.profile
    def error_func():
        raise ValueError("Test error")
    
    with pytest.raises(ValueError) as exc_info:
        error_func()
    
    assert "Test error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_profile_with_custom_name(profiler):
    """Тест профилирования с пользовательским именем"""
    @profiler.profile(name="custom_name")
    async def test_func():
        await asyncio.sleep(0.1)
        return "test"
    
    result = await test_func()
    
    assert result == "test"
    assert "custom_name" in profiler.execution_times
    assert len(profiler.execution_times["custom_name"]) == 1

def test_profiler_file_output(profiler):
    """Тест вывода в файл"""
    mock_file = mock_open()
    
    with patch('builtins.open', mock_file):
        @profiler.profile
        def test_func():
            time.sleep(0.1)
            return "test"
        
        test_func()
    
    # Проверяем, что файлы были созданы
    assert mock_file.call_count >= 2  # .prof и .txt файлы
    
    # Проверяем аргументы вызова open()
    calls = mock_file.call_args_list
    assert any(call[0][0].endswith('.prof') for call in calls)
    assert any(call[0][0].endswith('.txt') for call in calls) 