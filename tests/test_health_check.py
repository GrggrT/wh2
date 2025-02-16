import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from aiogram import Bot
from app.utils.health_check import HealthCheck
import asyncio

@pytest.fixture
def mock_bot():
    """Фикстура для создания мок-объекта бота"""
    bot = Mock(spec=Bot)
    bot.get_me = Mock()
    bot.get_me.return_value = Mock(
        id=123456789,
        username="test_bot",
        is_bot=True
    )
    bot.send_message = Mock()
    return bot

@pytest.fixture
def health_check(mock_bot):
    """Фикстура для создания объекта HealthCheck"""
    with patch.dict('os.environ', {'ADMIN_ID': '123456789'}):
        return HealthCheck(mock_bot)

@pytest.mark.asyncio
async def test_check_database(health_check):
    """Тест проверки базы данных"""
    # Мокаем выполнение запроса
    with patch('tortoise.Tortoise.get_connection') as mock_conn:
        mock_conn.return_value.execute_query = Mock()
        mock_conn.return_value.execute_query.side_effect = [
            None,  # Для SELECT 1
            [(5,)]  # Для count(*) FROM pg_stat_activity
        ]
        
        result = await health_check.check_database()
        
        assert result["status"] == "healthy"
        assert "latency_ms" in result
        assert result["connections"] == 5
        
        # Тест ошибки
        mock_conn.return_value.execute_query.side_effect = Exception("Test error")
        result = await health_check.check_database()
        
        assert result["status"] == "unhealthy"
        assert "error" in result

@pytest.mark.asyncio
async def test_check_telegram_api(health_check, mock_bot):
    """Тест проверки Telegram API"""
    result = await health_check.check_telegram_api()
    
    assert result["status"] == "healthy"
    assert "latency_ms" in result
    assert result["bot_info"]["username"] == "test_bot"
    
    # Тест ошибки
    mock_bot.get_me.side_effect = Exception("Test error")
    result = await health_check.check_telegram_api()
    
    assert result["status"] == "unhealthy"
    assert "error" in result

@pytest.mark.asyncio
async def test_check_scheduler(health_check):
    """Тест проверки планировщика"""
    with patch('app.utils.scheduler.scheduler') as mock_scheduler:
        mock_scheduler.scheduler.running = True
        mock_job = Mock()
        mock_job.id = "test_job"
        mock_job.next_run_time = datetime.now()
        mock_scheduler.scheduler.get_jobs.return_value = [mock_job]
        
        result = await health_check.check_scheduler()
        
        assert result["status"] == "healthy"
        assert result["jobs_count"] == 1
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["id"] == "test_job"
        
        # Тест ошибки
        mock_scheduler.scheduler.running = False
        result = await health_check.check_scheduler()
        
        assert result["status"] == "unhealthy"
        assert "error" in result

def test_check_system_resources(health_check):
    """Тест проверки системных ресурсов"""
    with patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.disk_usage') as mock_disk, \
         patch('psutil.cpu_percent') as mock_cpu:
        
        mock_memory.return_value = Mock(
            total=8 * 1024 * 1024 * 1024,  # 8 GB
            used=4 * 1024 * 1024 * 1024,   # 4 GB
            percent=50.0
        )
        mock_disk.return_value = Mock(
            total=100 * 1024 * 1024 * 1024,  # 100 GB
            used=50 * 1024 * 1024 * 1024,    # 50 GB
            percent=50.0
        )
        mock_cpu.return_value = 25.0
        
        result = health_check.check_system_resources()
        
        assert result["status"] == "healthy"
        assert result["memory"]["total_mb"] == 8 * 1024
        assert result["memory"]["used_mb"] == 4 * 1024
        assert result["memory"]["percent"] == 50.0
        assert result["disk"]["total_gb"] == 100
        assert result["disk"]["used_gb"] == 50
        assert result["disk"]["percent"] == 50.0
        assert result["cpu_percent"] == 25.0

@pytest.mark.asyncio
async def test_check_timezone_sync(health_check):
    """Тест проверки синхронизации часовых поясов"""
    with patch('app.utils.timezone_sync.timezone_sync') as mock_sync:
        mock_sync.get_timezone_info.return_value = {"timezone": "UTC"}
        mock_sync.last_sync = {1: datetime.now()}
        
        result = await health_check.check_timezone_sync()
        
        assert result["status"] == "healthy"
        assert "last_sync" in result
        assert result["users_synced"] == 1
        
        # Тест ошибки
        mock_sync.get_timezone_info.return_value = None
        result = await health_check.check_timezone_sync()
        
        assert result["status"] == "unhealthy"
        assert "error" in result

@pytest.mark.asyncio
async def test_check_all(health_check):
    """Тест полной проверки состояния"""
    with patch.multiple(health_check,
                       check_database=Mock(return_value={"status": "healthy"}),
                       check_telegram_api=Mock(return_value={"status": "healthy"}),
                       check_scheduler=Mock(return_value={"status": "healthy"}),
                       check_system_resources=Mock(return_value={"status": "healthy"}),
                       check_timezone_sync=Mock(return_value={"status": "healthy"})):
        
        result = await health_check.check()
        
        assert result["meta"]["status"] == "healthy"
        assert health_check.is_healthy is True
        assert health_check.error_count == 0
        
        # Тест с ошибкой в одном компоненте
        health_check.check_database.return_value = {"status": "unhealthy", "error": "Test error"}
        result = await health_check.check()
        
        assert result["meta"]["status"] == "unhealthy"
        assert health_check.is_healthy is False
        assert health_check.error_count == 1

@pytest.mark.asyncio
async def test_notify_admin(health_check, mock_bot):
    """Тест отправки уведомлений администратору"""
    status = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "status": "unhealthy"
        },
        "database": {
            "status": "unhealthy",
            "error": "Connection error"
        },
        "telegram_api": {
            "status": "healthy"
        }
    }
    
    await health_check.notify_admin(status)
    
    mock_bot.send_message.assert_called_once()
    message_text = mock_bot.send_message.call_args[0][1]
    assert "Проблемы с работой бота" in message_text
    assert "database" in message_text
    assert "Connection error" in message_text

@pytest.mark.asyncio
async def test_monitoring_cycle(health_check):
    """Тест цикла мониторинга"""
    # Устанавливаем короткий интервал для теста
    health_check.check_interval = 0.1
    
    # Мокаем методы
    health_check.check = Mock()
    health_check.check.return_value = {"meta": {"status": "healthy"}}
    health_check.notify_admin = Mock()
    
    # Запускаем мониторинг в фоне
    task = asyncio.create_task(health_check.start_monitoring())
    
    # Ждем несколько циклов
    await asyncio.sleep(0.3)
    
    # Отменяем задачу
    task.cancel()
    
    # Проверяем, что check вызывался несколько раз
    assert health_check.check.call_count >= 2
    
    # Проверяем, что уведомления не отправлялись (так как статус healthy)
    health_check.notify_admin.assert_not_called() 