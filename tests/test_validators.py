import pytest
from datetime import datetime, time
from app.utils.validators import (
    WorkplaceInput,
    TimeInput,
    RecordInput,
    parse_time,
    parse_date
)

def test_workplace_input_validation():
    """Тест валидации входных данных рабочего места"""
    # Тест валидных данных
    valid_data = {
        'name': 'Test Workplace',
        'rate': 1000.50
    }
    workplace = WorkplaceInput(**valid_data)
    assert workplace.name == valid_data['name']
    assert workplace.rate == valid_data['rate']
    
    # Тест пустого названия
    with pytest.raises(ValueError):
        WorkplaceInput(name='', rate=1000.50)
    
    # Тест слишком длинного названия
    with pytest.raises(ValueError):
        WorkplaceInput(name='a' * 101, rate=1000.50)
    
    # Тест отрицательной ставки
    with pytest.raises(ValueError):
        WorkplaceInput(name='Test', rate=-100)

def test_time_input_validation():
    """Тест валидации времени"""
    # Тест валидных данных
    valid_data = {
        'hour': 14,
        'minute': 30
    }
    time_input = TimeInput(**valid_data)
    assert time_input.hour == valid_data['hour']
    assert time_input.minute == valid_data['minute']
    
    # Тест невалидного часа
    with pytest.raises(ValueError):
        TimeInput(hour=24, minute=0)
    
    # Тест невалидных минут
    with pytest.raises(ValueError):
        TimeInput(hour=12, minute=60)
    
    # Тест преобразования в time
    time_obj = time_input.to_time()
    assert isinstance(time_obj, time)
    assert time_obj.hour == valid_data['hour']
    assert time_obj.minute == valid_data['minute']

def test_record_input_validation():
    """Тест валидации записи рабочего времени"""
    start_time = datetime.now()
    end_time = start_time.replace(hour=start_time.hour + 2)
    
    # Тест валидных данных
    valid_data = {
        'workplace_id': 1,
        'start_time': start_time,
        'end_time': end_time,
        'description': 'Test description'
    }
    record = RecordInput(**valid_data)
    assert record.workplace_id == valid_data['workplace_id']
    assert record.start_time == valid_data['start_time']
    assert record.end_time == valid_data['end_time']
    assert record.description == valid_data['description']
    
    # Тест конца раньше начала
    with pytest.raises(ValueError):
        RecordInput(
            workplace_id=1,
            start_time=end_time,
            end_time=start_time,
            description='Test'
        )
    
    # Тест слишком длинного описания
    with pytest.raises(ValueError):
        RecordInput(
            workplace_id=1,
            start_time=start_time,
            end_time=end_time,
            description='a' * 501
        )

def test_parse_time():
    """Тест парсинга времени"""
    # Тест валидного времени
    time_str = "14:30"
    time_input = parse_time(time_str)
    assert time_input.hour == 14
    assert time_input.minute == 30
    
    # Тест невалидного формата
    with pytest.raises(ValueError):
        parse_time("14.30")
    
    with pytest.raises(ValueError):
        parse_time("25:00")
    
    with pytest.raises(ValueError):
        parse_time("14:60")

def test_parse_date():
    """Тест парсинга даты"""
    # Тест валидной даты
    date_str = "01.02.2024"
    date = parse_date(date_str)
    assert date.day == 1
    assert date.month == 2
    assert date.year == 2024
    
    # Тест невалидного формата
    with pytest.raises(ValueError):
        parse_date("2024-02-01")
    
    with pytest.raises(ValueError):
        parse_date("32.13.2024")
    
    with pytest.raises(ValueError):
        parse_date("invalid") 