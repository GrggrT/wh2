import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import numpy as np
from app.utils.analytics import Analytics
from app.db.models import User, Workplace, Record

@pytest.fixture
def analytics():
    """Фикстура для создания объекта аналитики"""
    return Analytics()

@pytest.fixture
async def user():
    """Фикстура для создания тестового пользователя"""
    user = await User.create(
        telegram_id=123456789,
        username="test_user",
        timezone="Europe/Moscow"
    )
    yield user
    await user.delete()

@pytest.fixture
async def workplace(user):
    """Фикстура для создания тестового рабочего места"""
    workplace = await Workplace.create(
        user=user,
        name="Test Workplace",
        rate=1000.50
    )
    yield workplace
    await workplace.delete()

@pytest.fixture
async def records(user, workplace):
    """Фикстура для создания тестовых записей"""
    records = []
    start_time = datetime.now() - timedelta(days=7)
    
    for i in range(5):
        record = await Record.create(
            user=user,
            workplace=workplace,
            start_time=start_time + timedelta(days=i, hours=9),
            end_time=start_time + timedelta(days=i, hours=17)
        )
        records.append(record)
    
    yield records
    
    for record in records:
        await record.delete()

@pytest.mark.asyncio
async def test_user_statistics(analytics, user, records):
    """Тест получения статистики пользователей"""
    stats = await analytics.get_user_statistics(days=30)
    
    assert isinstance(stats, dict)
    assert "total_users" in stats
    assert "active_users" in stats
    assert "total_records" in stats
    assert "avg_work_duration" in stats
    assert "activity_rate" in stats
    
    assert stats["total_users"] > 0
    assert stats["active_users"] > 0
    assert stats["total_records"] == len(records)
    assert stats["avg_work_duration"] > 0
    assert 0 <= stats["activity_rate"] <= 100

@pytest.mark.asyncio
async def test_workplace_statistics(analytics, workplace, records):
    """Тест получения статистики рабочих мест"""
    stats = await analytics.get_workplace_statistics(days=30)
    
    assert isinstance(stats, dict)
    assert "workplaces" in stats
    assert "total_workplaces" in stats
    assert "most_used" in stats
    assert "most_profitable" in stats
    
    assert len(stats["workplaces"]) > 0
    assert stats["total_workplaces"] > 0
    
    workplace_stat = stats["workplaces"][0]
    assert workplace_stat["name"] == workplace.name
    assert workplace_stat["records_count"] == len(records)
    assert workplace_stat["total_hours"] > 0
    assert workplace_stat["total_earnings"] > 0

@pytest.mark.asyncio
async def test_activity_chart(analytics, records):
    """Тест генерации графика активности"""
    chart_data = await analytics.generate_activity_chart(days=30)
    
    assert isinstance(chart_data, bytes)
    assert len(chart_data) > 0

@pytest.mark.asyncio
async def test_heatmap(analytics, records):
    """Тест генерации тепловой карты"""
    heatmap_data = await analytics.generate_heatmap(days=30)
    
    assert isinstance(heatmap_data, bytes)
    assert len(heatmap_data) > 0

@pytest.mark.asyncio
async def test_efficiency_metrics(analytics, user, records):
    """Тест получения метрик эффективности"""
    metrics = await analytics.get_efficiency_metrics(user.telegram_id, days=30)
    
    assert isinstance(metrics, dict)
    assert "total_hours" in metrics
    assert "total_earnings" in metrics
    assert "avg_daily_hours" in metrics
    assert "efficiency_score" in metrics
    assert "recommendation" in metrics
    
    assert metrics["total_hours"] > 0
    assert metrics["total_earnings"] > 0
    assert metrics["avg_daily_hours"] > 0
    assert 0 <= metrics["efficiency_score"] <= 100
    assert isinstance(metrics["recommendation"], str)

@pytest.mark.asyncio
async def test_cache_functionality(analytics):
    """Тест функциональности кэширования"""
    # Первый запрос (без кэша)
    stats1 = await analytics.get_user_statistics(days=30)
    
    # Второй запрос (должен использовать кэш)
    stats2 = await analytics.get_user_statistics(days=30)
    
    assert stats1 == stats2
    
    # Проверяем наличие данных в кэше
    cache_key = "user_stats_30"
    assert cache_key in analytics.cached_data
    
    # Проверяем валидность кэша
    assert analytics._is_cache_valid(cache_key)
    
    # Проверяем получение данных из кэша
    cached_data = analytics._get_cached_data(cache_key)
    assert cached_data == stats1

@pytest.mark.asyncio
async def test_empty_data_handling(analytics):
    """Тест обработки пустых данных"""
    # Тест без записей
    stats = await analytics.get_workplace_statistics(days=30)
    assert isinstance(stats, dict)
    assert len(stats["workplaces"]) == 0
    
    # Тест метрик эффективности без данных
    metrics = await analytics.get_efficiency_metrics(999999, days=30)
    assert metrics["total_hours"] == 0
    assert metrics["efficiency_score"] == 0
    assert "Недостаточно данных" in metrics["recommendation"]

@pytest.mark.asyncio
async def test_error_handling(analytics):
    """Тест обработки ошибок"""
    # Тест с невалидным ID пользователя
    metrics = await analytics.get_efficiency_metrics(-1, days=30)
    assert isinstance(metrics, dict)
    assert len(metrics) == 0
    
    # Тест с ошибкой при генерации графика
    with patch('matplotlib.pyplot.savefig', side_effect=Exception("Test error")):
        chart_data = await analytics.generate_activity_chart(days=30)
        assert chart_data is None

@pytest.mark.asyncio
async def test_date_range_handling(analytics, user, workplace):
    """Тест обработки различных диапазонов дат"""
    # Создаем записи за разные периоды
    now = datetime.now()
    
    # Старая запись (за пределами периода анализа)
    old_record = await Record.create(
        user=user,
        workplace=workplace,
        start_time=now - timedelta(days=40),
        end_time=now - timedelta(days=40, hours=-8)
    )
    
    # Новая запись (в пределах периода анализа)
    new_record = await Record.create(
        user=user,
        workplace=workplace,
        start_time=now - timedelta(days=5),
        end_time=now - timedelta(days=5, hours=-8)
    )
    
    # Проверяем статистику за 30 дней
    stats = await analytics.get_workplace_statistics(days=30)
    workplace_stat = next(w for w in stats["workplaces"] if w["name"] == workplace.name)
    assert workplace_stat["records_count"] == 1  # Только новая запись
    
    # Проверяем статистику за 60 дней
    stats = await analytics.get_workplace_statistics(days=60)
    workplace_stat = next(w for w in stats["workplaces"] if w["name"] == workplace.name)
    assert workplace_stat["records_count"] == 2  # Обе записи
    
    # Очищаем тестовые данные
    await old_record.delete()
    await new_record.delete() 