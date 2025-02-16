import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from aiogram import types
from app.handlers.reports import (
    reports_handler,
    process_period_choice,
    generate_report,
    generate_efficiency_report,
    generate_activity_chart,
    generate_heatmap
)
from app.db.models import User, Workplace, Record

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

@pytest.fixture
def message():
    """Фикстура для создания тестового сообщения"""
    message = Mock(spec=types.Message)
    message.from_user = Mock()
    message.from_user.id = 123456789
    message.reply = Mock()
    message.reply_photo = Mock()
    return message

@pytest.mark.asyncio
async def test_reports_handler(message):
    """Тест обработчика команды /reports"""
    await reports_handler(message)
    
    message.reply.assert_called_once()
    args = message.reply.call_args[1]
    assert "📊 Отчеты и аналитика" in args["text"]
    assert isinstance(args["reply_markup"], types.ReplyKeyboardMarkup)
    
    # Проверяем наличие всех кнопок
    keyboard = args["reply_markup"].keyboard
    button_texts = [button.text for row in keyboard for button in row]
    assert "За сегодня" in button_texts
    assert "За неделю" in button_texts
    assert "За месяц" in button_texts
    assert "За произвольный период" in button_texts
    assert "Статистика эффективности" in button_texts
    assert "График активности" in button_texts
    assert "Тепловая карта" in button_texts

@pytest.mark.asyncio
async def test_process_period_choice(message, user, records):
    """Тест обработки выбора периода"""
    # Тест отчета за сегодня
    message.text = "За сегодня"
    await process_period_choice(message, Mock())
    
    message.reply.assert_called_once()
    assert "📊 Отчёт" in message.reply.call_args[1]["text"]
    
    # Сбрасываем мок
    message.reply.reset_mock()
    
    # Тест отчета за неделю
    message.text = "За неделю"
    await process_period_choice(message, Mock())
    
    message.reply.assert_called_once()
    assert "📊 Отчёт" in message.reply.call_args[1]["text"]
    
    # Тест неверного выбора
    message.reply.reset_mock()
    message.text = "Неверный выбор"
    await process_period_choice(message, Mock())
    
    message.reply.assert_called_once()
    assert "❌" in message.reply.call_args[1]["text"]

@pytest.mark.asyncio
async def test_generate_report(message, user, workplace, records):
    """Тест генерации отчета"""
    start_date = datetime.now().date() - timedelta(days=7)
    end_date = datetime.now().date()
    
    await generate_report(message, start_date, end_date)
    
    message.reply.assert_called_once()
    report_text = message.reply.call_args[1]["text"]
    
    assert "📊 Отчёт" in report_text
    assert workplace.name in report_text
    assert "Итого" in report_text
    assert "Всего часов" in report_text
    assert "Общая сумма" in report_text

@pytest.mark.asyncio
async def test_generate_efficiency_report(message, user, records):
    """Тест генерации отчета об эффективности"""
    # Мокаем аналитику
    mock_metrics = {
        "total_hours": 40.0,
        "total_earnings": 40000.0,
        "avg_daily_hours": 8.0,
        "efficiency_score": 85.0,
        "recommendation": "Отличный результат!"
    }
    
    with patch('app.utils.analytics.analytics.get_efficiency_metrics', return_value=mock_metrics):
        await generate_efficiency_report(message)
        
        message.reply.assert_called_once()
        report_text = message.reply.call_args[1]["text"]
        
        assert "📊 Анализ эффективности" in report_text
        assert "40.0" in report_text
        assert "40000.0" in report_text
        assert "85.0%" in report_text
        assert "Отличный результат!" in report_text

@pytest.mark.asyncio
async def test_generate_activity_chart(message, user, records):
    """Тест генерации графика активности"""
    # Мокаем генерацию графика
    mock_chart_data = b"test_chart_data"
    
    with patch('app.utils.analytics.analytics.generate_activity_chart', return_value=mock_chart_data):
        await generate_activity_chart(message)
        
        message.reply_photo.assert_called_once()
        call_args = message.reply_photo.call_args[1]
        
        assert isinstance(call_args["photo"], types.InputFile)
        assert "📈 График активности" in call_args["caption"]

@pytest.mark.asyncio
async def test_generate_heatmap(message, user, records):
    """Тест генерации тепловой карты"""
    # Мокаем генерацию карты
    mock_heatmap_data = b"test_heatmap_data"
    
    with patch('app.utils.analytics.analytics.generate_heatmap', return_value=mock_heatmap_data):
        await generate_heatmap(message)
        
        message.reply_photo.assert_called_once()
        call_args = message.reply_photo.call_args[1]
        
        assert isinstance(call_args["photo"], types.InputFile)
        assert "🌡 Тепловая карта активности" in call_args["caption"]

@pytest.mark.asyncio
async def test_error_handling(message):
    """Тест обработки ошибок"""
    # Тест ошибки при генерации графика
    with patch('app.utils.analytics.analytics.generate_activity_chart', return_value=None):
        await generate_activity_chart(message)
        
        message.reply.assert_called_once()
        assert "❌ Ошибка" in message.reply.call_args[1]["text"]
    
    # Тест ошибки при генерации тепловой карты
    message.reply.reset_mock()
    with patch('app.utils.analytics.analytics.generate_heatmap', return_value=None):
        await generate_heatmap(message)
        
        message.reply.assert_called_once()
        assert "❌ Ошибка" in message.reply.call_args[1]["text"]
    
    # Тест ошибки при получении метрик
    message.reply.reset_mock()
    with patch('app.utils.analytics.analytics.get_efficiency_metrics', return_value=None):
        await generate_efficiency_report(message)
        
        message.reply.assert_called_once()
        assert "❌ Ошибка" in message.reply.call_args[1]["text"] 