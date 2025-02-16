import pytest
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import asyncio
import aiohttp
from app.utils.backup import BackupManager

@pytest.fixture
def backup_manager():
    """Фикстура для создания менеджера бэкапов"""
    with patch.dict('os.environ', {
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass',
        'DB_HOST': 'localhost',
        'BACKUP_REMOTE_URL': 'https://example.com/backup',
        'BACKUP_REMOTE_TOKEN': 'test_token'
    }):
        manager = BackupManager()
        # Уменьшаем интервал для тестов
        manager.settings["backup_interval"] = 0.1
        return manager

@pytest.fixture
def mock_subprocess():
    """Фикстура для мока subprocess"""
    with patch('asyncio.create_subprocess_shell') as mock:
        process_mock = Mock()
        process_mock.communicate = Mock(return_value=(b"", b""))
        process_mock.returncode = 0
        mock.return_value = process_mock
        yield mock

@pytest.mark.asyncio
async def test_create_database_backup(backup_manager, mock_subprocess):
    """Тест создания резервной копии БД"""
    backup_file = await backup_manager.create_database_backup()
    
    assert backup_file is not None
    assert backup_file.exists()
    assert backup_file.suffix in ['.sql', '.gz']
    
    # Проверяем вызов pg_dump
    mock_subprocess.assert_called_once()
    command = mock_subprocess.call_args[0][0]
    assert 'pg_dump' in command
    assert '-h localhost' in command
    assert '-U test_user' in command
    assert '-d test_db' in command
    
    # Очищаем тестовый файл
    backup_file.unlink()

@pytest.mark.asyncio
async def test_create_config_backup(backup_manager):
    """Тест создания резервной копии конфигурации"""
    config_file = await backup_manager.create_config_backup()
    
    assert config_file is not None
    assert config_file.exists()
    assert config_file.suffix == '.json'
    
    # Проверяем содержимое файла
    with open(config_file) as f:
        config = json.load(f)
        assert "env_vars" in config
        assert "settings" in config
        assert "timestamp" in config
        assert config["env_vars"]["DB_NAME"] == "test_db"
    
    # Очищаем тестовый файл
    config_file.unlink()

@pytest.mark.asyncio
async def test_restore_from_backup(backup_manager, mock_subprocess):
    """Тест восстановления из бэкапа"""
    # Создаем тестовый файл бэкапа
    test_backup = backup_manager.backup_dir / "test_backup.sql"
    test_backup.write_text("-- Test backup")
    
    # Тестируем восстановление
    result = await backup_manager.restore_from_backup(test_backup)
    assert result is True
    
    # Проверяем вызов psql
    mock_subprocess.assert_called_once()
    command = mock_subprocess.call_args[0][0]
    assert 'psql' in command
    assert '-h localhost' in command
    assert '-U test_user' in command
    assert '-d test_db' in command
    
    # Очищаем тестовый файл
    test_backup.unlink()

@pytest.mark.asyncio
async def test_cleanup_old_backups(backup_manager):
    """Тест очистки старых бэкапов"""
    # Создаем тестовые файлы
    old_date = datetime.now() - timedelta(days=backup_manager.retention_days + 1)
    new_date = datetime.now()
    
    # Старые файлы
    old_backup = backup_manager.backup_dir / f"db_backup_{old_date.strftime('%Y%m%d')}_120000.sql"
    old_config = backup_manager.config_dir / f"config_backup_{old_date.strftime('%Y%m%d')}_120000.json"
    
    # Новые файлы
    new_backup = backup_manager.backup_dir / f"db_backup_{new_date.strftime('%Y%m%d')}_120000.sql"
    new_config = backup_manager.config_dir / f"config_backup_{new_date.strftime('%Y%m%d')}_120000.json"
    
    # Создаем файлы
    for file in [old_backup, old_config, new_backup, new_config]:
        file.write_text("test")
    
    # Запускаем очистку
    await backup_manager.cleanup_old_backups()
    
    # Проверяем результаты
    assert not old_backup.exists()
    assert not old_config.exists()
    assert new_backup.exists()
    assert new_config.exists()
    
    # Очищаем тестовые файлы
    new_backup.unlink()
    new_config.unlink()

@pytest.mark.asyncio
async def test_upload_to_remote(backup_manager):
    """Тест загрузки на удаленный сервер"""
    # Создаем тестовый файл
    test_file = backup_manager.backup_dir / "test_upload.sql"
    test_file.write_text("test data")
    
    # Включаем загрузку на удаленный сервер
    backup_manager.settings["upload_to_remote"] = True
    
    # Мокаем aiohttp.ClientSession
    with patch('aiohttp.ClientSession') as mock_session:
        mock_response = Mock()
        mock_response.status = 200
        mock_response.__aenter__ = Mock(return_value=mock_response)
        mock_response.__aexit__ = Mock()
        
        mock_session.return_value.post.return_value = mock_response
        mock_session.return_value.__aenter__ = Mock(return_value=mock_session.return_value)
        mock_session.return_value.__aexit__ = Mock()
        
        # Тестируем загрузку
        result = await backup_manager.upload_to_remote(test_file)
        assert result is True
        
        # Проверяем вызов API
        mock_session.return_value.post.assert_called_once()
        call_args = mock_session.return_value.post.call_args
        assert call_args[0][0] == backup_manager.settings["remote_url"]
        assert "Authorization" in call_args[1]["headers"]
    
    # Очищаем тестовый файл
    test_file.unlink()

@pytest.mark.asyncio
async def test_compression(backup_manager):
    """Тест сжатия и распаковки файлов"""
    # Создаем тестовый файл
    test_file = backup_manager.backup_dir / "test_compression.sql"
    test_data = "test " * 1000  # Создаем данные для сжатия
    test_file.write_text(test_data)
    
    # Сжимаем файл
    compressed_file = Path(str(test_file) + ".gz")
    await backup_manager._compress_file(test_file, compressed_file)
    
    assert compressed_file.exists()
    assert compressed_file.stat().st_size < test_file.stat().st_size
    
    # Распаковываем файл
    decompressed_file = backup_manager.backup_dir / "test_decompressed.sql"
    await backup_manager._decompress_file(compressed_file, decompressed_file)
    
    assert decompressed_file.exists()
    assert decompressed_file.read_text() == test_data
    
    # Очищаем тестовые файлы
    test_file.unlink()
    compressed_file.unlink()
    decompressed_file.unlink()

@pytest.mark.asyncio
async def test_run_backup(backup_manager, mock_subprocess):
    """Тест полного процесса резервного копирования"""
    results = await backup_manager.run_backup()
    
    assert isinstance(results, dict)
    assert results["success"] is True
    assert results["database_backup"] is not None
    assert results["config_backup"] is not None
    assert isinstance(results["errors"], list)
    assert len(results["errors"]) == 0
    
    # Очищаем созданные файлы
    if results["database_backup"]:
        Path(results["database_backup"]).unlink()
    if results["config_backup"]:
        Path(results["config_backup"]).unlink()

@pytest.mark.asyncio
async def test_backup_manager_lifecycle(backup_manager):
    """Тест жизненного цикла менеджера бэкапов"""
    # Запускаем менеджер
    task = asyncio.create_task(backup_manager.start())
    await asyncio.sleep(0.2)  # Даем время на запуск
    
    assert backup_manager.is_running is True
    
    # Останавливаем менеджер
    await backup_manager.stop()
    await asyncio.sleep(0.1)
    
    assert backup_manager.is_running is False
    
    # Отменяем задачу
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

@pytest.mark.asyncio
async def test_error_handling(backup_manager):
    """Тест обработки ошибок"""
    # Тест с неверными параметрами БД
    with patch.dict('os.environ', {'DB_NAME': ''}):
        backup_file = await backup_manager.create_database_backup()
        assert backup_file is None
    
    # Тест с несуществующим файлом бэкапа
    result = await backup_manager.restore_from_backup(Path("nonexistent.sql"))
    assert result is False
    
    # Тест с ошибкой при загрузке на сервер
    test_file = backup_manager.backup_dir / "test_error.sql"
    test_file.write_text("test")
    
    backup_manager.settings["upload_to_remote"] = True
    with patch('aiohttp.ClientSession') as mock_session:
        mock_session.return_value.post.side_effect = aiohttp.ClientError()
        result = await backup_manager.upload_to_remote(test_file)
        assert result is False
    
    test_file.unlink() 