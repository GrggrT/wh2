import logging
import time
import asyncio
import psutil
import gc
from typing import Dict, List, Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
from tortoise import Tortoise
from app.utils.profiler import profiler

logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    """Класс для оптимизации производительности"""
    
    def __init__(self):
        """Инициализация оптимизатора"""
        self.memory_threshold = 85  # Порог использования памяти (%)
        self.cpu_threshold = 80     # Порог использования CPU (%)
        self.db_query_threshold = 1.0  # Порог времени выполнения запроса (сек)
        self.cache_size_limit = 1000   # Максимальный размер кэша
        self.optimization_interval = 300  # Интервал оптимизации (сек)
        
        # Статистика
        self.slow_queries: List[Dict[str, Any]] = []
        self.memory_usage: List[Dict[str, Any]] = []
        self.cpu_usage: List[Dict[str, Any]] = []
        self.cache_hits = 0
        self.cache_misses = 0
    
    async def optimize_db_queries(self) -> Dict[str, Any]:
        """
        Оптимизация запросов к базе данных
        
        :return: Результаты оптимизации
        """
        try:
            conn = Tortoise.get_connection("default")
            
            # Анализ индексов
            index_stats = await conn.execute_query("""
                SELECT 
                    schemaname, tablename, indexname, 
                    idx_scan, idx_tup_read, idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE idx_scan = 0
                ORDER BY idx_tup_read DESC
            """)
            
            # Анализ медленных запросов
            slow_query_stats = await conn.execute_query("""
                SELECT query, calls, total_time, mean_time
                FROM pg_stat_statements
                WHERE mean_time > %s
                ORDER BY mean_time DESC
                LIMIT 10
            """, [self.db_query_threshold * 1000])  # конвертируем в миллисекунды
            
            # Анализ размера таблиц
            table_stats = await conn.execute_query("""
                SELECT 
                    schemaname, relname, n_live_tup, n_dead_tup,
                    last_vacuum, last_analyze
                FROM pg_stat_user_tables
                ORDER BY n_dead_tup DESC
            """)
            
            # Формируем рекомендации
            recommendations = []
            
            # Рекомендации по индексам
            for schema, table, index, *_ in index_stats:
                recommendations.append(
                    f"Неиспользуемый индекс: {schema}.{table}.{index}. "
                    "Рекомендуется удалить."
                )
            
            # Рекомендации по медленным запросам
            for query, calls, total_time, mean_time in slow_query_stats:
                recommendations.append(
                    f"Медленный запрос (среднее время: {mean_time:.2f}ms, "
                    f"вызовов: {calls}): {query[:100]}..."
                )
            
            # Рекомендации по обслуживанию таблиц
            for schema, table, live_tup, dead_tup, last_vacuum, last_analyze in table_stats:
                if dead_tup > live_tup * 0.1:  # Более 10% мертвых строк
                    recommendations.append(
                        f"Требуется VACUUM для {schema}.{table} "
                        f"(мертвых строк: {dead_tup})"
                    )
                if not last_analyze or (
                    datetime.now() - last_analyze > timedelta(days=7)
                ):
                    recommendations.append(
                        f"Требуется ANALYZE для {schema}.{table}"
                    )
            
            return {
                "unused_indexes": len(index_stats),
                "slow_queries": len(slow_query_stats),
                "tables_need_vacuum": len([
                    t for t in table_stats 
                    if t[3] > t[2] * 0.1
                ]),
                "recommendations": recommendations
            }
        
        except Exception as e:
            logger.error(f"Ошибка при оптимизации запросов: {e}")
            return {}
    
    def optimize_memory(self) -> Dict[str, Any]:
        """
        Оптимизация использования памяти
        
        :return: Результаты оптимизации
        """
        try:
            # Получаем текущее использование памяти
            memory = psutil.virtual_memory()
            initial_usage = memory.percent
            
            if initial_usage > self.memory_threshold:
                # Принудительный сбор мусора
                gc.collect()
                
                # Проверяем результат
                memory = psutil.virtual_memory()
                final_usage = memory.percent
                
                return {
                    "initial_usage": initial_usage,
                    "final_usage": final_usage,
                    "freed_memory": initial_usage - final_usage,
                    "threshold_exceeded": True,
                    "action_taken": "garbage_collection"
                }
            
            return {
                "current_usage": initial_usage,
                "threshold_exceeded": False,
                "action_taken": None
            }
        
        except Exception as e:
            logger.error(f"Ошибка при оптимизации памяти: {e}")
            return {}
    
    def optimize_cpu(self) -> Dict[str, Any]:
        """
        Оптимизация использования CPU
        
        :return: Результаты оптимизации
        """
        try:
            # Получаем текущую загрузку CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            
            if cpu_percent > self.cpu_threshold:
                # Анализируем процессы
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                    try:
                        if proc.info['cpu_percent'] > 5:  # Только активные процессы
                            processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                return {
                    "cpu_usage": cpu_percent,
                    "threshold_exceeded": True,
                    "high_cpu_processes": sorted(
                        processes,
                        key=lambda x: x['cpu_percent'],
                        reverse=True
                    )[:5]  # Топ-5 процессов
                }
            
            return {
                "cpu_usage": cpu_percent,
                "threshold_exceeded": False
            }
        
        except Exception as e:
            logger.error(f"Ошибка при оптимизации CPU: {e}")
            return {}
    
    def optimize_cache(self, cache: Dict[str, Any]) -> Dict[str, Any]:
        """
        Оптимизация кэша
        
        :param cache: Словарь с кэшем
        :return: Результаты оптимизации
        """
        try:
            initial_size = len(cache)
            
            if initial_size > self.cache_size_limit:
                # Удаляем 20% старых записей
                items_to_remove = sorted(
                    cache.items(),
                    key=lambda x: x[1][0]  # Сортировка по времени создания
                )[:int(initial_size * 0.2)]
                
                for key, _ in items_to_remove:
                    del cache[key]
                
                return {
                    "initial_size": initial_size,
                    "final_size": len(cache),
                    "items_removed": len(items_to_remove),
                    "cache_hits": self.cache_hits,
                    "cache_misses": self.cache_misses,
                    "hit_ratio": (
                        self.cache_hits / (self.cache_hits + self.cache_misses)
                        if (self.cache_hits + self.cache_misses) > 0 else 0
                    )
                }
            
            return {
                "current_size": initial_size,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "hit_ratio": (
                    self.cache_hits / (self.cache_hits + self.cache_misses)
                    if (self.cache_hits + self.cache_misses) > 0 else 0
                )
            }
        
        except Exception as e:
            logger.error(f"Ошибка при оптимизации кэша: {e}")
            return {}
    
    @profiler.profile(name="run_optimization")
    async def run_optimization(self) -> Dict[str, Any]:
        """
        Запуск полной оптимизации
        
        :return: Результаты оптимизации
        """
        try:
            # Оптимизация БД
            db_results = await self.optimize_db_queries()
            
            # Оптимизация памяти
            memory_results = self.optimize_memory()
            
            # Оптимизация CPU
            cpu_results = self.optimize_cpu()
            
            # Формируем общий отчет
            return {
                "timestamp": datetime.now().isoformat(),
                "database": db_results,
                "memory": memory_results,
                "cpu": cpu_results,
                "status": "success",
                "recommendations": (
                    db_results.get("recommendations", []) +
                    [
                        f"Высокое использование памяти: {memory_results['initial_usage']}%"
                        if memory_results.get("threshold_exceeded", False) else None,
                        f"Высокая загрузка CPU: {cpu_results['cpu_usage']}%"
                        if cpu_results.get("threshold_exceeded", False) else None
                    ]
                )
            }
        
        except Exception as e:
            logger.error(f"Ошибка при выполнении оптимизации: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }
    
    async def start_monitoring(self):
        """Запуск периодического мониторинга и оптимизации"""
        while True:
            try:
                results = await self.run_optimization()
                
                if results["status"] == "success":
                    # Логируем результаты
                    if any(r for r in results.get("recommendations", []) if r):
                        logger.warning(
                            "Обнаружены проблемы производительности:\n" +
                            "\n".join(r for r in results["recommendations"] if r)
                        )
                    else:
                        logger.info("Оптимизация выполнена успешно, проблем не обнаружено")
                else:
                    logger.error(f"Ошибка при оптимизации: {results.get('error')}")
            
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
            
            await asyncio.sleep(self.optimization_interval)

# Создаем глобальный экземпляр оптимизатора
optimizer = PerformanceOptimizer() 