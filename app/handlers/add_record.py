from datetime import datetime
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, code
from app.db.models import User, Workplace, Record

class RecordForm(StatesGroup):
    """Состояния формы добавления записи"""
    waiting_for_workplace = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_description = State()

async def add_record_start(message: types.Message, state: FSMContext):
    """Начало добавления новой записи"""
    # Получаем пользователя и его рабочие места
    user = await User.get(telegram_id=message.from_user.id)
    workplaces = await Workplace.filter(user=user)
    
    if not workplaces:
        await message.reply(
            text(
                "❌ У вас пока нет рабочих мест.",
                "Сначала добавьте рабочее место командой /add_workplace",
                sep="\n"
            ),
            parse_mode=types.ParseMode.MARKDOWN
        )
        return
    
    # Создаем клавиатуру с рабочими местами
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for workplace in workplaces:
        keyboard.add(workplace.name)
    
    await RecordForm.waiting_for_workplace.set()
    await message.reply(
        "Выберите рабочее место:",
        reply_markup=keyboard,
        parse_mode=types.ParseMode.MARKDOWN
    )

async def process_workplace(message: types.Message, state: FSMContext):
    """Обработка выбора рабочего места"""
    user = await User.get(telegram_id=message.from_user.id)
    workplace = await Workplace.get_or_none(user=user, name=message.text)
    
    if not workplace:
        await message.reply(
            "❌ Рабочее место не найдено. Пожалуйста, выберите из списка.",
            parse_mode=types.ParseMode.MARKDOWN
        )
        return
    
    async with state.proxy() as data:
        data['workplace_id'] = workplace.id
    
    await RecordForm.waiting_for_start_time.set()
    await message.reply(
        text(
            "Введите время начала работы в формате ЧЧ:ММ",
            "Например: 09:00",
            sep="\n"
        ),
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode=types.ParseMode.MARKDOWN
    )

async def process_start_time(message: types.Message, state: FSMContext):
    """Обработка времени начала"""
    try:
        time = datetime.strptime(message.text, "%H:%M")
        today = datetime.now().date()
        start_time = datetime.combine(today, time.time())
        
        async with state.proxy() as data:
            data['start_time'] = start_time
        
        await RecordForm.waiting_for_end_time.set()
        await message.reply(
            text(
                "Введите время окончания работы в формате ЧЧ:ММ",
                "Например: 18:00",
                sep="\n"
            ),
            parse_mode=types.ParseMode.MARKDOWN
        )
    except ValueError:
        await message.reply(
            "❌ Неверный формат времени. Пожалуйста, используйте формат ЧЧ:ММ",
            parse_mode=types.ParseMode.MARKDOWN
        )

async def process_end_time(message: types.Message, state: FSMContext):
    """Обработка времени окончания"""
    try:
        time = datetime.strptime(message.text, "%H:%M")
        today = datetime.now().date()
        end_time = datetime.combine(today, time.time())
        
        async with state.proxy() as data:
            if end_time <= data['start_time']:
                await message.reply(
                    "❌ Время окончания должно быть позже времени начала",
                    parse_mode=types.ParseMode.MARKDOWN
                )
                return
            
            data['end_time'] = end_time
        
        await RecordForm.waiting_for_description.set()
        await message.reply(
            text(
                "Введите описание работы (необязательно)",
                "Или отправьте /skip чтобы пропустить",
                sep="\n"
            ),
            parse_mode=types.ParseMode.MARKDOWN
        )
    except ValueError:
        await message.reply(
            "❌ Неверный формат времени. Пожалуйста, используйте формат ЧЧ:ММ",
            parse_mode=types.ParseMode.MARKDOWN
        )

async def process_description(message: types.Message, state: FSMContext):
    """Обработка описания и сохранение записи"""
    async with state.proxy() as data:
        description = None if message.text == "/skip" else message.text
        
        # Получаем пользователя и рабочее место
        user = await User.get(telegram_id=message.from_user.id)
        workplace = await Workplace.get(id=data['workplace_id'])
        
        # Создаем запись
        record = await Record.create(
            user=user,
            workplace=workplace,
            start_time=data['start_time'],
            end_time=data['end_time'],
            description=description
        )
        
        # Вычисляем продолжительность и стоимость
        duration = (data['end_time'] - data['start_time']).total_seconds() / 3600
        cost = duration * float(workplace.rate)
        
        response_text = text(
            bold("✅ Запись успешно добавлена!"),
            "",
            f"📍 Место: {workplace.name}",
            f"🕒 Начало: {data['start_time'].strftime('%H:%M')}",
            f"🕒 Конец: {data['end_time'].strftime('%H:%M')}",
            f"⏱ Продолжительность: {duration:.2f} ч",
            f"💰 Стоимость: {cost:.2f} руб",
            "",
            f"📝 Описание: {description or 'не указано'}",
            sep="\n"
        )
        
        await message.reply(response_text, parse_mode=types.ParseMode.MARKDOWN)
    
    await state.finish()

def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков"""
    dp.register_message_handler(add_record_start, commands=['add_record'])
    dp.register_message_handler(process_workplace, state=RecordForm.waiting_for_workplace)
    dp.register_message_handler(process_start_time, state=RecordForm.waiting_for_start_time)
    dp.register_message_handler(process_end_time, state=RecordForm.waiting_for_end_time)
    dp.register_message_handler(process_description, state=RecordForm.waiting_for_description) 