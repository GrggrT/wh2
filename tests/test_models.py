import pytest
from datetime import datetime, timedelta
from app.db.models import User, Workplace, Record

@pytest.mark.asyncio
async def test_user_creation():
    """Тест создания пользователя"""
    user_data = {
        'telegram_id': 123456789,
        'username': 'test_user',
        'timezone': 'Europe/Moscow'
    }
    
    # Создаем пользователя
    user = await User.create(**user_data)
    
    # Проверяем, что пользователь создан корректно
    assert user.telegram_id == user_data['telegram_id']
    assert user.username == user_data['username']
    assert user.timezone == user_data['timezone']
    
    # Проверяем, что created_at установлен
    assert user.created_at is not None
    
    # Очищаем тестовые данные
    await user.delete()

@pytest.mark.asyncio
async def test_workplace_creation():
    """Тест создания рабочего места"""
    # Создаем пользователя
    user = await User.create(
        telegram_id=123456789,
        username='test_user',
        timezone='Europe/Moscow'
    )
    
    workplace_data = {
        'user': user,
        'name': 'Test Workplace',
        'rate': 1000.50
    }
    
    # Создаем рабочее место
    workplace = await Workplace.create(**workplace_data)
    
    # Проверяем, что рабочее место создано корректно
    assert workplace.name == workplace_data['name']
    assert float(workplace.rate) == workplace_data['rate']
    assert workplace.user.telegram_id == user.telegram_id
    
    # Проверяем, что created_at установлен
    assert workplace.created_at is not None
    
    # Очищаем тестовые данные
    await workplace.delete()
    await user.delete()

@pytest.mark.asyncio
async def test_record_creation():
    """Тест создания записи рабочего времени"""
    # Создаем пользователя и рабочее место
    user = await User.create(
        telegram_id=123456789,
        username='test_user',
        timezone='Europe/Moscow'
    )
    
    workplace = await Workplace.create(
        user=user,
        name='Test Workplace',
        rate=1000.50
    )
    
    # Данные для записи
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=4)
    description = "Test work description"
    
    record_data = {
        'user': user,
        'workplace': workplace,
        'start_time': start_time,
        'end_time': end_time,
        'description': description
    }
    
    # Создаем запись
    record = await Record.create(**record_data)
    
    # Проверяем, что запись создана корректно
    assert record.user.telegram_id == user.telegram_id
    assert record.workplace.id == workplace.id
    assert record.start_time == start_time
    assert record.end_time == end_time
    assert record.description == description
    
    # Проверяем, что created_at и updated_at установлены
    assert record.created_at is not None
    assert record.updated_at is not None
    
    # Очищаем тестовые данные
    await record.delete()
    await workplace.delete()
    await user.delete()

@pytest.mark.asyncio
async def test_user_workplaces_relationship():
    """Тест связи пользователя с рабочими местами"""
    # Создаем пользователя
    user = await User.create(
        telegram_id=123456789,
        username='test_user',
        timezone='Europe/Moscow'
    )
    
    # Создаем несколько рабочих мест
    workplace1 = await Workplace.create(
        user=user,
        name='Workplace 1',
        rate=1000.50
    )
    
    workplace2 = await Workplace.create(
        user=user,
        name='Workplace 2',
        rate=1500.75
    )
    
    # Получаем рабочие места пользователя
    user_workplaces = await Workplace.filter(user=user)
    
    # Проверяем, что у пользователя правильное количество рабочих мест
    assert len(user_workplaces) == 2
    
    # Проверяем, что это те самые рабочие места
    workplace_names = {w.name for w in user_workplaces}
    assert workplace_names == {'Workplace 1', 'Workplace 2'}
    
    # Очищаем тестовые данные
    await Workplace.filter(user=user).delete()
    await user.delete()

@pytest.mark.asyncio
async def test_cascade_deletion():
    """Тест каскадного удаления"""
    # Создаем пользователя
    user = await User.create(
        telegram_id=123456789,
        username='test_user',
        timezone='Europe/Moscow'
    )
    
    # Создаем рабочее место
    workplace = await Workplace.create(
        user=user,
        name='Test Workplace',
        rate=1000.50
    )
    
    # Создаем несколько записей
    start_time = datetime.now()
    for i in range(3):
        await Record.create(
            user=user,
            workplace=workplace,
            start_time=start_time + timedelta(hours=i*4),
            end_time=start_time + timedelta(hours=(i+1)*4),
            description=f"Record {i+1}"
        )
    
    # Проверяем, что записи созданы
    records_count = await Record.filter(user=user).count()
    assert records_count == 3
    
    # Удаляем пользователя
    await user.delete()
    
    # Проверяем, что все связанные записи удалены
    workplace_exists = await Workplace.exists(id=workplace.id)
    assert not workplace_exists
    
    records_exist = await Record.filter(workplace=workplace).exists()
    assert not records_exist 