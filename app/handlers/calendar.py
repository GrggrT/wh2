from datetime import datetime, timedelta
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, code
from app.db.models import User, Record, Workplace

class CalendarForm(StatesGroup):
    """Состояния формы календаря"""
    viewing_date = State()
    editing_record = State()

def create_calendar_keyboard(current_date: datetime) -> types.InlineKeyboardMarkup:
    """Создание клавиатуры календаря"""
    keyboard = types.InlineKeyboardMarkup(row_width=7)
    
    # Кнопки навигации по месяцам
    nav_row = [
        types.InlineKeyboardButton("◀️", callback_data=f"calendar:prev:{current_date.strftime('%Y-%m')}"),
        types.InlineKeyboardButton(f"{current_date.strftime('%B %Y')}", callback_data="ignore"),
        types.InlineKeyboardButton("▶️", callback_data=f"calendar:next:{current_date.strftime('%Y-%m')}")
    ]
    keyboard.row(*nav_row)
    
    # Названия дней недели
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    weekday_buttons = [types.InlineKeyboardButton(day, callback_data="ignore") for day in weekdays]
    keyboard.row(*weekday_buttons)
    
    # Получаем первый день месяца
    first_day = current_date.replace(day=1)
    # Получаем последний день месяца
    if current_date.month == 12:
        last_day = current_date.replace(year=current_date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_day = current_date.replace(month=current_date.month + 1, day=1) - timedelta(days=1)
    
    # Заполняем календарь
    current = first_day - timedelta(days=first_day.weekday())
    while current <= last_day + timedelta(days=6-last_day.weekday()):
        week = []
        for _ in range(7):
            if current.month == current_date.month:
                week.append(types.InlineKeyboardButton(
                    str(current.day),
                    callback_data=f"calendar:day:{current.strftime('%Y-%m-%d')}"
                ))
            else:
                week.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            current += timedelta(days=1)
        keyboard.row(*week)
    
    # Добавляем кнопку "Сегодня"
    keyboard.row(types.InlineKeyboardButton(
        "📅 Сегодня",
        callback_data=f"calendar:today"
    ))
    
    return keyboard

async def get_day_records(user_id: int, date: datetime) -> str:
    """Получение записей за день"""
    user = await User.get(telegram_id=user_id)
    records = await Record.filter(
        user=user,
        start_time__gte=date.replace(hour=0, minute=0, second=0),
        start_time__lt=date.replace(hour=0, minute=0, second=0) + timedelta(days=1)
    ).prefetch_related('workplace')
    
    if not records:
        return "Нет записей на этот день"
    
    result = []
    total_duration = timedelta()
    total_earnings = 0
    
    for record in records:
        if record.end_time:
            duration = record.end_time - record.start_time
            earnings = duration.total_seconds() / 3600 * float(record.workplace.rate)
            total_duration += duration
            total_earnings += earnings
            
            result.extend([
                f"🏢 {record.workplace.name}",
                f"⏰ {record.start_time.strftime('%H:%M')} - {record.end_time.strftime('%H:%M')}",
                f"⌛️ {duration.total_seconds() / 3600:.1f} ч",
                f"💰 {earnings:.2f} руб",
                f"📝 {record.description or 'Без описания'}",
                ""
            ])
    
    if result:
        total_hours = total_duration.total_seconds() / 3600
        result.extend([
            bold("Итого:"),
            f"⌛️ {total_hours:.1f} ч",
            f"💰 {total_earnings:.2f} руб"
        ])
    
    return "\n".join(result)

async def calendar_handler(message: types.Message):
    """Обработчик команды /calendar"""
    current_date = datetime.now()
    keyboard = create_calendar_keyboard(current_date)
    
    await message.reply(
        text(
            bold("📅 Календарь"),
            "",
            "Выберите дату для просмотра записей",
            sep="\n"
        ),
        reply_markup=keyboard,
        parse_mode=types.ParseMode.MARKDOWN
    )

async def calendar_callback_handler(callback_query: types.CallbackQuery):
    """Обработчик callback-запросов календаря"""
    action = callback_query.data.split(":")
    
    if action[0] != "calendar" or callback_query.data == "ignore":
        return
    
    if action[1] in ["prev", "next"]:
        current_date = datetime.strptime(action[2], "%Y-%m")
        if action[1] == "prev":
            if current_date.month == 1:
                current_date = current_date.replace(year=current_date.year - 1, month=12)
            else:
                current_date = current_date.replace(month=current_date.month - 1)
        else:
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        keyboard = create_calendar_keyboard(current_date)
        await callback_query.message.edit_reply_markup(reply_markup=keyboard)
    
    elif action[1] == "today":
        current_date = datetime.now()
        keyboard = create_calendar_keyboard(current_date)
        await callback_query.message.edit_reply_markup(reply_markup=keyboard)
    
    elif action[1] == "day":
        selected_date = datetime.strptime(action[2], "%Y-%m-%d")
        records_text = await get_day_records(callback_query.from_user.id, selected_date)
        
        # Добавляем кнопки управления записями
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("➕ Добавить запись", callback_data=f"record:add:{action[2]}"),
            types.InlineKeyboardButton("📅 К календарю", callback_data="calendar:back")
        )
        
        await callback_query.message.edit_text(
            text(
                bold(f"📅 {selected_date.strftime('%d.%m.%Y')}"),
                "",
                records_text,
                sep="\n"
            ),
            reply_markup=keyboard,
            parse_mode=types.ParseMode.MARKDOWN
        )
    
    elif action[1] == "back":
        current_date = datetime.now()
        keyboard = create_calendar_keyboard(current_date)
        await callback_query.message.edit_text(
            text(
                bold("📅 Календарь"),
                "",
                "Выберите дату для просмотра записей",
                sep="\n"
            ),
            reply_markup=keyboard,
            parse_mode=types.ParseMode.MARKDOWN
        )
    
    await callback_query.answer()

def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков календаря"""
    dp.register_message_handler(calendar_handler, commands=['calendar'])
    dp.register_callback_query_handler(
        calendar_callback_handler,
        lambda c: c.data and (c.data.startswith('calendar:') or c.data == 'ignore')
    ) 