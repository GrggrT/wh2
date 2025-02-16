import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from io import BytesIO
from app.db.models import User, Workplace, Record
from app.utils.profiler import profiler

logger = logging.getLogger(__name__)

class Analytics:
    """Класс для анализа и визуализации данных"""
    
    def __init__(self):
        """Инициализация аналитики"""
        self.cached_data = {}
        self.cache_ttl = 300  # Время жизни кэша в секундах
        self.cache_last_update = {}
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Проверка валидности кэша
        
        :param cache_key: Ключ кэша
        :return: True если кэш валиден
        """
        if cache_key not in self.cache_last_update:
            return False
        
        return (datetime.now() - self.cache_last_update[cache_key]).total_seconds() < self.cache_ttl
    
    def _get_cached_data(self, cache_key: str) -> Optional[Any]:
        """
        Получение данных из кэша
        
        :param cache_key: Ключ кэша
        :return: Данные из кэша или None
        """
        if self._is_cache_valid(cache_key):
            return self.cached_data.get(cache_key)
        return None
    
    def _set_cached_data(self, cache_key: str, data: Any):
        """
        Сохранение данных в кэш
        
        :param cache_key: Ключ кэша
        :param data: Данные для кэширования
        """
        self.cached_data[cache_key] = data
        self.cache_last_update[cache_key] = datetime.now()
    
    @profiler.profile(name="get_user_statistics")
    async def get_user_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Получение статистики пользователей
        
        :param days: Количество дней для анализа
        :return: Словарь со статистикой
        """
        cache_key = f"user_stats_{days}"
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached
        
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем общее количество пользователей
            total_users = await User.all().count()
            
            # Получаем активных пользователей
            active_users = await User.filter(
                records__start_time__gte=start_date
            ).distinct().count()
            
            # Получаем все записи за период
            records = await Record.filter(
                start_time__gte=start_date
            ).prefetch_related('user', 'workplace')
            
            # Вычисляем статистику
            total_duration = timedelta()
            total_records = len(records)
            
            for record in records:
                if record.end_time:
                    total_duration += record.end_time - record.start_time
            
            avg_duration = (
                total_duration.total_seconds() / total_records / 3600
                if total_records > 0 else 0
            )
            
            activity_rate = (active_users / total_users * 100) if total_users > 0 else 0
            
            stats = {
                "total_users": total_users,
                "active_users": active_users,
                "total_records": total_records,
                "avg_work_duration": round(avg_duration, 2),
                "activity_rate": round(activity_rate, 2)
            }
            
            self._set_cached_data(cache_key, stats)
            return stats
        
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователей: {e}")
            return {}
    
    @profiler.profile(name="get_workplace_statistics")
    async def get_workplace_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Получение статистики рабочих мест
        
        :param days: Количество дней для анализа
        :return: Словарь со статистикой
        """
        cache_key = f"workplace_stats_{days}"
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached
        
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем все рабочие места с записями
            workplaces = await Workplace.all().prefetch_related('records')
            workplace_stats = []
            
            for workplace in workplaces:
                records = [
                    r for r in workplace.records
                    if r.start_time >= start_date and r.end_time
                ]
                
                if records:
                    total_duration = sum(
                        (r.end_time - r.start_time).total_seconds() / 3600
                        for r in records
                    )
                    total_earnings = total_duration * float(workplace.rate)
                    
                    workplace_stats.append({
                        "name": workplace.name,
                        "records_count": len(records),
                        "total_hours": round(total_duration, 2),
                        "total_earnings": round(total_earnings, 2),
                        "avg_daily_hours": round(total_duration / days, 2)
                    })
            
            # Сортируем по количеству записей
            workplace_stats.sort(key=lambda x: x["records_count"], reverse=True)
            
            stats = {
                "workplaces": workplace_stats,
                "total_workplaces": len(workplaces),
                "most_used": workplace_stats[0] if workplace_stats else None,
                "most_profitable": max(
                    workplace_stats,
                    key=lambda x: x["total_earnings"]
                ) if workplace_stats else None
            }
            
            self._set_cached_data(cache_key, stats)
            return stats
        
        except Exception as e:
            logger.error(f"Ошибка при получении статистики рабочих мест: {e}")
            return {}
    
    @profiler.profile(name="generate_activity_chart")
    async def generate_activity_chart(self, days: int = 30) -> Optional[bytes]:
        """
        Генерация графика активности
        
        :param days: Количество дней для анализа
        :return: График в формате PNG или None
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем все записи за период
            records = await Record.filter(
                start_time__gte=start_date
            ).prefetch_related('workplace')
            
            # Группируем данные по дням
            daily_hours = {}
            
            for record in records:
                if record.end_time:
                    day = record.start_time.date()
                    duration = (record.end_time - record.start_time).total_seconds() / 3600
                    daily_hours[day] = daily_hours.get(day, 0) + duration
            
            # Создаем график
            plt.figure(figsize=(12, 6))
            dates = sorted(daily_hours.keys())
            hours = [daily_hours[date] for date in dates]
            
            plt.plot(dates, hours, marker='o')
            plt.title('Активность по дням')
            plt.xlabel('Дата')
            plt.ylabel('Часы')
            plt.grid(True)
            plt.xticks(rotation=45)
            
            # Сохраняем график в буфер
            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close()
            
            return buf.getvalue()
        
        except Exception as e:
            logger.error(f"Ошибка при генерации графика активности: {e}")
            return None
    
    @profiler.profile(name="generate_heatmap")
    async def generate_heatmap(self, days: int = 30) -> Optional[bytes]:
        """
        Генерация тепловой карты активности
        
        :param days: Количество дней для анализа
        :return: Тепловая карта в формате PNG или None
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем все записи за период
            records = await Record.filter(
                start_time__gte=start_date
            ).prefetch_related('workplace')
            
            # Создаем матрицу для тепловой карты
            hours = range(24)
            weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            activity_matrix = np.zeros((7, 24))
            
            for record in records:
                if record.end_time:
                    weekday = record.start_time.weekday()
                    hour = record.start_time.hour
                    duration = (record.end_time - record.start_time).total_seconds() / 3600
                    activity_matrix[weekday][hour] += duration
            
            # Создаем тепловую карту
            plt.figure(figsize=(15, 8))
            sns.heatmap(
                activity_matrix,
                xticklabels=hours,
                yticklabels=weekdays,
                cmap='YlOrRd',
                annot=True,
                fmt='.1f'
            )
            
            plt.title('Тепловая карта активности')
            plt.xlabel('Час')
            plt.ylabel('День недели')
            
            # Сохраняем карту в буфер
            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close()
            
            return buf.getvalue()
        
        except Exception as e:
            logger.error(f"Ошибка при генерации тепловой карты: {e}")
            return None
    
    @profiler.profile(name="get_efficiency_metrics")
    async def get_efficiency_metrics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Получение метрик эффективности для пользователя
        
        :param user_id: ID пользователя
        :param days: Количество дней для анализа
        :return: Словарь с метриками
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем пользователя и его записи
            user = await User.get(telegram_id=user_id)
            records = await Record.filter(
                user=user,
                start_time__gte=start_date
            ).prefetch_related('workplace')
            
            if not records:
                return {
                    "total_hours": 0,
                    "total_earnings": 0,
                    "avg_daily_hours": 0,
                    "efficiency_score": 0,
                    "recommendation": "Недостаточно данных для анализа"
                }
            
            # Вычисляем метрики
            total_duration = timedelta()
            total_earnings = 0
            
            for record in records:
                if record.end_time:
                    duration = record.end_time - record.start_time
                    total_duration += duration
                    total_earnings += (
                        duration.total_seconds() / 3600 * float(record.workplace.rate)
                    )
            
            total_hours = total_duration.total_seconds() / 3600
            avg_daily_hours = total_hours / days
            
            # Вычисляем эффективность
            efficiency_score = min(100, (avg_daily_hours / 8) * 100)
            
            # Формируем рекомендации
            if efficiency_score < 50:
                recommendation = "Рекомендуется увеличить количество рабочих часов"
            elif efficiency_score < 80:
                recommendation = "Хороший результат, есть потенциал для роста"
            else:
                recommendation = "Отличная эффективность! Поддерживайте текущий темп"
            
            return {
                "total_hours": round(total_hours, 2),
                "total_earnings": round(total_earnings, 2),
                "avg_daily_hours": round(avg_daily_hours, 2),
                "efficiency_score": round(efficiency_score, 2),
                "recommendation": recommendation
            }
        
        except Exception as e:
            logger.error(f"Ошибка при получении метрик эффективности: {e}")
            return {}

# Создаем глобальный экземпляр аналитики
analytics = Analytics() 