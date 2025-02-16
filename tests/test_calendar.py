import pytest
from datetime import datetime, timedelta
from aiogram import types
from app.handlers.calendar import (
    create_calendar_keyboard,
    get_day_records,
    calendar_handler,
    calendar_callback_handler
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
async def record(user, workplace):
    """Фикстура для создания тестовой записи"""
    now = datetime.now()
    record = await Record.create(
        user=user,
        workplace=workplace,
        start_time=now.replace(hour=9, minute=0),
        end_time=now.replace(hour=17, minute=0),
        description="Test record"
    )
    yield record
    await record.delete()

def test_create_calendar_keyboard():
    """Тест создания клавиатуры календаря"""
    current_date = datetime(2024, 3, 20)
    keyboard = create_calendar_keyboard(current_date)
    
    # Проверяем наличие кнопок навигации
    assert "March 2024" in keyboard.inline_keyboard[0][1].text
    assert "◀️" in keyboard.inline_keyboard[0][0].text
    assert "▶️" in keyboard.inline_keyboard[0][2].text
    
    # Проверяем дни недели
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for i, day in enumerate(weekdays):
        assert keyboard.inline_keyboard[1][i].text == day
    
    # Проверяем кнопку "Сегодня"
    assert "📅 Сегодня" in keyboard.inline_keyboard[-1][0].text

@pytest.mark.asyncio
async def test_get_day_records(user, workplace, record):
    """Тест получения записей за день"""
    today = datetime.now()
    records_text = await get_day_records(user.telegram_id, today)
    
    # Проверяем наличие информации о записи
    assert workplace.name in records_text
    assert "09:00" in records_text
    assert "17:00" in records_text
    assert "8.0 ч" in records_text
    assert "8000.00 руб" in records_text
    assert "Test record" in records_text

@pytest.mark.asyncio
async def test_calendar_handler(message):
    """Тест обработчика команды /calendar"""
    response = await calendar_handler(message)
    
    # Проверяем текст сообщения
    assert "📅 Календарь" in response.text
    assert "Выберите дату для просмотра записей" in response.text
    
    # Проверяем наличие клавиатуры
    assert response.reply_markup is not None
    assert isinstance(response.reply_markup, types.InlineKeyboardMarkup)

@pytest.mark.asyncio
async def test_calendar_callback_handler(callback_query, user, workplace, record):
    """Тест обработчика callback-запросов календаря"""
    # Тест навигации по месяцам
    callback_query.data = f"calendar:next:{datetime.now().strftime('%Y-%m')}"
    await calendar_callback_handler(callback_query)
    assert callback_query.message.edit_reply_markup.called
    
    # Тест просмотра дня
    today = datetime.now()
    callback_query.data = f"calendar:day:{today.strftime('%Y-%m-%d')}"
    await calendar_callback_handler(callback_query)
    
    message_text = callback_query.message.edit_text.call_args[0][0]
    assert today.strftime('%d.%m.%Y') in message_text
    assert workplace.name in message_text
    assert "Test record" in message_text
    
    # Тест возврата к календарю
    callback_query.data = "calendar:back"
    await calendar_callback_handler(callback_query)
    assert "Выберите дату для просмотра записей" in callback_query.message.edit_text.call_args[0][0]

@pytest.mark.asyncio
async def test_empty_day_records(user):
    """Тест получения записей за день без записей"""
    today = datetime.now()
    records_text = await get_day_records(user.telegram_id, today)
    assert "Нет записей на этот день" in records_text

@pytest.mark.asyncio
async def test_calendar_navigation():
    """Тест навигации по календарю"""
    current_date = datetime(2024, 3, 20)
    
    # Тест перехода на следующий месяц
    next_month = current_date.replace(month=4)
    keyboard = create_calendar_keyboard(next_month)
    assert "April 2024" in keyboard.inline_keyboard[0][1].text
    
    # Тест перехода на предыдущий месяц
    prev_month = current_date.replace(month=2)
    keyboard = create_calendar_keyboard(prev_month)
    assert "February 2024" in keyboard.inline_keyboard[0][1].text
    
    # Тест перехода на следующий год
    next_year = current_date.replace(year=2025, month=1)
    keyboard = create_calendar_keyboard(next_year)
    assert "January 2025" in keyboard.inline_keyboard[0][1].text 