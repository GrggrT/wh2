import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from aiogram import Bot
from app.utils.notifications import NotificationManager, setup_notifications
from app.db.models import User, Workplace, Record

@pytest.fixture
def mock_bot():
    """Фикстура для создания мок-объекта бота"""
    bot = Mock(spec=Bot)
    bot.send_message = Mock()
    return bot

@pytest.fixture
def notification_manager(mock_bot):
    """Фикстура для создания менеджера уведомлений"""
    return NotificationManager(mock_bot)

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
async def workplace(user):
    """Фикстура для создания тестового рабочего места"""
    workplace = await Workplace.create(
        user=user,
        name="Test Workplace",
        rate=1000.50
    )
    yield workplace
    await workplace.delete()

@pytest.mark.asyncio
async def test_add_notification(notification_manager):
    """Тест добавления уведомления"""
    result = await notification_manager.add_notification(
        user_id=123456789,
        notification_type="test",
        message="Test message",
        priority="normal"
    )
    
    assert result is True
    assert len(notification_manager.notification_queue) == 1
    notification = notification_manager.notification_queue[0]
    assert notification["user_id"] == 123456789
    assert notification["type"] == "test"
    assert notification["message"] == "Test message"
    assert notification["priority"] == "normal"

@pytest.mark.asyncio
async def test_quiet_hours(notification_manager, user):
    """Тест проверки тихого режима"""
    with patch('datetime.datetime') as mock_datetime:
        # Тест ночного времени
        mock_datetime.now.return_value = datetime(2024, 1, 1, 23, 30)
        assert await notification_manager.is_quiet_hours(user) is True
        
        # Тест дневного времени
        mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 0)
        assert await notification_manager.is_quiet_hours(user) is False

@pytest.mark.asyncio
async def test_process_notifications(notification_manager):
    """Тест обработки уведомлений"""
    # Добавляем тестовое уведомление
    await notification_manager.add_notification(
        user_id=123456789,
        notification_type="test",
        message="Test message",
        priority="high"
    )
    
    # Обрабатываем уведомления
    await notification_manager.process_notifications()
    
    # Проверяем, что уведомление было отправлено
    notification_manager.bot.send_message.assert_called_once_with(
        123456789,
        "Test message"
    )
    assert len(notification_manager.notification_queue) == 0

@pytest.mark.asyncio
async def test_check_unfinished_records(notification_manager, user, workplace):
    """Тест проверки незавершенных записей"""
    # Создаем незавершенную запись
    record = await Record.create(
        user=user,
        workplace=workplace,
        start_time=datetime.now(),
        end_time=None
    )
    
    # Проверяем незавершенные записи
    await notification_manager.check_unfinished_records()
    
    # Проверяем, что уведомление было добавлено
    assert len(notification_manager.notification_queue) == 1
    notification = notification_manager.notification_queue[0]
    assert notification["user_id"] == user.telegram_id
    assert notification["type"] == "task_reminder"
    assert "незавершенная запись" in notification["message"]
    
    await record.delete()

@pytest.mark.asyncio
async def test_performance_alerts(notification_manager):
    """Тест проверки оповещений о производительности"""
    with patch('app.utils.profiler.profiler.analyze_slow_queries') as mock_analyze:
        # Имитируем медленные запросы
        mock_analyze.return_value = {
            "test_operation": {
                "count": 10,
                "avg_time": 2.5,
                "max_time": 5.0
            }
        }
        
        # Проверяем оповещения о производительности
        await notification_manager.check_performance_alerts()
        
        # Проверяем, что уведомление было добавлено
        assert len(notification_manager.notification_queue) == 1
        notification = notification_manager.notification_queue[0]
        assert notification["type"] == "performance_alert"
        assert notification["priority"] == "high"
        assert "проблемы с производительностью" in notification["message"]

@pytest.mark.asyncio
async def test_notification_manager_lifecycle(notification_manager):
    """Тест жизненного цикла менеджера уведомлений"""
    # Запускаем менеджер уведомлений
    task = asyncio.create_task(notification_manager.start())
    await asyncio.sleep(0.1)
    
    assert notification_manager.is_running is True
    
    # Останавливаем менеджер
    await notification_manager.stop()
    await asyncio.sleep(0.1)
    
    assert notification_manager.is_running is False
    task.cancel()

@pytest.mark.asyncio
async def test_scheduled_notifications(notification_manager):
    """Тест запланированных уведомлений"""
    # Добавляем запланированное уведомление
    scheduled_time = datetime.now() + timedelta(hours=1)
    await notification_manager.add_notification(
        user_id=123456789,
        notification_type="scheduled",
        message="Scheduled message",
        scheduled_time=scheduled_time
    )
    
    # Проверяем, что уведомление не отправляется раньше времени
    await notification_manager.process_notifications()
    notification_manager.bot.send_message.assert_not_called()
    
    # Имитируем наступление времени отправки
    notification_manager.notification_queue[0]["scheduled_time"] = datetime.now()
    await notification_manager.process_notifications()
    
    notification_manager.bot.send_message.assert_called_once_with(
        123456789,
        "Scheduled message"
    )

@pytest.mark.asyncio
async def test_setup_notifications(mock_bot):
    """Тест инициализации системы уведомлений"""
    manager = setup_notifications(mock_bot)
    assert isinstance(manager, NotificationManager)
    assert manager.bot == mock_bot
    assert manager.is_running is False
    assert len(manager.notification_queue) == 0 