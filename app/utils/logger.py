import os
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import aiofiles
from logging.handlers import RotatingFileHandler
import traceback

class LogManager:
    """Менеджер логирования и мониторинга"""
    
    def __init__(self):
        """Инициализация менеджера логирования"""
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # Настройки логирования
        self.settings = {
            "app_log_file": self.logs_dir / "app.log",
            "error_log_file": self.logs_dir / "error.log",
            "access_log_file": self.logs_dir / "access.log",
            "max_file_size": 10 * 1024 * 1024,  # 10 MB
            "backup_count": 5,
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "date_format": "%Y-%m-%d %H:%M:%S"
        }
        
        # Инициализация логгеров
        self._setup_loggers()
        
        # Статистика
        self.stats = {
            "total_requests": 0,
            "error_count": 0,
            "warning_count": 0,
            "last_errors": []
        }
    
    def _setup_loggers(self):
        """Настройка логгеров"""
        # Основной логгер приложения
        app_handler = RotatingFileHandler(
            self.settings["app_log_file"],
            maxBytes=self.settings["max_file_size"],
            backupCount=self.settings["backup_count"]
        )
        app_handler.setFormatter(logging.Formatter(
            self.settings["log_format"],
            self.settings["date_format"]
        ))
        
        self.app_logger = logging.getLogger("app")
        self.app_logger.setLevel(logging.INFO)
        self.app_logger.addHandler(app_handler)
        
        # Логгер ошибок
        error_handler = RotatingFileHandler(
            self.settings["error_log_file"],
            maxBytes=self.settings["max_file_size"],
            backupCount=self.settings["backup_count"]
        )
        error_handler.setFormatter(logging.Formatter(
            self.settings["log_format"],
            self.settings["date_format"]
        ))
        error_handler.setLevel(logging.ERROR)
        
        self.error_logger = logging.getLogger("error")
        self.error_logger.setLevel(logging.ERROR)
        self.error_logger.addHandler(error_handler)
        
        # Логгер доступа
        access_handler = RotatingFileHandler(
            self.settings["access_log_file"],
            maxBytes=self.settings["max_file_size"],
            backupCount=self.settings["backup_count"]
        )
        access_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(message)s",
            self.settings["date_format"]
        ))
        
        self.access_logger = logging.getLogger("access")
        self.access_logger.setLevel(logging.INFO)
        self.access_logger.addHandler(access_handler)
    
    async def log_request(self, user_id: int, command: str, processing_time: float):
        """
        Логирование запроса
        
        :param user_id: ID пользователя
        :param command: Команда
        :param processing_time: Время обработки в секундах
        """
        self.stats["total_requests"] += 1
        
        log_entry = (
            f"User: {user_id}, Command: {command}, "
            f"Processing Time: {processing_time:.3f}s"
        )
        self.access_logger.info(log_entry)
    
    async def log_error(
        self,
        error: Exception,
        user_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Логирование ошибки
        
        :param error: Объект ошибки
        :param user_id: ID пользователя (опционально)
        :param context: Контекст ошибки (опционально)
        """
        self.stats["error_count"] += 1
        
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "user_id": user_id,
            "context": context
        }
        
        # Сохраняем для статистики
        self.stats["last_errors"].append(error_info)
        if len(self.stats["last_errors"]) > 10:  # Храним только последние 10 ошибок
            self.stats["last_errors"].pop(0)
        
        # Логируем ошибку
        error_message = json.dumps(error_info, indent=2)
        self.error_logger.error(error_message)
    
    async def log_warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        """
        Логирование предупреждения
        
        :param message: Сообщение
        :param context: Контекст предупреждения (опционально)
        """
        self.stats["warning_count"] += 1
        
        warning_info = {
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "context": context
        }
        
        self.app_logger.warning(json.dumps(warning_info, indent=2))
    
    async def get_logs(
        self,
        log_type: str = "app",
        limit: int = 100,
        level: Optional[str] = None
    ) -> List[str]:
        """
        Получение логов
        
        :param log_type: Тип логов (app, error, access)
        :param limit: Максимальное количество строк
        :param level: Уровень логирования (опционально)
        :return: Список строк лога
        """
        log_file = self.settings.get(f"{log_type}_log_file")
        if not log_file or not log_file.exists():
            return []
        
        try:
            async with aiofiles.open(log_file, 'r') as f:
                lines = await f.readlines()
                
                # Фильтруем по уровню логирования
                if level:
                    lines = [
                        line for line in lines
                        if f" - {level.upper()} - " in line
                    ]
                
                return lines[-limit:]
        
        except Exception as e:
            self.error_logger.error(f"Ошибка при чтении логов: {e}")
            return []
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики логирования
        
        :return: Словарь со статистикой
        """
        # Получаем размеры файлов логов
        log_sizes = {}
        for log_type in ["app", "error", "access"]:
            log_file = self.settings.get(f"{log_type}_log_file")
            if log_file and log_file.exists():
                log_sizes[log_type] = log_file.stat().st_size
        
        return {
            "total_requests": self.stats["total_requests"],
            "error_count": self.stats["error_count"],
            "warning_count": self.stats["warning_count"],
            "last_errors": self.stats["last_errors"][-5:],  # Последние 5 ошибок
            "log_files": {
                name: {
                    "size_mb": size / (1024 * 1024),
                    "path": str(self.settings[f"{name}_log_file"])
                }
                for name, size in log_sizes.items()
            }
        }
    
    async def cleanup_old_logs(self):
        """Очистка старых файлов логов"""
        try:
            for log_type in ["app", "error", "access"]:
                log_file = self.settings.get(f"{log_type}_log_file")
                if log_file and log_file.exists():
                    # Проверяем размер файла
                    if log_file.stat().st_size > self.settings["max_file_size"]:
                        # Создаем новый файл
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_file = log_file.with_name(f"{log_file.stem}_{timestamp}.log")
                        log_file.rename(backup_file)
                        
                        # Удаляем старые бэкапы
                        backup_files = sorted(
                            log_file.parent.glob(f"{log_file.stem}_*.log"),
                            key=lambda x: x.stat().st_mtime
                        )
                        
                        while len(backup_files) > self.settings["backup_count"]:
                            backup_files[0].unlink()
                            backup_files.pop(0)
        
        except Exception as e:
            self.error_logger.error(f"Ошибка при очистке старых логов: {e}")
    
    async def export_logs(self, export_dir: Path) -> Optional[Path]:
        """
        Экспорт всех логов в архив
        
        :param export_dir: Директория для экспорта
        :return: Путь к архиву или None в случае ошибки
        """
        try:
            import shutil
            
            # Создаем временную директорию для логов
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = export_dir / f"logs_export_{timestamp}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Копируем файлы логов
            for log_type in ["app", "error", "access"]:
                log_file = self.settings.get(f"{log_type}_log_file")
                if log_file and log_file.exists():
                    shutil.copy2(log_file, temp_dir)
            
            # Создаем архив
            archive_path = export_dir / f"logs_export_{timestamp}.zip"
            shutil.make_archive(
                str(archive_path.with_suffix("")),
                'zip',
                temp_dir
            )
            
            # Очищаем временную директорию
            shutil.rmtree(temp_dir)
            
            return archive_path
        
        except Exception as e:
            self.error_logger.error(f"Ошибка при экспорте логов: {e}")
            return None

# Создаем глобальный экземпляр менеджера логирования
log_manager = LogManager() 