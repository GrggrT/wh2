import pytest
import json
import csv
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from app.utils.export import ExportManager
from app.db.models import User, Workplace, Record
import os

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

@pytest.fixture
async def records(user, workplace):
    """Фикстура для создания тестовых записей"""
    records = []
    start_time = datetime.now() - timedelta(days=7)
    
    for i in range(5):
        record = await Record.create(
            user=user,
            workplace=workplace,
            start_time=start_time + timedelta(days=i, hours=9),
            end_time=start_time + timedelta(days=i, hours=17),
            description=f"Test record {i+1}"
        )
        records.append(record)
    
    yield records
    
    for record in records:
        await record.delete()

@pytest.fixture
def export_manager():
    """Фикстура для создания менеджера экспорта"""
    manager = ExportManager()
    # Создаем временную директорию для тестов
    manager.export_dir = Path("test_exports")
    manager.export_dir.mkdir(exist_ok=True)
    yield manager
    # Очищаем временную директорию
    for file in manager.export_dir.glob("*"):
        file.unlink()
    manager.export_dir.rmdir()

@pytest.mark.asyncio
async def test_export_to_csv(export_manager, user, records):
    """Тест экспорта в CSV"""
    # Экспортируем данные
    file_path = await export_manager.export_records(
        user_id=user.telegram_id,
        export_format="csv"
    )
    
    assert file_path is not None
    assert file_path.exists()
    assert file_path.suffix == ".csv"
    
    # Проверяем содержимое файла
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        assert len(rows) == len(records)
        for row in rows:
            assert "workplace" in row
            assert "start_time" in row
            assert "end_time" in row
            assert "duration_hours" in row
            assert "earnings" in row
            assert "description" in row

@pytest.mark.asyncio
async def test_export_to_json(export_manager, user, records):
    """Тест экспорта в JSON"""
    # Экспортируем данные
    file_path = await export_manager.export_records(
        user_id=user.telegram_id,
        export_format="json"
    )
    
    assert file_path is not None
    assert file_path.exists()
    assert file_path.suffix == ".json"
    
    # Проверяем содержимое файла
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
        assert isinstance(data, list)
        assert len(data) == len(records)
        for item in data:
            assert "workplace" in item
            assert "start_time" in item
            assert "end_time" in item
            assert "duration_hours" in item
            assert "earnings" in item
            assert "description" in item

@pytest.mark.asyncio
async def test_export_to_excel(export_manager, user, records):
    """Тест экспорта в Excel"""
    # Экспортируем данные
    file_path = await export_manager.export_records(
        user_id=user.telegram_id,
        export_format="xlsx"
    )
    
    assert file_path is not None
    assert file_path.exists()
    assert file_path.suffix == ".xlsx"
    
    # Проверяем содержимое файла
    df = pd.read_excel(file_path)
    
    assert len(df) == len(records)
    assert "workplace" in df.columns
    assert "start_time" in df.columns
    assert "end_time" in df.columns
    assert "duration_hours" in df.columns
    assert "earnings" in df.columns
    assert "description" in df.columns

@pytest.mark.asyncio
async def test_export_with_date_filter(export_manager, user, records):
    """Тест экспорта с фильтрацией по датам"""
    start_date = datetime.now() - timedelta(days=3)
    end_date = datetime.now()
    
    # Экспортируем данные с фильтром
    file_path = await export_manager.export_records(
        user_id=user.telegram_id,
        start_date=start_date,
        end_date=end_date,
        export_format="json"
    )
    
    assert file_path is not None
    
    # Проверяем фильтрацию
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
        for item in data:
            record_date = datetime.fromisoformat(item["start_time"])
            assert start_date <= record_date <= end_date

@pytest.mark.asyncio
async def test_export_empty_data(export_manager, user):
    """Тест экспорта при отсутствии данных"""
    # Пробуем экспортировать без записей
    file_path = await export_manager.export_records(
        user_id=user.telegram_id,
        export_format="csv"
    )
    
    assert file_path is None

@pytest.mark.asyncio
async def test_invalid_format(export_manager, user):
    """Тест с неверным форматом экспорта"""
    with pytest.raises(ValueError):
        await export_manager.export_records(
            user_id=user.telegram_id,
            export_format="invalid"
        )

@pytest.mark.asyncio
async def test_cleanup_old_exports(export_manager):
    """Тест очистки старых экспортов"""
    # Создаем тестовые файлы
    old_file = export_manager.export_dir / "export_old.csv"
    new_file = export_manager.export_dir / "export_new.csv"
    
    old_file.write_text("test")
    new_file.write_text("test")
    
    # Изменяем время модификации старого файла
    old_time = datetime.now() - timedelta(days=10)
    os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))
    
    # Запускаем очистку
    await export_manager.cleanup_old_exports(days=7)
    
    assert not old_file.exists()
    assert new_file.exists()

@pytest.mark.asyncio
async def test_error_handling(export_manager, user, records):
    """Тест обработки ошибок"""
    # Тест ошибки при записи в файл
    with patch('aiofiles.open', side_effect=Exception("Test error")):
        file_path = await export_manager.export_records(
            user_id=user.telegram_id,
            export_format="csv"
        )
        assert file_path is None
    
    # Тест ошибки при создании Excel файла
    with patch('pandas.DataFrame.to_excel', side_effect=Exception("Test error")):
        file_path = await export_manager.export_records(
            user_id=user.telegram_id,
            export_format="xlsx"
        )
        assert file_path is None

@pytest.mark.asyncio
async def test_concurrent_exports(export_manager, user, records):
    """Тест одновременных экспортов"""
    import asyncio
    
    # Запускаем несколько экспортов одновременно
    tasks = []
    for format in ["csv", "json", "xlsx"]:
        task = asyncio.create_task(
            export_manager.export_records(
                user_id=user.telegram_id,
                export_format=format
            )
        )
        tasks.append(task)
    
    # Ждем завершения всех экспортов
    results = await asyncio.gather(*tasks)
    
    # Проверяем результаты
    assert all(result is not None for result in results)
    assert len(set(str(result) for result in results)) == len(results)  # Уникальные имена файлов 