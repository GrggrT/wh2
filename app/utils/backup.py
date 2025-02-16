import os
import logging
import asyncio
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import aiofiles
import aiohttp
import json
from pathlib import Path
from app.utils.profiler import profiler

logger = logging.getLogger(__name__)

class BackupManager:
    """Менеджер резервного копирования"""
    
    def __init__(self):
        """Инициализация менеджера"""
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        self.config_dir = Path("config")
        self.config_dir.mkdir(exist_ok=True)
        
        self.retention_days = 7  # Хранить бэкапы 7 дней
        self.is_running = False
        
        # Настройки
        self.settings = {
            "backup_interval": 24 * 60 * 60,  # Раз в сутки
            "compress_backups": True,
            "upload_to_remote": False,
            "remote_url": os.getenv("BACKUP_REMOTE_URL", ""),
            "remote_token": os.getenv("BACKUP_REMOTE_TOKEN", "")
        }
    
    async def create_database_backup(self) -> Optional[Path]:
        """
        Создание резервной копии базы данных
        
        :return: Путь к файлу бэкапа или None в случае ошибки
        """
        try:
            # Получаем параметры подключения из переменных окружения
            db_name = os.getenv("DB_NAME")
            db_user = os.getenv("DB_USER")
            db_password = os.getenv("DB_PASSWORD")
            db_host = os.getenv("DB_HOST")
            
            if not all([db_name, db_user, db_password, db_host]):
                raise ValueError("Не все параметры БД заданы в переменных окружения")
            
            # Формируем имя файла для бэкапа
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"db_backup_{timestamp}.sql"
            
            # Формируем команду для pg_dump
            command = (
                f"PGPASSWORD='{db_password}' pg_dump "
                f"-h {db_host} -U {db_user} -d {db_name} "
                f"-F p -f {backup_file}"
            )
            
            # Выполняем команду
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"Создана резервная копия БД: {backup_file}")
                
                if self.settings["compress_backups"]:
                    # Сжимаем файл
                    compressed_file = Path(str(backup_file) + ".gz")
                    await self._compress_file(backup_file, compressed_file)
                    backup_file.unlink()  # Удаляем несжатый файл
                    backup_file = compressed_file
                
                return backup_file
            else:
                error_msg = stderr.decode() if stderr else "Неизвестная ошибка"
                raise Exception(f"Ошибка при создании бэкапа: {error_msg}")
        
        except Exception as e:
            logger.error(f"Ошибка при создании резервной копии БД: {e}")
            return None
    
    async def create_config_backup(self) -> Optional[Path]:
        """
        Создание резервной копии конфигурации
        
        :return: Путь к файлу бэкапа или None в случае ошибки
        """
        try:
            # Собираем конфигурацию
            config = {
                "env_vars": {
                    key: value
                    for key, value in os.environ.items()
                    if key.startswith(("BOT_", "DB_", "BACKUP_"))
                },
                "settings": self.settings,
                "timestamp": datetime.now().isoformat()
            }
            
            # Формируем имя файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            config_file = self.config_dir / f"config_backup_{timestamp}.json"
            
            # Сохраняем конфигурацию
            async with aiofiles.open(config_file, 'w') as f:
                await f.write(json.dumps(config, indent=2))
            
            logger.info(f"Создана резервная копия конфигурации: {config_file}")
            return config_file
        
        except Exception as e:
            logger.error(f"Ошибка при создании резервной копии конфигурации: {e}")
            return None
    
    async def restore_from_backup(self, backup_file: Path) -> bool:
        """
        Восстановление из резервной копии
        
        :param backup_file: Путь к файлу бэкапа
        :return: True если восстановление успешно
        """
        try:
            if not backup_file.exists():
                raise FileNotFoundError(f"Файл бэкапа не найден: {backup_file}")
            
            # Получаем параметры подключения
            db_name = os.getenv("DB_NAME")
            db_user = os.getenv("DB_USER")
            db_password = os.getenv("DB_PASSWORD")
            db_host = os.getenv("DB_HOST")
            
            if not all([db_name, db_user, db_password, db_host]):
                raise ValueError("Не все параметры БД заданы в переменных окружения")
            
            # Проверяем, является ли файл сжатым
            is_compressed = backup_file.suffix == '.gz'
            if is_compressed:
                # Распаковываем файл
                uncompressed_file = Path(str(backup_file)[:-3])
                await self._decompress_file(backup_file, uncompressed_file)
                backup_file = uncompressed_file
            
            # Формируем команду для восстановления
            command = (
                f"PGPASSWORD='{db_password}' psql "
                f"-h {db_host} -U {db_user} -d {db_name} "
                f"-f {backup_file}"
            )
            
            # Выполняем команду
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"База данных успешно восстановлена из: {backup_file}")
                return True
            else:
                error_msg = stderr.decode() if stderr else "Неизвестная ошибка"
                raise Exception(f"Ошибка при восстановлении: {error_msg}")
        
        except Exception as e:
            logger.error(f"Ошибка при восстановлении из бэкапа: {e}")
            return False
        finally:
            # Удаляем распакованный файл, если он был создан
            if is_compressed and backup_file != Path(str(backup_file) + ".gz"):
                backup_file.unlink()
    
    async def cleanup_old_backups(self):
        """Очистка старых резервных копий"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # Очищаем старые бэкапы БД
            for backup_file in self.backup_dir.glob("db_backup_*.sql*"):
                try:
                    # Извлекаем дату из имени файла
                    timestamp = datetime.strptime(
                        backup_file.stem.split('_')[2],
                        "%Y%m%d"
                    )
                    
                    if timestamp.date() < cutoff_date.date():
                        backup_file.unlink()
                        logger.info(f"Удален старый бэкап: {backup_file}")
                except (ValueError, IndexError):
                    continue
            
            # Очищаем старые бэкапы конфигурации
            for config_file in self.config_dir.glob("config_backup_*.json"):
                try:
                    timestamp = datetime.strptime(
                        config_file.stem.split('_')[2],
                        "%Y%m%d"
                    )
                    
                    if timestamp.date() < cutoff_date.date():
                        config_file.unlink()
                        logger.info(f"Удалена старая конфигурация: {config_file}")
                except (ValueError, IndexError):
                    continue
        
        except Exception as e:
            logger.error(f"Ошибка при очистке старых бэкапов: {e}")
    
    async def upload_to_remote(self, file_path: Path) -> bool:
        """
        Загрузка бэкапа на удаленный сервер
        
        :param file_path: Путь к файлу для загрузки
        :return: True если загрузка успешна
        """
        if not self.settings["upload_to_remote"]:
            return False
        
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"Файл не найден: {file_path}")
            
            headers = {
                "Authorization": f"Bearer {self.settings['remote_token']}",
                "Content-Type": "application/octet-stream"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.settings["remote_url"],
                    data=file_path.read_bytes(),
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.info(f"Файл {file_path} успешно загружен на удаленный сервер")
                        return True
                    else:
                        raise Exception(
                            f"Ошибка при загрузке: {response.status} - {await response.text()}"
                        )
        
        except Exception as e:
            logger.error(f"Ошибка при загрузке файла на удаленный сервер: {e}")
            return False
    
    @staticmethod
    async def _compress_file(source: Path, target: Path):
        """
        Сжатие файла
        
        :param source: Исходный файл
        :param target: Целевой файл
        """
        import gzip
        with open(source, 'rb') as f_in:
            with gzip.open(target, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    @staticmethod
    async def _decompress_file(source: Path, target: Path):
        """
        Распаковка файла
        
        :param source: Исходный файл
        :param target: Целевой файл
        """
        import gzip
        with gzip.open(source, 'rb') as f_in:
            with open(target, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    @profiler.profile(name="run_backup")
    async def run_backup(self) -> Dict[str, Any]:
        """
        Запуск полного процесса резервного копирования
        
        :return: Результаты резервного копирования
        """
        results = {
            "success": False,
            "database_backup": None,
            "config_backup": None,
            "uploaded_to_remote": False,
            "errors": []
        }
        
        try:
            # Создаем бэкап БД
            db_backup = await self.create_database_backup()
            if db_backup:
                results["database_backup"] = str(db_backup)
                
                # Загружаем на удаленный сервер
                if self.settings["upload_to_remote"]:
                    uploaded = await self.upload_to_remote(db_backup)
                    results["uploaded_to_remote"] = uploaded
            else:
                results["errors"].append("Ошибка при создании бэкапа БД")
            
            # Создаем бэкап конфигурации
            config_backup = await self.create_config_backup()
            if config_backup:
                results["config_backup"] = str(config_backup)
            else:
                results["errors"].append("Ошибка при создании бэкапа конфигурации")
            
            # Очищаем старые бэкапы
            await self.cleanup_old_backups()
            
            results["success"] = not results["errors"]
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении резервного копирования: {e}")
            results["errors"].append(str(e))
        
        return results
    
    async def start(self):
        """Запуск периодического резервного копирования"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Запущен процесс резервного копирования")
        
        while self.is_running:
            try:
                results = await self.run_backup()
                if results["success"]:
                    logger.info("Резервное копирование успешно выполнено")
                else:
                    logger.error(
                        f"Ошибки при резервном копировании: {', '.join(results['errors'])}"
                    )
            except Exception as e:
                logger.error(f"Ошибка в цикле резервного копирования: {e}")
            
            await asyncio.sleep(self.settings["backup_interval"])
    
    async def stop(self):
        """Остановка процесса резервного копирования"""
        self.is_running = False
        logger.info("Остановлен процесс резервного копирования")

# Создаем глобальный экземпляр менеджера
backup_manager = BackupManager() 