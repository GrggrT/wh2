import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from app.utils.timezone_sync import TimeZoneSync
from app.db.models import User
import asyncio

@pytest.fixture
async def user():
    """Фикстура для создания тестового пользователя"""
    user = await User.create(
        telegram_id=123456789,
        username="test_user",
        timezone="Europe/Moscow"
    )
    yield user
    await user.delete()

@pytest.fixture
def timezone_sync():
    """Фикстура для создания синхронизатора"""
    with patch.dict('os.environ', {'TIMEZONE_DB_API_KEY': 'test_key'}):
        return TimeZoneSync()

@pytest.mark.asyncio
async def test_get_timezone_info(timezone_sync):
    """Тест получения информации о часовом поясе"""
    # Подготавливаем мок для _make_request
    timezone_sync._make_request = Mock()
    timezone_sync._make_request.return_value = {
        "status": "OK",
        "zoneName": "Europe/Moscow",
        "gmtOffset": 10800,  # UTC+3
    }
    
    # Получаем информацию о часовом поясе
    result = await timezone_sync.get_timezone_info("Europe/Moscow")
    
    # Проверяем результат
    assert result is not None
    assert result["timezone"] == "Europe/Moscow"
    assert result["offset"] == 10800
    assert result["formatted"] == "UTC+3"
    
    # Проверяем вызов _make_request
    timezone_sync._make_request.assert_called_once_with(
        "get-time-zone",
        {"zone": "Europe/Moscow", "by": "zone"}
    )

@pytest.mark.asyncio
async def test_sync_user_timezone(timezone_sync, user):
    """Тест синхронизации часового пояса пользователя"""
    # Подготавливаем мок для get_timezone_info
    timezone_sync.get_timezone_info = Mock()
    timezone_sync.get_timezone_info.return_value = {
        "timezone": "Europe/Moscow",
        "offset": 10800,
        "formatted": "UTC+3"
    }
    
    # Синхронизируем часовой пояс
    result = await timezone_sync.sync_user_timezone(user)
    
    # Проверяем результат
    assert result is True
    assert user.timezone == "Europe/Moscow"
    assert user.telegram_id in timezone_sync.last_sync
    
    # Проверяем, что повторная синхронизация не выполняется
    timezone_sync.get_timezone_info.reset_mock()
    result = await timezone_sync.sync_user_timezone(user)
    assert result is True
    timezone_sync.get_timezone_info.assert_not_called()

@pytest.mark.asyncio
async def test_sync_all_users(timezone_sync):
    """Тест синхронизации всех пользователей"""
    # Создаем тестовых пользователей
    users = []
    for i in range(3):
        user = await User.create(
            telegram_id=1000 + i,
            username=f"test_user_{i}",
            timezone="Europe/Moscow"
        )
        users.append(user)
    
    # Подготавливаем мок для sync_user_timezone
    timezone_sync.sync_user_timezone = Mock()
    timezone_sync.sync_user_timezone.side_effect = [True, False, True]
    
    # Синхронизируем всех пользователей
    results = await timezone_sync.sync_all_users()
    
    # Проверяем результаты
    assert len(results["success"]) == 2
    assert len(results["failed"]) == 1
    assert timezone_sync.sync_user_timezone.call_count == 3
    
    # Очищаем тестовые данные
    for user in users:
        await user.delete()

@pytest.mark.asyncio
async def test_error_handling(timezone_sync, user):
    """Тест обработки ошибок"""
    # Тест ошибки API
    timezone_sync._make_request = Mock()
    timezone_sync._make_request.return_value = None
    result = await timezone_sync.get_timezone_info("Invalid/Zone")
    assert result is None
    
    # Тест ошибки синхронизации
    timezone_sync.get_timezone_info = Mock()
    timezone_sync.get_timezone_info.side_effect = Exception("Test error")
    result = await timezone_sync.sync_user_timezone(user)
    assert result is False

@pytest.mark.asyncio
async def test_periodic_sync(timezone_sync):
    """Тест периодической синхронизации"""
    # Устанавливаем короткий интервал для теста
    timezone_sync.sync_interval = timedelta(seconds=0.1)
    
    # Подготавливаем мок для sync_all_users
    timezone_sync.sync_all_users = Mock()
    timezone_sync.sync_all_users.return_value = {"success": [], "failed": []}
    
    # Запускаем периодическую синхронизацию в фоне
    task = asyncio.create_task(timezone_sync.start_periodic_sync())
    
    # Ждем несколько циклов
    await asyncio.sleep(0.3)
    
    # Отменяем задачу
    task.cancel()
    
    # Проверяем, что sync_all_users вызывался несколько раз
    assert timezone_sync.sync_all_users.call_count >= 2

@pytest.mark.asyncio
async def test_timezone_validation(timezone_sync):
    """Тест валидации часовых поясов"""
    # Тест валидного часового пояса
    timezone_sync._make_request = Mock()
    timezone_sync._make_request.return_value = {
        "status": "OK",
        "zoneName": "Europe/London",
        "gmtOffset": 0
    }
    result = await timezone_sync.get_timezone_info("Europe/London")
    assert result["formatted"] == "UTC+0"
    
    # Тест отрицательного смещения
    timezone_sync._make_request.return_value = {
        "status": "OK",
        "zoneName": "America/New_York",
        "gmtOffset": -18000  # UTC-5
    }
    result = await timezone_sync.get_timezone_info("America/New_York")
    assert result["formatted"] == "UTC-5" 