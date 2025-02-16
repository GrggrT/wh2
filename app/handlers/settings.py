from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.markdown import text, bold, code
from app.db.models import User
from app.utils.timezone import timezone_db

class SettingsForm(StatesGroup):
    """Состояния формы настроек"""
    waiting_for_timezone = State()
    waiting_for_location = State()

async def settings_handler(message: types.Message):
    """Обработчик команды /settings"""
    user = await User.get(telegram_id=message.from_user.id)
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add("Изменить часовой пояс")
    keyboard.add("Определить часовой пояс по геолокации")
    keyboard.add("Назад")
    
    settings_text = text(
        bold("⚙️ Настройки"),
        "",
        f"🌐 Часовой пояс: {user.timezone}",
        "",
        "Выберите действие:",
        sep="\n"
    )
    
    await message.reply(
        settings_text,
        reply_markup=keyboard,
        parse_mode=types.ParseMode.MARKDOWN
    )

async def process_settings_choice(message: types.Message, state: FSMContext):
    """Обработка выбора действия в настройках"""
    if message.text == "Изменить часовой пояс":
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        timezones = [
            "Europe/Moscow", "Europe/London", "Europe/Paris", "Europe/Berlin",
            "Asia/Tokyo", "Asia/Singapore", "America/New_York", "America/Los_Angeles"
        ]
        for tz in timezones:
            keyboard.add(tz)
        keyboard.add("Назад")
        
        await SettingsForm.waiting_for_timezone.set()
        await message.reply(
            text(
                "Выберите ваш часовой пояс из списка",
                "или отправьте название вашего города на английском языке",
                "",
                "Например: Moscow, New York, London",
                sep="\n"
            ),
            reply_markup=keyboard,
            parse_mode=types.ParseMode.MARKDOWN
        )
    
    elif message.text == "Определить часовой пояс по геолокации":
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton("Отправить геолокацию", request_location=True))
        keyboard.add("Назад")
        
        await SettingsForm.waiting_for_location.set()
        await message.reply(
            text(
                "📍 Отправьте вашу геолокацию для определения часового пояса",
                "",
                "Нажмите кнопку 'Отправить геолокацию' ниже",
                sep="\n"
            ),
            reply_markup=keyboard,
            parse_mode=types.ParseMode.MARKDOWN
        )
    
    elif message.text == "Назад":
        await message.reply(
            "Вы вернулись в главное меню",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode=types.ParseMode.MARKDOWN
        )
    
    else:
        await message.reply(
            "❌ Пожалуйста, выберите действие из меню",
            parse_mode=types.ParseMode.MARKDOWN
        )

async def process_timezone(message: types.Message, state: FSMContext):
    """Обработка выбора часового пояса"""
    if message.text == "Назад":
        await state.finish()
        await settings_handler(message)
        return
    
    try:
        # Получаем информацию о часовом поясе
        timezone_info = await timezone_db.get_time_zone_by_zone(message.text)
        if not timezone_info:
            await message.reply(
                "❌ Не удалось найти информацию о часовом поясе. Пожалуйста, выберите из списка.",
                parse_mode=types.ParseMode.MARKDOWN
            )
            return
        
        # Обновляем часовой пояс пользователя
        user = await User.get(telegram_id=message.from_user.id)
        user.timezone = timezone_info["timezone"]
        await user.save()
        
        await message.reply(
            text(
                bold("✅ Настройки обновлены"),
                "",
                f"🌐 Новый часовой пояс: {timezone_info['timezone']}",
                f"⏰ Смещение: {timezone_info['formatted']}",
                sep="\n"
            ),
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode=types.ParseMode.MARKDOWN
        )
        
        await state.finish()
    
    except Exception as e:
        await message.reply(
            text(
                "❌ Произошла ошибка при обновлении часового пояса",
                "",
                str(e),
                sep="\n"
            ),
            parse_mode=types.ParseMode.MARKDOWN
        )

async def process_location(message: types.Message, state: FSMContext):
    """Обработка полученной геолокации"""
    if not message.location:
        await message.reply(
            "❌ Пожалуйста, отправьте геолокацию с помощью кнопки ниже",
            parse_mode=types.ParseMode.MARKDOWN
        )
        return
    
    try:
        # Получаем информацию о часовом поясе по координатам
        timezone_info = await timezone_db.get_time_zone(
            message.location.latitude,
            message.location.longitude
        )
        
        if not timezone_info:
            await message.reply(
                "❌ Не удалось определить часовой пояс по вашей геолокации",
                parse_mode=types.ParseMode.MARKDOWN
            )
            return
        
        # Обновляем часовой пояс пользователя
        user = await User.get(telegram_id=message.from_user.id)
        user.timezone = timezone_info["timezone"]
        await user.save()
        
        await message.reply(
            text(
                bold("✅ Часовой пояс успешно определён"),
                "",
                f"🌐 Ваш часовой пояс: {timezone_info['timezone']}",
                f"⏰ Смещение: {timezone_info['formatted']}",
                f"📍 Координаты: {message.location.latitude:.6f}, {message.location.longitude:.6f}",
                sep="\n"
            ),
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode=types.ParseMode.MARKDOWN
        )
        
        await state.finish()
    
    except Exception as e:
        await message.reply(
            text(
                "❌ Произошла ошибка при определении часового пояса",
                "",
                str(e),
                sep="\n"
            ),
            parse_mode=types.ParseMode.MARKDOWN
        )

def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков"""
    dp.register_message_handler(settings_handler, commands=['settings'])
    dp.register_message_handler(process_settings_choice, lambda msg: msg.text in [
        "Изменить часовой пояс",
        "Определить часовой пояс по геолокации",
        "Назад"
    ])
    dp.register_message_handler(process_timezone, state=SettingsForm.waiting_for_timezone)
    dp.register_message_handler(process_location, content_types=['location'], state=SettingsForm.waiting_for_location) 