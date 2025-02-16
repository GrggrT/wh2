from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, code
from app.db.models import User, Workplace

class WorkplaceForm(StatesGroup):
    """Состояния формы добавления рабочего места"""
    waiting_for_name = State()
    waiting_for_rate = State()

async def workplaces_handler(message: types.Message):
    """Обработчик команды /workplaces"""
    # Получаем пользователя
    user = await User.get(telegram_id=message.from_user.id)
    
    # Получаем список рабочих мест пользователя
    workplaces = await Workplace.filter(user=user)
    
    if not workplaces:
        response_text = text(
            bold("📍 У вас пока нет рабочих мест"),
            "",
            "Добавьте новое рабочее место командой /add_workplace",
            sep="\n"
        )
    else:
        workplace_list = "\n".join([
            f"🔹 {w.name} - {w.rate} руб/час" for w in workplaces
        ])
        response_text = text(
            bold("📍 Ваши рабочие места:"),
            "",
            workplace_list,
            "",
            "Команды:",
            "/add_workplace - Добавить новое место",
            "/edit_workplace - Редактировать место",
            "/delete_workplace - Удалить место",
            sep="\n"
        )
    
    await message.reply(response_text, parse_mode=types.ParseMode.MARKDOWN)

async def add_workplace_start(message: types.Message, state: FSMContext):
    """Начало добавления нового рабочего места"""
    await WorkplaceForm.waiting_for_name.set()
    await message.reply(
        "Введите название рабочего места:",
        parse_mode=types.ParseMode.MARKDOWN
    )

async def process_workplace_name(message: types.Message, state: FSMContext):
    """Обработка названия рабочего места"""
    async with state.proxy() as data:
        data['name'] = message.text
    
    await WorkplaceForm.waiting_for_rate.set()
    await message.reply(
        "Введите почасовую ставку (в рублях):",
        parse_mode=types.ParseMode.MARKDOWN
    )

async def process_workplace_rate(message: types.Message, state: FSMContext):
    """Обработка ставки рабочего места"""
    try:
        rate = float(message.text)
        if rate < 0:
            raise ValueError("Ставка не может быть отрицательной")
        
        async with state.proxy() as data:
            # Получаем пользователя
            user = await User.get(telegram_id=message.from_user.id)
            
            # Создаем новое рабочее место
            workplace = await Workplace.create(
                user=user,
                name=data['name'],
                rate=rate
            )
            
            response_text = text(
                bold("✅ Рабочее место успешно добавлено!"),
                "",
                f"📍 Название: {workplace.name}",
                f"💰 Ставка: {workplace.rate} руб/час",
                sep="\n"
            )
            
            await message.reply(response_text, parse_mode=types.ParseMode.MARKDOWN)
    except ValueError:
        await message.reply(
            "❌ Ошибка! Введите корректное числовое значение для ставки.",
            parse_mode=types.ParseMode.MARKDOWN
        )
        return
    
    await state.finish()

def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков"""
    dp.register_message_handler(workplaces_handler, commands=['workplaces'])
    dp.register_message_handler(add_workplace_start, commands=['add_workplace'])
    dp.register_message_handler(process_workplace_name, state=WorkplaceForm.waiting_for_name)
    dp.register_message_handler(process_workplace_rate, state=WorkplaceForm.waiting_for_rate) 