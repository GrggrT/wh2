import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from tortoise import Tortoise

from app.bot import register_handlers, on_startup, on_shutdown
from app.db.models import User, Workplace, Record
from app.utils.scheduler import setup_scheduler
from app.utils.notifications import setup_notifications
from app.utils.performance import optimizer
from app.utils.health_check import HealthCheck

@pytest.fixture
async def database():
    """Фикстура для инициализации тестовой базы данных"""
    # Используем SQLite для тестов
    await Tortoise.init(
        db_url='sqlite://:memory:',
        modules={'models': ['app.db.models']}
    )
    await Tortoise.generate_schemas()
    
    yield
    
    await Tortoise.close_connections()

@pytest.fixture
def mock_bot():
    """Фикстура для создания мок-объекта бота"""
    bot = Mock(spec=Bot)
    bot.send_message = Mock()
    return bot

@pytest.fixture
def dispatcher(mock_bot):
    """Фикстура для создания диспетчера"""
    storage = MemoryStorage()
    dp = Dispatcher(mock_bot, storage=storage)
    register_handlers(dp)
    return dp

@pytest.fixture
async def user(database):
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
async def test_full_startup_shutdown(mock_bot, dispatcher, database):
    """Тест полного цикла запуска и остановки бота"""
    # Запуск
    await on_startup(dispatcher)
    
    # Проверяем инициализацию компонентов
    mock_bot.send_message.assert_called_once()
    message_text = mock_bot.send_message.call_args[0][1]
    assert "Бот запущен" in message_text
    assert "База данных: подключена" in message_text
    assert "Планировщик: активен" in message_text
    assert "Уведомления: активны" in message_text
    assert "Оптимизация: активна" in message_text
    
    # Остановка
    await on_shutdown(dispatcher)
    
    # Проверяем корректную остановку
    assert mock_bot.send_message.call_count == 2
    last_message = mock_bot.send_message.call_args[0][1]
    assert "Бот останавливается" in last_message

@pytest.mark.asyncio
async def test_record_workflow(mock_bot, dispatcher, user, workplace):
    """Тест полного рабочего процесса с записями"""
    # Создание записи
    record = await Record.create(
        user=user,
        workplace=workplace,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(hours=8),
        description="Test record"
    )
    
    # Проверка создания записи
    assert record.id is not None
    assert record.user.id == user.id
    assert record.workplace.id == workplace.id
    
    # Проверка уведомлений
    notifications = setup_notifications(mock_bot)
    await notifications.check_unfinished_records()
    
    # Проверка оптимизации
    results = await optimizer.run_optimization()
    assert results["status"] == "success"
    
    # Проверка health check
    health_check = HealthCheck(mock_bot)
    status = await health_check.check()
    assert status["meta"]["status"] == "healthy"
    
    # Очистка
    await record.delete()

@pytest.mark.asyncio
async def test_concurrent_operations(mock_bot, dispatcher, user, workplace):
    """Тест параллельных операций"""
    async def create_record(delay: float):
        await asyncio.sleep(delay)
        return await Record.create(
            user=user,
            workplace=workplace,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=8)
        )
    
    # Создаем несколько записей параллельно
    records = await asyncio.gather(*[
        create_record(delay)
        for delay in [0.1, 0.2, 0.3]
    ])
    
    # Проверяем создание всех записей
    assert len(records) == 3
    assert all(r.id is not None for r in records)
    
    # Проверяем работу планировщика
    scheduler = setup_scheduler(mock_bot)
    assert scheduler.scheduler.running
    
    # Очистка
    for record in records:
        await record.delete()

@pytest.mark.asyncio
async def test_error_handling(mock_bot, dispatcher, user, workplace):
    """Тест обработки ошибок"""
    # Тест ошибки создания записи
    with pytest.raises(ValueError):
        await Record.create(
            user=user,
            workplace=workplace,
            start_time=datetime.now() + timedelta(hours=1),  # Будущее время
            end_time=datetime.now()  # Прошлое время
        )
    
    # Тест ошибки в планировщике
    scheduler = setup_scheduler(mock_bot)
    scheduler.scheduler.add_job(
        lambda: 1/0,  # Заведомо ошибочная операция
        'interval',
        seconds=1,
        id='error_job'
    )
    await asyncio.sleep(1.1)
    
    # Тест ошибки в оптимизаторе
    with patch('app.utils.performance.PerformanceOptimizer.optimize_db_queries',
              side_effect=Exception("Test error")):
        results = await optimizer.run_optimization()
        assert results["status"] == "error"
        assert "Test error" in results["error"]

@pytest.mark.asyncio
async def test_data_consistency(mock_bot, dispatcher, user, workplace):
    """Тест целостности данных"""
    # Создаем тестовые данные
    records = []
    for i in range(5):
        record = await Record.create(
            user=user,
            workplace=workplace,
            start_time=datetime.now() + timedelta(days=i),
            end_time=datetime.now() + timedelta(days=i, hours=8)
        )
        records.append(record)
    
    # Проверяем связи
    user_records = await Record.filter(user=user)
    assert len(user_records) == 5
    
    workplace_records = await Record.filter(workplace=workplace)
    assert len(workplace_records) == 5
    
    # Проверяем каскадное удаление
    await workplace.delete()
    remaining_records = await Record.filter(workplace=workplace)
    assert len(remaining_records) == 0
    
    # Проверяем статистику
    total_users = await User.all().count()
    assert total_users > 0
    
    # Очистка
    await user.delete()

@pytest.mark.asyncio
async def test_performance_monitoring(mock_bot, dispatcher, user, workplace):
    """Тест мониторинга производительности"""
    # Создаем нагрузку
    records = []
    for i in range(100):
        record = await Record.create(
            user=user,
            workplace=workplace,
            start_time=datetime.now() + timedelta(days=i),
            end_time=datetime.now() + timedelta(days=i, hours=8)
        )
        records.append(record)
    
    # Проверяем оптимизацию
    results = await optimizer.run_optimization()
    assert results["status"] == "success"
    assert "database" in results
    assert "memory" in results
    assert "cpu" in results
    
    # Проверяем статистику запросов
    db_stats = results["database"]
    assert "slow_queries" in db_stats
    
    # Проверяем использование памяти
    memory_stats = results["memory"]
    assert not memory_stats.get("threshold_exceeded", False)
    
    # Очистка
    for record in records:
        await record.delete()

@pytest.mark.asyncio
async def test_notification_system(mock_bot, dispatcher, user, workplace):
    """Тест системы уведомлений"""
    # Создаем незавершенную запись
    record = await Record.create(
        user=user,
        workplace=workplace,
        start_time=datetime.now(),
        end_time=None
    )
    
    # Инициализируем систему уведомлений
    notifications = setup_notifications(mock_bot)
    
    # Проверяем отправку уведомлений
    await notifications.check_unfinished_records()
    
    # Проверяем вызов отправки сообщения
    assert mock_bot.send_message.called
    message_text = mock_bot.send_message.call_args[0][1]
    assert "незавершенная запись" in message_text
    assert workplace.name in message_text
    
    # Очистка
    await record.delete()

@pytest.mark.asyncio
async def test_system_health(mock_bot, dispatcher, database):
    """Тест проверки здоровья системы"""
    # Инициализируем health check
    health_check = HealthCheck(mock_bot)
    
    # Проверяем все компоненты
    status = await health_check.check()
    
    # Проверяем результаты
    assert status["meta"]["status"] == "healthy"
    assert status["database"]["status"] == "healthy"
    assert status["telegram_api"]["status"] == "healthy"
    assert status["scheduler"]["status"] == "healthy"
    assert status["system"]["status"] == "healthy" 