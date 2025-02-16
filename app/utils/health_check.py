import logging
import asyncio
import os
import psutil
from datetime import datetime
from typing import Dict, Any
from tortoise import Tortoise
from aiogram import Bot
from app.utils.scheduler import scheduler
from app.utils.timezone_sync import timezone_sync

logger = logging.getLogger(__name__)

class HealthCheck:
    """Класс для проверки состояния приложения"""
    
    def __init__(self, bot: Bot):
        """
        Инициализация
        
        :param bot: Экземпляр бота
        """
        self.bot = bot
        self.last_check = None
        self.is_healthy = False
        self.admin_id = os.getenv("ADMIN_ID")
        self.check_interval = 60  # Интервал проверки в секундах
        self.alert_threshold = 3  # Количество ошибок подряд для оповещения
        self.error_count = 0
    
    async def check_database(self) -> Dict[str, Any]:
        """
        Проверка подключения к базе данных
        
        :return: Результат проверки
        """
        try:
            conn = Tortoise.get_connection("default")
            await conn.execute_query("SELECT 1")
            return {
                "status": "healthy",
                "latency_ms": 0,  # TODO: Добавить измерение латентности
                "connections": await conn.execute_query("SELECT count(*) FROM pg_stat_activity")[0][0]
            }
        except Exception as e:
            logger.error(f"Ошибка при проверке базы данных: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_telegram_api(self) -> Dict[str, Any]:
        """
        Проверка подключения к Telegram API
        
        :return: Результат проверки
        """
        try:
            start_time = datetime.now()
            me = await self.bot.get_me()
            latency = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "bot_info": {
                    "id": me.id,
                    "username": me.username,
                    "is_bot": me.is_bot
                }
            }
        except Exception as e:
            logger.error(f"Ошибка при проверке Telegram API: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_scheduler(self) -> Dict[str, Any]:
        """
        Проверка работы планировщика
        
        :return: Результат проверки
        """
        try:
            if not scheduler or not scheduler.scheduler.running:
                raise Exception("Планировщик не запущен")
            
            jobs = scheduler.scheduler.get_jobs()
            return {
                "status": "healthy",
                "jobs_count": len(jobs),
                "jobs": [
                    {
                        "id": job.id,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None
                    }
                    for job in jobs
                ]
            }
        except Exception as e:
            logger.error(f"Ошибка при проверке планировщика: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """
        Проверка системных ресурсов
        
        :return: Результат проверки
        """
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "status": "healthy",
                "memory": {
                    "total_mb": memory.total // (1024 * 1024),
                    "used_mb": memory.used // (1024 * 1024),
                    "percent": memory.percent
                },
                "disk": {
                    "total_gb": disk.total // (1024 * 1024 * 1024),
                    "used_gb": disk.used // (1024 * 1024 * 1024),
                    "percent": disk.percent
                },
                "cpu_percent": psutil.cpu_percent(interval=1)
            }
        except Exception as e:
            logger.error(f"Ошибка при проверке системных ресурсов: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_timezone_sync(self) -> Dict[str, Any]:
        """
        Проверка синхронизации часовых поясов
        
        :return: Результат проверки
        """
        try:
            # Проверяем доступность API
            test_result = await timezone_sync.get_timezone_info("UTC")
            if not test_result:
                raise Exception("Не удалось получить информацию о часовом поясе")
            
            return {
                "status": "healthy",
                "last_sync": max(timezone_sync.last_sync.values()).isoformat() if timezone_sync.last_sync else None,
                "users_synced": len(timezone_sync.last_sync)
            }
        except Exception as e:
            logger.error(f"Ошибка при проверке синхронизации часовых поясов: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check(self) -> Dict[str, Any]:
        """
        Проверка состояния всех компонентов
        
        :return: Словарь с результатами проверки
        """
        self.last_check = datetime.now()
        
        # Проверяем все компоненты
        results = {
            "database": await self.check_database(),
            "telegram_api": await self.check_telegram_api(),
            "scheduler": await self.check_scheduler(),
            "system": self.check_system_resources(),
            "timezone_sync": await self.check_timezone_sync()
        }
        
        # Определяем общий статус
        components_healthy = all(
            component["status"] == "healthy"
            for component in results.values()
        )
        
        if components_healthy:
            self.is_healthy = True
            self.error_count = 0
        else:
            self.is_healthy = False
            self.error_count += 1
        
        results["meta"] = {
            "timestamp": self.last_check.isoformat(),
            "status": "healthy" if self.is_healthy else "unhealthy",
            "uptime_seconds": int(psutil.boot_time()),
            "error_count": self.error_count
        }
        
        return results
    
    async def notify_admin(self, status: Dict[str, Any]):
        """
        Отправка уведомления администратору
        
        :param status: Результаты проверки
        """
        if not self.admin_id:
            return
        
        try:
            # Формируем сообщение
            message_lines = [
                "🔴 Проблемы с работой бота:",
                "",
                f"⏰ Время проверки: {status['meta']['timestamp']}"
            ]
            
            for component, result in status.items():
                if component != "meta" and result["status"] == "unhealthy":
                    message_lines.extend([
                        "",
                        f"❌ {component}:",
                        f"Ошибка: {result.get('error', 'Неизвестная ошибка')}"
                    ])
            
            await self.bot.send_message(
                self.admin_id,
                "\n".join(message_lines)
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору: {e}")
    
    async def start_monitoring(self):
        """Запуск периодической проверки состояния"""
        while True:
            try:
                status = await self.check()
                
                # Логируем результаты
                log_level = logging.WARNING if not self.is_healthy else logging.INFO
                logger.log(log_level, f"Состояние системы: {status['meta']['status']}")
                
                # Отправляем уведомление при необходимости
                if self.error_count >= self.alert_threshold:
                    await self.notify_admin(status)
            except Exception as e:
                logger.error(f"Ошибка при проверке состояния: {e}")
            
            await asyncio.sleep(self.check_interval) 