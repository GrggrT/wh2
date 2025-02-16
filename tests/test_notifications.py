import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from aiogram import Bot
from app.utils.notifications import NotificationManager, setup_notifications
from app.db.models import User, Workplace, Record
import asyncio

@pytest.fixture
def mock_bot():
    """Фикстура для создания мок-объекта бота"""
    bot = Mock(spec=Bot)
    bot.send_message = Mock()
    bot.get_me = Mock(return_value=Mock(id=123456789))
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
    # Устанавливаем текущее время в тихий период
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime.now().replace(hour=23, minute=30)
        is_quiet = await notification_manager.is_quiet_hours(user)
        assert is_quiet is True
        
        # Проверяем активное время
        mock_datetime.now.return_value = datetime.now().replace(hour=14, minute=0)
        is_quiet = await notification_manager.is_quiet_hours(user)
        assert is_quiet is False

@pytest.mark.asyncio
async def test_process_notifications(notification_manager, user):
    """Тест обработки уведомлений"""
    # Добавляем тестовое уведомление
    await notification_manager.add_notification(
        user_id=user.telegram_id,
        notification_type="test",
        message="Test message",
        priority="normal"
    )
    
    # Обрабатываем уведомления
    await notification_manager.process_notifications()
    
    # Проверяем, что уведомление было отправлено
    notification_manager.bot.send_message.assert_called_once_with(
        user.telegram_id,
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
    assert workplace.name in notification["message"]
    
    await record.delete()

@pytest.mark.asyncio
async def test_check_performance_alerts(notification_manager):
    """Тест проверки оповещений о производительности"""
    # Мокаем профилировщик
    with patch('app.utils.profiler.profiler') as mock_profiler:
        mock_profiler.get_stats.return_value = {"test": "stats"}
        mock_profiler.analyze_slow_queries.return_value = {
            "slow_operation": {
                "count": 5,
                "avg_time": 2.5,
                "max_time": 3.0
            }
        }
        
        # Проверяем оповещения о производительности
        await notification_manager.check_performance_alerts()
        
        # Проверяем, что уведомление было добавлено
        assert len(notification_manager.notification_queue) == 1
        notification = notification_manager.notification_queue[0]
        assert notification["type"] == "performance_alert"
        assert notification["priority"] == "high"
        assert "Медленные операции" in notification["message"]

@pytest.mark.asyncio
async def test_notification_manager_lifecycle(notification_manager):
    """Тест жизненного цикла менеджера уведомлений"""
    # Запускаем менеджер
    task = asyncio.create_task(notification_manager.start())
    
    # Даем время на запуск
    await asyncio.sleep(0.1)
    
    assert notification_manager.is_running is True
    
    # Останавливаем менеджер
    await notification_manager.stop()
    
    assert notification_manager.is_running is False
    
    # Отменяем задачу
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

@pytest.mark.asyncio
async def test_scheduled_notifications(notification_manager, user):
    """Тест запланированных уведомлений"""
    # Добавляем уведомление на будущее время
    future_time = datetime.now() + timedelta(hours=1)
    await notification_manager.add_notification(
        user_id=user.telegram_id,
        notification_type="scheduled",
        message="Scheduled message",
        scheduled_time=future_time
    )
    
    # Проверяем, что уведомление не отправляется сразу
    await notification_manager.process_notifications()
    notification_manager.bot.send_message.assert_not_called()
    
    # Эмулируем наступление времени отправки
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = future_time + timedelta(minutes=1)
        await notification_manager.process_notifications()
        
        # Проверяем отправку уведомления
        notification_manager.bot.send_message.assert_called_once()

def test_setup_notifications(mock_bot):
    """Тест инициализации системы уведомлений"""
    manager = setup_notifications(mock_bot)
    assert isinstance(manager, NotificationManager)
    assert manager.bot == mock_bot 