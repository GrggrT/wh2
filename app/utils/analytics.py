import os
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from io import BytesIO
from tortoise.functions import Count, Sum
from app.db.models import User, Workplace, Record
from app.utils.profiler import profiler

logger = logging.getLogger(__name__)

class Analytics:
    """Класс для аналитики и визуализации данных"""
    
    def __init__(self):
        """Инициализация аналитики"""
        self.cache_dir = Path("cache/analytics")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Настройки кэширования
        self.cache_ttl = 3600  # 1 час
        self.cached_data = {}
        
        # Настройки визуализации
        plt.style.use('seaborn')
        sns.set_palette("husl")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Проверка валидности кэша
        
        :param cache_key: Ключ кэша
        :return: True если кэш валиден
        """
        if cache_key not in self.cached_data:
            return False
        
        cache_time = self.cached_data[cache_key]["timestamp"]
        return (datetime.now() - cache_time).total_seconds() < self.cache_ttl
    
    def _get_cached_data(self, cache_key: str) -> Optional[Any]:
        """
        Получение данных из кэша
        
        :param cache_key: Ключ кэша
        :return: Данные или None
        """
        if self._is_cache_valid(cache_key):
            return self.cached_data[cache_key]["data"]
        return None
    
    def _set_cached_data(self, cache_key: str, data: Any):
        """
        Сохранение данных в кэш
        
        :param cache_key: Ключ кэша
        :param data: Данные для кэширования
        """
        self.cached_data[cache_key] = {
            "data": data,
            "timestamp": datetime.now()
        }
    
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
            
            # Получаем общую статистику
            total_users = await User.all().count()
            active_users = await User.filter(
                records__start_time__gte=start_date
            ).distinct().count()
            
            total_records = await Record.filter(
                start_time__gte=start_date
            ).count()
            
            # Вычисляем среднюю продолжительность работы
            records = await Record.filter(
                start_time__gte=start_date,
                end_time__isnull=False
            ).all()
            
            total_duration = timedelta()
            for record in records:
                total_duration += record.end_time - record.start_time
            
            avg_duration = (
                total_duration.total_seconds() / len(records) / 3600
                if records else 0
            )
            
            # Вычисляем активность
            activity_rate = (active_users / total_users * 100) if total_users else 0
            
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
            
            # Получаем статистику по рабочим местам
            workplaces = await Workplace.all().prefetch_related('records')
            workplace_stats = []
            
            for workplace in workplaces:
                records = [
                    r for r in workplace.records
                    if r.start_time >= start_date and r.end_time
                ]
                
                if not records:
                    continue
                
                total_duration = timedelta()
                total_earnings = 0
                
                for record in records:
                    duration = record.end_time - record.start_time
                    total_duration += duration
                    total_earnings += (
                        duration.total_seconds() / 3600 * float(workplace.rate)
                    )
                
                workplace_stats.append({
                    "name": workplace.name,
                    "records_count": len(records),
                    "total_hours": round(total_duration.total_seconds() / 3600, 2),
                    "total_earnings": round(total_earnings, 2),
                    "avg_daily_hours": round(
                        total_duration.total_seconds() / 3600 / days, 2
                    )
                })
            
            # Сортируем по заработку
            workplace_stats.sort(key=lambda x: x["total_earnings"], reverse=True)
            
            stats = {
                "workplaces": workplace_stats,
                "total_workplaces": len(workplace_stats),
                "most_used": workplace_stats[0] if workplace_stats else None,
                "most_profitable": workplace_stats[0] if workplace_stats else None
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
            
            # Получаем данные по дням
            records = await Record.filter(
                start_time__gte=start_date
            ).all()
            
            # Группируем по дням
            daily_stats = {}
            for record in records:
                day = record.start_time.date()
                if day not in daily_stats:
                    daily_stats[day] = {
                        "count": 0,
                        "hours": 0
                    }
                
                daily_stats[day]["count"] += 1
                if record.end_time:
                    duration = (record.end_time - record.start_time).total_seconds() / 3600
                    daily_stats[day]["hours"] += duration
            
            # Создаем график
            plt.figure(figsize=(12, 6))
            dates = sorted(daily_stats.keys())
            counts = [daily_stats[d]["count"] for d in dates]
            hours = [daily_stats[d]["hours"] for d in dates]
            
            plt.subplot(2, 1, 1)
            plt.plot(dates, counts, marker='o')
            plt.title("Количество записей по дням")
            plt.xticks(rotation=45)
            plt.grid(True)
            
            plt.subplot(2, 1, 2)
            plt.plot(dates, hours, marker='o', color='green')
            plt.title("Часы работы по дням")
            plt.xticks(rotation=45)
            plt.grid(True)
            
            plt.tight_layout()
            
            # Сохраняем график
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=300)
            plt.close()
            
            return buffer.getvalue()
        
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
            
            # Получаем данные
            records = await Record.filter(
                start_time__gte=start_date,
                end_time__isnull=False
            ).all()
            
            # Создаем матрицу для тепловой карты
            hours = 24
            days_of_week = 7
            heatmap_data = np.zeros((days_of_week, hours))
            
            for record in records:
                day = record.start_time.weekday()
                hour = record.start_time.hour
                duration = (record.end_time - record.start_time).total_seconds() / 3600
                heatmap_data[day][hour] += duration
            
            # Создаем тепловую карту
            plt.figure(figsize=(12, 8))
            sns.heatmap(
                heatmap_data,
                cmap='YlOrRd',
                xticklabels=range(24),
                yticklabels=['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            )
            
            plt.title("Тепловая карта активности")
            plt.xlabel("Час")
            plt.ylabel("День недели")
            
            # Сохраняем карту
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=300)
            plt.close()
            
            return buffer.getvalue()
        
        except Exception as e:
            logger.error(f"Ошибка при генерации тепловой карты: {e}")
            return None
    
    @profiler.profile(name="get_efficiency_metrics")
    async def get_efficiency_metrics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Получение метрик эффективности
        
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
            daily_hours = {}
            
            for record in records:
                duration = record.end_time - record.start_time
                total_duration += duration
                
                earnings = (
                    duration.total_seconds() / 3600 * float(record.workplace.rate)
                )
                total_earnings += earnings
                
                day = record.start_time.date()
                if day not in daily_hours:
                    daily_hours[day] = 0
                daily_hours[day] += duration.total_seconds() / 3600
            
            total_hours = total_duration.total_seconds() / 3600
            avg_daily_hours = total_hours / len(daily_hours) if daily_hours else 0
            
            # Вычисляем эффективность
            efficiency_score = min(100, (avg_daily_hours / 8) * 100)
            
            # Формируем рекомендации
            if efficiency_score < 50:
                recommendation = (
                    "Рекомендуется увеличить количество рабочих часов "
                    "для повышения эффективности"
                )
            elif efficiency_score < 80:
                recommendation = (
                    "Хороший результат! Для улучшения попробуйте "
                    "оптимизировать распределение времени"
                )
            else:
                recommendation = (
                    "Отличный результат! Продолжайте поддерживать "
                    "текущий уровень эффективности"
                )
            
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