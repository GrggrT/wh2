import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from io import BytesIO
from tortoise.functions import Count, Avg, Sum
from app.db.models import User, Workplace, Record
from app.utils.profiler import profiler

logger = logging.getLogger(__name__)

class Analytics:
    """Класс для сбора и анализа статистики"""
    
    def __init__(self):
        """Инициализация аналитики"""
        self.cache_timeout = timedelta(minutes=5)
        self.cached_data: Dict[str, Tuple[datetime, Any]] = {}
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Проверка актуальности кэша
        
        :param cache_key: Ключ кэша
        :return: True если кэш актуален
        """
        if cache_key not in self.cached_data:
            return False
        cache_time, _ = self.cached_data[cache_key]
        return datetime.now() - cache_time < self.cache_timeout
    
    def _get_cached_data(self, cache_key: str) -> Optional[Any]:
        """
        Получение данных из кэша
        
        :param cache_key: Ключ кэша
        :return: Данные из кэша или None
        """
        if self._is_cache_valid(cache_key):
            return self.cached_data[cache_key][1]
        return None
    
    def _set_cached_data(self, cache_key: str, data: Any):
        """
        Сохранение данных в кэш
        
        :param cache_key: Ключ кэша
        :param data: Данные для кэширования
        """
        self.cached_data[cache_key] = (datetime.now(), data)
    
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
            
            # Общая статистика пользователей
            total_users = await User.all().count()
            active_users = await User.filter(
                records__start_time__gte=start_date
            ).distinct().count()
            
            # Статистика по записям
            total_records = await Record.filter(
                start_time__gte=start_date
            ).count()
            
            # Среднее время работы
            records = await Record.filter(
                start_time__gte=start_date,
                end_time__isnull=False
            ).all()
            
            total_duration = timedelta()
            for record in records:
                total_duration += record.end_time - record.start_time
            
            avg_duration = (
                total_duration.total_seconds() / len(records)
                if records else 0
            ) / 3600  # в часах
            
            stats = {
                "total_users": total_users,
                "active_users": active_users,
                "total_records": total_records,
                "avg_work_duration": round(avg_duration, 2),
                "activity_rate": round(active_users / total_users * 100 if total_users else 0, 2)
            }
            
            self._set_cached_data(cache_key, stats)
            return stats
        
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователей: {e}")
            return {}
    
    @profiler.profile(name="get_workplace_statistics")
    async def get_workplace_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Получение статистики по рабочим местам
        
        :param days: Количество дней для анализа
        :return: Словарь со статистикой
        """
        cache_key = f"workplace_stats_{days}"
        cached = self._get_cached_data(cache_key)
        if cached:
            return cached
        
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            # Статистика по рабочим местам
            workplaces = await Workplace.all().prefetch_related('records')
            workplace_stats = []
            
            for workplace in workplaces:
                records = [r for r in workplace.records if r.start_time >= start_date]
                total_duration = timedelta()
                total_earnings = 0
                
                for record in records:
                    if record.end_time:
                        duration = record.end_time - record.start_time
                        total_duration += duration
                        total_earnings += duration.total_seconds() / 3600 * float(workplace.rate)
                
                workplace_stats.append({
                    "name": workplace.name,
                    "records_count": len(records),
                    "total_hours": round(total_duration.total_seconds() / 3600, 2),
                    "total_earnings": round(total_earnings, 2),
                    "avg_daily_hours": round(
                        total_duration.total_seconds() / 3600 / days, 2
                    )
                })
            
            stats = {
                "workplaces": workplace_stats,
                "total_workplaces": len(workplaces),
                "most_used": max(
                    workplace_stats,
                    key=lambda x: x["records_count"]
                ) if workplace_stats else None,
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
        :return: График в формате PNG или None в случае ошибки
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем все записи за период
            records = await Record.filter(
                start_time__gte=start_date
            ).prefetch_related('workplace')
            
            # Подготавливаем данные для графика
            dates = []
            hours = []
            
            current_date = start_date
            while current_date <= datetime.now():
                day_records = [
                    r for r in records
                    if r.start_time.date() == current_date.date() and r.end_time
                ]
                
                total_hours = sum(
                    (r.end_time - r.start_time).total_seconds() / 3600
                    for r in day_records
                )
                
                dates.append(current_date.date())
                hours.append(total_hours)
                
                current_date += timedelta(days=1)
            
            # Создаем график
            plt.figure(figsize=(12, 6))
            plt.plot(dates, hours, marker='o')
            plt.title('Активность пользователей')
            plt.xlabel('Дата')
            plt.ylabel('Часы работы')
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
        :return: Тепловая карта в формате PNG или None в случае ошибки
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем все записи за период
            records = await Record.filter(
                start_time__gte=start_date,
                end_time__isnull=False
            ).all()
            
            # Создаем матрицу активности (7 дней x 24 часа)
            activity_matrix = np.zeros((7, 24))
            
            for record in records:
                current_time = record.start_time
                end_time = record.end_time
                
                while current_time < end_time:
                    day_of_week = current_time.weekday()
                    hour = current_time.hour
                    activity_matrix[day_of_week][hour] += 1
                    current_time += timedelta(hours=1)
            
            # Создаем тепловую карту
            plt.figure(figsize=(15, 7))
            sns.heatmap(
                activity_matrix,
                cmap='YlOrRd',
                xticklabels=range(24),
                yticklabels=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
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
            
            # Получаем записи пользователя
            records = await Record.filter(
                user_id=user_id,
                start_time__gte=start_date,
                end_time__isnull=False
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
            daily_hours = defaultdict(float)
            
            for record in records:
                duration = record.end_time - record.start_time
                total_duration += duration
                total_earnings += duration.total_seconds() / 3600 * float(record.workplace.rate)
                daily_hours[record.start_time.date()] += duration.total_seconds() / 3600
            
            avg_daily_hours = sum(daily_hours.values()) / len(daily_hours)
            
            # Вычисляем эффективность (0-100)
            efficiency_score = min(100, (
                (avg_daily_hours / 8) * 70 +  # Оптимальная длительность
                (len(daily_hours) / days) * 30  # Регулярность
            ))
            
            # Формируем рекомендации
            if efficiency_score < 50:
                recommendation = "Рекомендуется увеличить регулярность работы"
            elif avg_daily_hours > 10:
                recommendation = "Рекомендуется сократить длительность рабочего дня"
            elif avg_daily_hours < 4:
                recommendation = "Рекомендуется увеличить длительность рабочего дня"
            else:
                recommendation = "Оптимальный режим работы"
            
            return {
                "total_hours": round(total_duration.total_seconds() / 3600, 2),
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