import os
import logging
from datetime import datetime
import aiohttp
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class TimeZoneDB:
    """Класс для работы с TimeZoneDB API"""
    
    def __init__(self):
        """Инициализация клиента TimeZoneDB"""
        self.api_key = os.getenv("TIMEZONE_DB_API_KEY")
        if not self.api_key:
            raise ValueError("Не задан TIMEZONE_DB_API_KEY в переменных окружения")
        
        self.base_url = "http://api.timezonedb.com/v2.1"
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
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
    
    async def get_time_zone(self, lat: float, lng: float) -> Optional[Dict]:
        """
        Получение информации о часовом поясе по координатам
        
        :param lat: Широта
        :param lng: Долгота
        :return: Информация о часовом поясе или None в случае ошибки
        """
        params = {
            "lat": lat,
            "lng": lng,
            "by": "position"
        }
        
        result = await self._make_request("get-time-zone", params)
        if result and result.get("status") == "OK":
            return {
                "timezone": result.get("zoneName"),
                "offset": result.get("gmtOffset"),
                "formatted": f"UTC{'+' if result.get('gmtOffset', 0) >= 0 else ''}{result.get('gmtOffset', 0) // 3600}"
            }
        return None
    
    async def get_time_zone_by_zone(self, zone: str) -> Optional[Dict]:
        """
        Получение информации о часовом поясе по названию зоны
        
        :param zone: Название зоны (например, "Europe/Moscow")
        :return: Информация о часовом поясе или None в случае ошибки
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
    
    async def convert_time(self, time: datetime, from_zone: str, to_zone: str) -> Optional[datetime]:
        """
        Конвертация времени между часовыми поясами
        
        :param time: Время для конвертации
        :param from_zone: Исходный часовой пояс
        :param to_zone: Целевой часовой пояс
        :return: Сконвертированное время или None в случае ошибки
        """
        # Получаем информацию об исходном часовом поясе
        from_tz = await self.get_time_zone_by_zone(from_zone)
        if not from_tz:
            return None
        
        # Получаем информацию о целевом часовом поясе
        to_tz = await self.get_time_zone_by_zone(to_zone)
        if not to_tz:
            return None
        
        # Вычисляем разницу в секундах
        offset_diff = to_tz["offset"] - from_tz["offset"]
        
        # Применяем смещение
        return time + offset_diff

# Создаем глобальный экземпляр клиента
timezone_db = TimeZoneDB() 