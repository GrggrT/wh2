import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from app.utils.scheduler import TaskScheduler
from app.db.models import User, Workplace, Record

@pytest.fixture
async def user():
    """Фикстура для создания тестового пользователя"""
    user = await User.create(
        telegram_id=123456789,
        username='test_user',
        timezone='Europe/Moscow'
    )
    yield user
    await user.delete()

@pytest.fixture
async def workplace(user):
    """Фикстура для создания тестового рабочего места"""
    workplace = await Workplace.create(
        user=user,
        name='Test Workplace',
        rate=1000.50
    )
    yield workplace
    await workplace.delete()

@pytest.fixture
def mock_bot():
    """Фикстура для создания мок-объекта бота"""
    bot = Mock()
    bot.send_message = Mock()
    return bot

@pytest.mark.asyncio
async def test_check_unfinished_records(user, workplace, mock_bot):
    """Тест проверки незавершенных записей"""
    # Создаем тестовую запись
    start_time = datetime.now()
    record = await Record.create(
        user=user,
        workplace=workplace,
        start_time=start_time,
        end_time=None
    )
    
    scheduler = TaskScheduler(mock_bot)
    await scheduler.check_unfinished_records()
    
    # Проверяем, что было отправлено уведомление
    mock_bot.send_message.assert_called_once()
    args = mock_bot.send_message.call_args[0]
    assert args[0] == user.telegram_id
    assert workplace.name in args[1]
    assert start_time.strftime('%H:%M') in args[1]
    
    await record.delete()

@pytest.mark.asyncio
async def test_send_weekly_reports(user, workplace, mock_bot):
    """Тест отправки еженедельных отчетов"""
    # Создаем тестовые записи
    start_time = datetime.now() - timedelta(days=1)
    records = []
    
    for i in range(3):
        record = await Record.create(
            user=user,
            workplace=workplace,
            start_time=start_time + timedelta(hours=i*4),
            end_time=start_time + timedelta(hours=(i+1)*4),
            description=f"Record {i+1}"
        )
        records.append(record)
    
    scheduler = TaskScheduler(mock_bot)
    await scheduler.send_weekly_reports()
    
    # Проверяем, что отчет был отправлен
    mock_bot.send_message.assert_called_once()
    args = mock_bot.send_message.call_args[0]
    assert args[0] == user.telegram_id
    assert "Еженедельный отчет" in args[1]
    assert workplace.name in args[1]
    assert "Итого" in args[1]
    
    for record in records:
        await record.delete()

@pytest.mark.asyncio
async def test_cleanup_old_data(user, workplace):
    """Тест очистки старых данных"""
    # Создаем старую запись
    old_time = datetime.now() - timedelta(days=400)
    old_record = await Record.create(
        user=user,
        workplace=workplace,
        start_time=old_time,
        end_time=old_time + timedelta(hours=4),
        description="Old record"
    )
    
    # Создаем новую запись
    new_time = datetime.now()
    new_record = await Record.create(
        user=user,
        workplace=workplace,
        start_time=new_time,
        end_time=new_time + timedelta(hours=4),
        description="New record"
    )
    
    scheduler = TaskScheduler(Mock())
    await scheduler.cleanup_old_data()
    
    # Проверяем, что старая запись удалена, а новая осталась
    assert not await Record.exists(id=old_record.id)
    assert await Record.exists(id=new_record.id)
    
    await new_record.delete()

@pytest.mark.asyncio
async def test_backup_database(mock_bot):
    """Тест резервного копирования базы данных"""
    with patch('os.system') as mock_system, \
         patch('os.makedirs') as mock_makedirs, \
         patch('os.listdir') as mock_listdir, \
         patch('os.path.getctime') as mock_getctime, \
         patch('os.remove') as mock_remove:
        
        # Настраиваем моки
        mock_system.return_value = 0
        mock_listdir.return_value = ['old_backup.sql']
        mock_getctime.return_value = (datetime.now() - timedelta(days=10)).timestamp()
        
        scheduler = TaskScheduler(mock_bot)
        await scheduler.backup_database()
        
        # Проверяем, что была попытка создать директорию
        mock_makedirs.assert_called_once()
        
        # Проверяем, что была выполнена команда pg_dump
        mock_system.assert_called_once()
        assert 'pg_dump' in mock_system.call_args[0][0]
        
        # Проверяем, что была попытка удалить старый бэкап
        mock_remove.assert_called_once() 