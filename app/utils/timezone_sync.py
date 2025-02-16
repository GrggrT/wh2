import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import aiohttp
from app.db.models import User

logger = logging.getLogger(__name__)

class TimeZoneSync:
    """Класс для синхронизации часовых поясов"""
    
    def __init__(self):
        """Инициализация синхронизатора"""
        self.api_key = os.getenv("TIMEZONE_DB_API_KEY")
        if not self.api_key:
            raise ValueError("Не задан TIMEZONE_DB_API_KEY в переменных окружения")
        
        self.base_url = "http://api.timezonedb.com/v2.1"
        self.sync_interval = timedelta(hours=24)  # Синхронизация раз в сутки
        self.last_sync: Dict[int, datetime] = {}  # Время последней синхронизации для каждого пользователя
    
    async def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """
        Выполнение запроса к API
        
        :param endpoint: Конечная точка API
        :param params: Параметры запроса
        :return: Результат запроса или None в случае ошибки
        """
        params["key"] = self.api_key
        params["format"] = "json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/{endpoint}", params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Ошибка API TimeZoneDB: {response.status} - {await response.text()}")
                        return None
        except Exception as e:
            logger.error(f"Ошибка при запросе к TimeZoneDB: {e}")
            return None
    
    async def get_timezone_info(self, zone: str) -> Optional[Dict]:
        """
        Получение информации о часовом поясе
        
        :param zone: Название часового пояса
        :return: Информация о часовом поясе или None
        """
        params = {
            "zone": zone,
            "by": "zone"
        }
        
        result = await self._make_request("get-time-zone", params)
        if result and result.get("status") == "OK":
            return {
                "timezone": result.get("zoneName"),
                "offset": result.get("gmtOffset"),
                "formatted": f"UTC{'+' if result.get('gmtOffset', 0) >= 0 else ''}{result.get('gmtOffset', 0) // 3600}"
            }
        return None
    
    async def sync_user_timezone(self, user: User) -> bool:
        """
        Синхронизация часового пояса пользователя
        
        :param user: Объект пользователя
        :return: True если синхронизация успешна, False в противном случае
        """
        # Проверяем, нужна ли синхронизация
        if user.telegram_id in self.last_sync:
            last_sync_time = self.last_sync[user.telegram_id]
            if datetime.now() - last_sync_time < self.sync_interval:
                return True
        
        try:
            # Получаем информацию о часовом поясе
            timezone_info = await self.get_timezone_info(user.timezone)
            if not timezone_info:
                return False
            
            # Обновляем информацию о пользователе
            user.timezone = timezone_info["timezone"]
            await user.save()
            
            # Обновляем время последней синхронизации
            self.last_sync[user.telegram_id] = datetime.now()
            
            logger.info(f"Синхронизирован часовой пояс для пользователя {user.telegram_id}: {timezone_info['timezone']}")
            return True
        
        except Exception as e:
            logger.error(f"Ошибка при синхронизации часового пояса пользователя {user.telegram_id}: {e}")
            return False
    
    async def sync_all_users(self) -> Dict[str, List[int]]:
        """
        Синхронизация часовых поясов всех пользователей
        
        :return: Словарь с результатами синхронизации
        """
        results = {
            "success": [],
            "failed": []
        }
        
        try:
            users = await User.all()
            for user in users:
                success = await self.sync_user_timezone(user)
                if success:
                    results["success"].append(user.telegram_id)
                else:
                    results["failed"].append(user.telegram_id)
            
            logger.info(
                f"Завершена синхронизация часовых поясов. "
                f"Успешно: {len(results['success'])}, "
                f"Ошибок: {len(results['failed'])}"
            )
        
        except Exception as e:
            logger.error(f"Ошибка при массовой синхронизации часовых поясов: {e}")
        
        return results
    
    async def start_periodic_sync(self):
        """Запуск периодической синхронизации"""
        while True:
            try:
                await self.sync_all_users()
            except Exception as e:
                logger.error(f"Ошибка в процессе периодической синхронизации: {e}")
            
            await asyncio.sleep(self.sync_interval.total_seconds())

# Создаем глобальный экземпляр синхронизатора
timezone_sync = TimeZoneSync() 