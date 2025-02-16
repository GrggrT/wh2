import pytest
import json
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from app.utils.logger import LogManager

@pytest.fixture
def log_manager():
    """Фикстура для создания менеджера логирования"""
    # Создаем временную директорию для тестовых логов
    test_logs_dir = Path("test_logs")
    test_logs_dir.mkdir(exist_ok=True)
    
    # Создаем менеджер с тестовыми настройками
    manager = LogManager()
    manager.logs_dir = test_logs_dir
    manager.settings.update({
        "app_log_file": test_logs_dir / "app.log",
        "error_log_file": test_logs_dir / "error.log",
        "access_log_file": test_logs_dir / "access.log",
        "max_file_size": 1024,  # 1 KB для тестов
        "backup_count": 2
    })
    
    # Переинициализируем логгеры с новыми настройками
    manager._setup_loggers()
    
    yield manager
    
    # Очищаем тестовые файлы
    shutil.rmtree(test_logs_dir)

@pytest.mark.asyncio
async def test_log_request(log_manager):
    """Тест логирования запросов"""
    await log_manager.log_request(123456789, "/test", 0.5)
    
    # Проверяем статистику
    assert log_manager.stats["total_requests"] == 1
    
    # Проверяем файл лога
    async with aiofiles.open(log_manager.settings["access_log_file"], 'r') as f:
        lines = await f.readlines()
        assert len(lines) == 1
        assert "User: 123456789" in lines[0]
        assert "Command: /test" in lines[0]
        assert "Processing Time: 0.500s" in lines[0]

@pytest.mark.asyncio
async def test_log_error(log_manager):
    """Тест логирования ошибок"""
    test_error = ValueError("Test error")
    await log_manager.log_error(
        test_error,
        user_id=123456789,
        context={"test": "context"}
    )
    
    # Проверяем статистику
    assert log_manager.stats["error_count"] == 1
    assert len(log_manager.stats["last_errors"]) == 1
    
    error_info = log_manager.stats["last_errors"][0]
    assert error_info["error_type"] == "ValueError"
    assert error_info["error_message"] == "Test error"
    assert error_info["user_id"] == 123456789
    assert error_info["context"] == {"test": "context"}
    
    # Проверяем файл лога
    async with aiofiles.open(log_manager.settings["error_log_file"], 'r') as f:
        content = await f.read()
        error_log = json.loads(content)
        assert error_log["error_type"] == "ValueError"
        assert error_log["error_message"] == "Test error"

@pytest.mark.asyncio
async def test_log_warning(log_manager):
    """Тест логирования предупреждений"""
    await log_manager.log_warning(
        "Test warning",
        context={"test": "context"}
    )
    
    # Проверяем статистику
    assert log_manager.stats["warning_count"] == 1
    
    # Проверяем файл лога
    async with aiofiles.open(log_manager.settings["app_log_file"], 'r') as f:
        content = await f.read()
        warning_log = json.loads(content)
        assert warning_log["message"] == "Test warning"
        assert warning_log["context"] == {"test": "context"}

@pytest.mark.asyncio
async def test_get_logs(log_manager):
    """Тест получения логов"""
    # Создаем тестовые логи
    for i in range(5):
        await log_manager.log_request(123456789, f"/test_{i}", 0.5)
        await log_manager.log_warning(f"Warning {i}")
        await log_manager.log_error(ValueError(f"Error {i}"))
    
    # Получаем логи разных типов
    access_logs = await log_manager.get_logs("access", limit=3)
    assert len(access_logs) == 3
    assert "test_4" in access_logs[-1]
    
    app_logs = await log_manager.get_logs("app", limit=3, level="WARNING")
    assert len(app_logs) == 3
    assert "Warning" in app_logs[-1]
    
    error_logs = await log_manager.get_logs("error", limit=3)
    assert len(error_logs) == 3
    assert "Error" in error_logs[-1]

@pytest.mark.asyncio
async def test_get_statistics(log_manager):
    """Тест получения статистики"""
    # Создаем тестовые логи
    await log_manager.log_request(123456789, "/test", 0.5)
    await log_manager.log_warning("Test warning")
    await log_manager.log_error(ValueError("Test error"))
    
    stats = await log_manager.get_statistics()
    
    assert stats["total_requests"] == 1
    assert stats["error_count"] == 1
    assert stats["warning_count"] == 1
    assert len(stats["last_errors"]) == 1
    assert len(stats["log_files"]) == 3
    
    for log_type in ["app", "error", "access"]:
        assert log_type in stats["log_files"]
        assert stats["log_files"][log_type]["size_mb"] > 0

@pytest.mark.asyncio
async def test_cleanup_old_logs(log_manager):
    """Тест очистки старых логов"""
    # Создаем большое количество логов
    large_data = "x" * 1000  # 1 KB данных
    for _ in range(3):  # Создаем 3 KB данных (больше max_file_size)
        await log_manager.log_warning(large_data)
    
    # Запускаем очистку
    await log_manager.cleanup_old_logs()
    
    # Проверяем, что созданы бэкапы
    backup_files = list(log_manager.logs_dir.glob("app_*.log"))
    assert len(backup_files) <= log_manager.settings["backup_count"]

@pytest.mark.asyncio
async def test_export_logs(log_manager):
    """Тест экспорта логов"""
    # Создаем тестовые логи
    await log_manager.log_request(123456789, "/test", 0.5)
    await log_manager.log_warning("Test warning")
    await log_manager.log_error(ValueError("Test error"))
    
    # Создаем временную директорию для экспорта
    export_dir = Path("test_export")
    export_dir.mkdir(exist_ok=True)
    
    try:
        # Экспортируем логи
        archive_path = await log_manager.export_logs(export_dir)
        
        assert archive_path is not None
        assert archive_path.exists()
        assert archive_path.suffix == ".zip"
        
        # Проверяем содержимое архива
        import zipfile
        with zipfile.ZipFile(archive_path) as zf:
            files = zf.namelist()
            assert "app.log" in files
            assert "error.log" in files
            assert "access.log" in files
    
    finally:
        # Очищаем тестовые файлы
        shutil.rmtree(export_dir)

@pytest.mark.asyncio
async def test_error_handling(log_manager):
    """Тест обработки ошибок"""
    # Тест с несуществующим типом лога
    logs = await log_manager.get_logs("invalid_type")
    assert logs == []
    
    # Тест с ошибкой при чтении файла
    with patch('aiofiles.open', side_effect=Exception("Test error")):
        logs = await log_manager.get_logs("app")
        assert logs == []
    
    # Тест с ошибкой при экспорте
    with patch('shutil.make_archive', side_effect=Exception("Test error")):
        result = await log_manager.export_logs(Path("test_export"))
        assert result is None

@pytest.mark.asyncio
async def test_log_rotation(log_manager):
    """Тест ротации логов"""
    # Уменьшаем максимальный размер файла для теста
    log_manager.settings["max_file_size"] = 100  # 100 байт
    
    # Создаем логи, превышающие лимит
    for i in range(10):
        await log_manager.log_warning("x" * 20)  # 20 байт на каждое сообщение
    
    # Проверяем, что созданы ротированные файлы
    log_files = list(log_manager.logs_dir.glob("app*.log*"))
    assert len(log_files) > 1
    
    # Проверяем, что количество файлов не превышает backup_count
    assert len(log_files) <= log_manager.settings["backup_count"] + 1 