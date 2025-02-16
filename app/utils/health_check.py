import logging
import asyncio
from datetime import datetime
from tortoise import Tortoise
from aiogram import Bot

logger = logging.getLogger(__name__)

async def check_database():
    """
    Проверка подключения к базе данных
    
    :return: True если подключение активно, False в противном случае
    """
    try:
        conn = Tortoise.get_connection("default")
        await conn.execute_query("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке базы данных: {e}")
        return False

async def check_bot(bot: Bot):
    """
    Проверка подключения к Telegram API
    
    :param bot: Экземпляр бота
    :return: True если подключение активно, False в противном случае
    """
    try:
        me = await bot.get_me()
        return bool(me and me.is_bot)
    except Exception as e:
        logger.error(f"Ошибка при проверке бота: {e}")
        return False

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
    
    async def check(self):
        """
        Проверка состояния всех компонентов
        
        :return: Словарь с результатами проверки
        """
        self.last_check = datetime.now()
        
        # Проверяем компоненты
        db_status = await check_database()
        bot_status = await check_bot(self.bot)
        
        # Общий статус
        self.is_healthy = all([db_status, bot_status])
        
        return {
            "status": "healthy" if self.is_healthy else "unhealthy",
            "timestamp": self.last_check.isoformat(),
            "components": {
                "database": {
                    "status": "up" if db_status else "down"
                },
                "telegram_api": {
                    "status": "up" if bot_status else "down"
                }
            }
        }
    
    async def start_monitoring(self, interval: int = 60):
        """
        Запуск периодической проверки состояния
        
        :param interval: Интервал проверки в секундах
        """
        while True:
            try:
                status = await self.check()
                if not self.is_healthy:
                    logger.warning(f"Нездоровое состояние приложения: {status}")
            except Exception as e:
                logger.error(f"Ошибка при проверке состояния: {e}")
            
            await asyncio.sleep(interval) 