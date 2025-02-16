import os
import time
import logging
import functools
import cProfile
import pstats
import asyncio
from typing import Optional, Callable, Any, Dict
from datetime import datetime
from tortoise import Tortoise
from collections import defaultdict

logger = logging.getLogger(__name__)

class Profiler:
    """Класс для профилирования производительности"""
    
    def __init__(self):
        """Инициализация профилировщика"""
        self.stats_dir = "profiling"
        os.makedirs(self.stats_dir, exist_ok=True)
        
        # Статистика выполнения
        self.execution_times: Dict[str, list] = defaultdict(list)
        self.db_queries: Dict[str, int] = defaultdict(int)
        
        # Настройки
        self.enabled = os.getenv("ENABLE_PROFILING", "false").lower() == "true"
        self.slow_threshold = float(os.getenv("SLOW_THRESHOLD", "1.0"))  # секунды
    
    def profile(self, func: Optional[Callable] = None, *, name: Optional[str] = None):
        """
        Декоратор для профилирования функций
        
        :param func: Функция для профилирования
        :param name: Имя для профиля (если не указано, используется имя функции)
        :return: Обернутая функция
        """
        def decorator(fn):
            if not self.enabled:
                return fn
            
            profile_name = name or fn.__name__
            
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                profiler = cProfile.Profile()
                
                try:
                    # Запускаем профилировщик
                    profiler.enable()
                    result = await fn(*args, **kwargs)
                    profiler.disable()
                    
                    # Сохраняем статистику
                    execution_time = time.time() - start_time
                    self.execution_times[profile_name].append(execution_time)
                    
                    # Проверяем медленные операции
                    if execution_time > self.slow_threshold:
                        logger.warning(
                            f"Медленная операция: {profile_name} "
                            f"выполнялась {execution_time:.2f} секунд"
                        )
                    
                    # Сохраняем профиль
                    stats_file = os.path.join(
                        self.stats_dir,
                        f"{profile_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.prof"
                    )
                    profiler.dump_stats(stats_file)
                    
                    # Анализируем статистику
                    with open(f"{stats_file}.txt", "w") as f:
                        stats = pstats.Stats(profiler, stream=f)
                        stats.sort_stats("cumulative")
                        stats.print_stats()
                    
                    return result
                
                except Exception as e:
                    logger.error(f"Ошибка при профилировании {profile_name}: {e}")
                    raise
            
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                profiler = cProfile.Profile()
                
                try:
                    # Запускаем профилировщик
                    profiler.enable()
                    result = fn(*args, **kwargs)
                    profiler.disable()
                    
                    # Сохраняем статистику
                    execution_time = time.time() - start_time
                    self.execution_times[profile_name].append(execution_time)
                    
                    # Проверяем медленные операции
                    if execution_time > self.slow_threshold:
                        logger.warning(
                            f"Медленная операция: {profile_name} "
                            f"выполнялась {execution_time:.2f} секунд"
                        )
                    
                    # Сохраняем профиль
                    stats_file = os.path.join(
                        self.stats_dir,
                        f"{profile_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.prof"
                    )
                    profiler.dump_stats(stats_file)
                    
                    # Анализируем статистику
                    with open(f"{stats_file}.txt", "w") as f:
                        stats = pstats.Stats(profiler, stream=f)
                        stats.sort_stats("cumulative")
                        stats.print_stats()
                    
                    return result
                
                except Exception as e:
                    logger.error(f"Ошибка при профилировании {profile_name}: {e}")
                    raise
            
            return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper
        
        return decorator(func) if func else decorator
    
    def track_db_query(self, query_type: str):
        """
        Отслеживание запросов к базе данных
        
        :param query_type: Тип запроса (SELECT, INSERT, UPDATE, DELETE)
        """
        if not self.enabled:
            return
        
        self.db_queries[query_type] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики профилирования
        
        :return: Словарь со статистикой
        """
        stats = {
            "execution_times": {},
            "db_queries": dict(self.db_queries),
            "total_db_queries": sum(self.db_queries.values())
        }
        
        # Вычисляем статистику времени выполнения
        for name, times in self.execution_times.items():
            if times:
                stats["execution_times"][name] = {
                    "min": min(times),
                    "max": max(times),
                    "avg": sum(times) / len(times),
                    "count": len(times)
                }
        
        return stats
    
    def reset_stats(self):
        """Сброс статистики"""
        self.execution_times.clear()
        self.db_queries.clear()
    
    def analyze_slow_queries(self) -> Dict[str, Any]:
        """
        Анализ медленных запросов
        
        :return: Словарь с результатами анализа
        """
        slow_queries = {}
        
        for name, times in self.execution_times.items():
            slow_times = [t for t in times if t > self.slow_threshold]
            if slow_times:
                slow_queries[name] = {
                    "count": len(slow_times),
                    "avg_time": sum(slow_times) / len(slow_times),
                    "max_time": max(slow_times)
                }
        
        return slow_queries
    
    async def analyze_db_performance(self) -> Dict[str, Any]:
        """
        Анализ производительности базы данных
        
        :return: Словарь с результатами анализа
        """
        try:
            conn = Tortoise.get_connection("default")
            
            # Анализ индексов
            index_stats = await conn.execute_query("""
                SELECT 
                    schemaname, tablename, indexname, 
                    idx_scan, idx_tup_read, idx_tup_fetch
                FROM pg_stat_user_indexes
                ORDER BY idx_scan DESC
            """)
            
            # Анализ таблиц
            table_stats = await conn.execute_query("""
                SELECT 
                    schemaname, relname, seq_scan, seq_tup_read,
                    n_live_tup, n_dead_tup
                FROM pg_stat_user_tables
                ORDER BY seq_scan DESC
            """)
            
            return {
                "indexes": index_stats,
                "tables": table_stats,
                "recommendations": self._generate_db_recommendations(index_stats, table_stats)
            }
        
        except Exception as e:
            logger.error(f"Ошибка при анализе производительности БД: {e}")
            return {}
    
    def _generate_db_recommendations(self, index_stats, table_stats) -> list:
        """
        Генерация рекомендаций по оптимизации БД
        
        :param index_stats: Статистика индексов
        :param table_stats: Статистика таблиц
        :return: Список рекомендаций
        """
        recommendations = []
        
        # Анализ неиспользуемых индексов
        for schema, table, index, scans, *_ in index_stats:
            if scans == 0:
                recommendations.append(
                    f"Неиспользуемый индекс: {schema}.{table}.{index}"
                )
        
        # Анализ таблиц без индексов
        for schema, table, seq_scans, *_, dead_tuples in table_stats:
            if seq_scans > 100:  # Много последовательных сканирований
                recommendations.append(
                    f"Возможно нужен индекс: {schema}.{table} "
                    f"(последовательных сканирований: {seq_scans})"
                )
            
            if dead_tuples > 1000:  # Много мертвых строк
                recommendations.append(
                    f"Требуется VACUUM: {schema}.{table} "
                    f"(мертвых строк: {dead_tuples})"
                )
        
        return recommendations

# Создаем глобальный экземпляр профилировщика
profiler = Profiler() 