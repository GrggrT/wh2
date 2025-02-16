import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from tortoise import Tortoise
import psutil
import statistics

from app.bot import register_handlers
from app.db.models import User, Workplace, Record
from app.utils.performance import optimizer

@pytest.fixture
async def database():
    """Фикстура для инициализации тестовой базы данных"""
    await Tortoise.init(
        db_url='sqlite://:memory:',
        modules={'models': ['app.db.models']}
    )
    await Tortoise.generate_schemas()
    
    yield
    
    await Tortoise.close_connections()

@pytest.fixture
def mock_bot():
    """Фикстура для создания мок-объекта бота"""
    bot = Mock(spec=Bot)
    bot.send_message = Mock()
    return bot

@pytest.fixture
def dispatcher(mock_bot):
    """Фикстура для создания диспетчера"""
    storage = MemoryStorage()
    dp = Dispatcher(mock_bot, storage=storage)
    register_handlers(dp)
    return dp

@pytest.fixture
async def test_data(database):
    """Фикстура для создания тестовых данных"""
    # Создаем пользователей
    users = []
    workplaces = []
    records = []
    
    for i in range(10):
        user = await User.create(
            telegram_id=1000000 + i,
            username=f"test_user_{i}",
            timezone="Europe/Moscow"
        )
        users.append(user)
        
        # Создаем рабочие места для каждого пользователя
        for j in range(3):
            workplace = await Workplace.create(
                user=user,
                name=f"Workplace {j+1}",
                rate=1000.0 + j * 100
            )
            workplaces.append(workplace)
            
            # Создаем записи для каждого рабочего места
            for k in range(5):
                record = await Record.create(
                    user=user,
                    workplace=workplace,
                    start_time=datetime.now() - timedelta(days=k),
                    end_time=datetime.now() - timedelta(days=k, hours=-8),
                    description=f"Test record {k+1}"
                )
                records.append(record)
    
    yield {
        "users": users,
        "workplaces": workplaces,
        "records": records
    }
    
    # Очистка
    for record in records:
        await record.delete()
    for workplace in workplaces:
        await workplace.delete()
    for user in users:
        await user.delete()

class LoadTestMetrics:
    """Класс для сбора метрик нагрузочного тестирования"""
    
    def __init__(self):
        self.response_times = []
        self.error_count = 0
        self.success_count = 0
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """Начало теста"""
        self.start_time = time.time()
    
    def stop(self):
        """Окончание теста"""
        self.end_time = time.time()
    
    def add_response_time(self, response_time: float):
        """Добавление времени отклика"""
        self.response_times.append(response_time)
    
    def add_error(self):
        """Увеличение счетчика ошибок"""
        self.error_count += 1
    
    def add_success(self):
        """Увеличение счетчика успешных операций"""
        self.success_count += 1
    
    def get_statistics(self) -> dict:
        """Получение статистики тестирования"""
        if not self.response_times:
            return {}
        
        return {
            "total_requests": len(self.response_times),
            "total_errors": self.error_count,
            "success_rate": (
                self.success_count /
                (self.success_count + self.error_count)
                if (self.success_count + self.error_count) > 0 else 0
            ) * 100,
            "avg_response_time": statistics.mean(self.response_times),
            "min_response_time": min(self.response_times),
            "max_response_time": max(self.response_times),
            "p95_response_time": statistics.quantiles(self.response_times, n=20)[18],
            "total_duration": self.end_time - self.start_time if self.end_time else 0,
            "rps": len(self.response_times) / (self.end_time - self.start_time) if self.end_time else 0
        }

@pytest.mark.asyncio
async def test_concurrent_record_creation(test_data, mock_bot, dispatcher):
    """Тест создания множества записей одновременно"""
    metrics = LoadTestMetrics()
    metrics.start()
    
    async def create_record(user, workplace, i):
        start_time = time.time()
        try:
            record = await Record.create(
                user=user,
                workplace=workplace,
                start_time=datetime.now() + timedelta(hours=i),
                end_time=datetime.now() + timedelta(hours=i+8),
                description=f"Load test record {i}"
            )
            metrics.add_success()
            return record
        except Exception as e:
            metrics.add_error()
            raise
        finally:
            metrics.add_response_time(time.time() - start_time)
    
    # Создаем множество записей параллельно
    user = test_data["users"][0]
    workplace = test_data["workplaces"][0]
    
    tasks = [
        create_record(user, workplace, i)
        for i in range(100)
    ]
    
    records = await asyncio.gather(*tasks, return_exceptions=True)
    metrics.stop()
    
    # Анализируем результаты
    stats = metrics.get_statistics()
    assert stats["success_rate"] > 95  # Ожидаем высокий процент успеха
    assert stats["avg_response_time"] < 0.1  # Ожидаем быстрый отклик
    
    # Очистка
    for record in records:
        if isinstance(record, Record):
            await record.delete()

@pytest.mark.asyncio
async def test_concurrent_queries(test_data, mock_bot, dispatcher):
    """Тест параллельных запросов к базе данных"""
    metrics = LoadTestMetrics()
    metrics.start()
    
    async def run_query(user_id: int):
        start_time = time.time()
        try:
            # Выполняем сложный запрос
            records = await Record.filter(
                user_id=user_id
            ).prefetch_related(
                'workplace'
            ).order_by(
                '-start_time'
            ).limit(10)
            
            metrics.add_success()
            return records
        except Exception as e:
            metrics.add_error()
            raise
        finally:
            metrics.add_response_time(time.time() - start_time)
    
    # Запускаем множество запросов параллельно
    tasks = [
        run_query(user.id)
        for user in test_data["users"]
        for _ in range(10)  # 10 запросов на пользователя
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    metrics.stop()
    
    # Анализируем результаты
    stats = metrics.get_statistics()
    assert stats["success_rate"] > 95
    assert stats["avg_response_time"] < 0.2

@pytest.mark.asyncio
async def test_system_load(test_data, mock_bot, dispatcher):
    """Тест нагрузки на систему"""
    # Начальные показатели
    initial_cpu = psutil.cpu_percent()
    initial_memory = psutil.virtual_memory().percent
    
    metrics = LoadTestMetrics()
    metrics.start()
    
    async def mixed_operations(user, workplace):
        start_time = time.time()
        try:
            # Создание записи
            record = await Record.create(
                user=user,
                workplace=workplace,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=8)
            )
            
            # Получение статистики
            records = await Record.filter(user=user).count()
            
            # Обновление записи
            record.description = "Updated description"
            await record.save()
            
            # Получение детальной информации
            await Record.filter(
                user=user
            ).prefetch_related('workplace').all()
            
            metrics.add_success()
            return record
        except Exception as e:
            metrics.add_error()
            raise
        finally:
            metrics.add_response_time(time.time() - start_time)
    
    # Запускаем множество смешанных операций
    tasks = []
    for user in test_data["users"]:
        for workplace in test_data["workplaces"][:3]:  # Берем первые 3 рабочих места
            tasks.extend([mixed_operations(user, workplace) for _ in range(10)])
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    metrics.stop()
    
    # Конечные показатели
    final_cpu = psutil.cpu_percent()
    final_memory = psutil.virtual_memory().percent
    
    # Анализируем результаты
    stats = metrics.get_statistics()
    assert stats["success_rate"] > 90
    assert stats["avg_response_time"] < 0.5
    
    # Проверяем нагрузку на систему
    assert final_cpu - initial_cpu < 50  # Нагрузка на CPU не должна быть чрезмерной
    assert final_memory - initial_memory < 20  # Утечек памяти быть не должно
    
    # Очистка
    for result in results:
        if isinstance(result, Record):
            await result.delete()

@pytest.mark.asyncio
async def test_optimization_under_load(test_data, mock_bot, dispatcher):
    """Тест работы оптимизатора под нагрузкой"""
    # Создаем дополнительную нагрузку
    records = []
    for _ in range(50):
        for user in test_data["users"]:
            for workplace in test_data["workplaces"][:2]:
                record = await Record.create(
                    user=user,
                    workplace=workplace,
                    start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(hours=8)
                )
                records.append(record)
    
    # Запускаем оптимизацию
    start_time = time.time()
    results = await optimizer.run_optimization()
    optimization_time = time.time() - start_time
    
    # Проверяем результаты
    assert results["status"] == "success"
    assert optimization_time < 5  # Оптимизация должна быть быстрой
    assert "database" in results
    assert "memory" in results
    assert "cpu" in results
    
    # Проверяем рекомендации
    if "recommendations" in results:
        assert any(
            "индекс" in r.lower() or
            "vacuum" in r.lower() or
            "analyze" in r.lower()
            for r in results["recommendations"]
            if r is not None
        )
    
    # Очистка
    for record in records:
        await record.delete()

@pytest.mark.asyncio
async def test_long_running_operations(test_data, mock_bot, dispatcher):
    """Тест длительных операций"""
    metrics = LoadTestMetrics()
    metrics.start()
    
    async def long_operation(user):
        start_time = time.time()
        try:
            # Симулируем сложную агрегацию
            records = await Record.filter(
                user=user
            ).prefetch_related(
                'workplace'
            ).all()
            
            total_duration = timedelta()
            total_earnings = 0
            
            for record in records:
                if record.end_time:
                    duration = record.end_time - record.start_time
                    total_duration += duration
                    total_earnings += (
                        duration.total_seconds() / 3600 *
                        float(record.workplace.rate)
                    )
            
            # Симулируем сложные вычисления
            await asyncio.sleep(0.1)
            
            metrics.add_success()
            return {
                "total_hours": total_duration.total_seconds() / 3600,
                "total_earnings": total_earnings
            }
        except Exception as e:
            metrics.add_error()
            raise
        finally:
            metrics.add_response_time(time.time() - start_time)
    
    # Запускаем длительные операции параллельно
    tasks = [
        long_operation(user)
        for user in test_data["users"]
        for _ in range(5)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    metrics.stop()
    
    # Анализируем результаты
    stats = metrics.get_statistics()
    assert stats["success_rate"] > 95
    assert stats["avg_response_time"] < 1.0  # Допускаем более длительное время отклика
    assert stats["p95_response_time"] < 2.0  # 95-й процентиль должен быть в пределах 