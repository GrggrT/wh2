from aiogram import types, Dispatcher
from aiogram.utils.markdown import text, bold
from app.db.models import User

async def start_handler(message: types.Message):
    """
    Обработчик команды /start
    """
    # Создаем или получаем пользователя
    user, created = await User.get_or_create(
        telegram_id=message.from_user.id,
        defaults={
            'username': message.from_user.username
        }
    )

    welcome_text = text(
        bold("👋 Добро пожаловать в бот учёта рабочего времени!"),
        "",
        "🔹 Этот бот поможет вам вести учёт рабочего времени и создавать отчёты.",
        "🔹 Используйте /help для получения списка доступных команд.",
        "",
        "Начните с добавления рабочего места командой /workplaces",
        sep="\n"
    )
    
    await message.reply(welcome_text, parse_mode=types.ParseMode.MARKDOWN)

async def help_handler(message: types.Message):
    """
    Обработчик команды /help
    """
    help_text = text(
        bold("📋 Доступные команды:"),
        "",
        "🔸 /start - Начало работы с ботом",
        "🔸 /help - Показать это сообщение",
        "🔸 /add_record - Добавить запись о рабочем времени",
        "🔸 /workplaces - Управление рабочими местами",
        "🔸 /reports - Генерация отчётов",
        "🔸 /calendar - Просмотр и редактирование записей",
        "🔸 /settings - Персональные настройки",
        sep="\n"
    )
    
    await message.reply(help_text, parse_mode=types.ParseMode.MARKDOWN)

def register_handlers(dp: Dispatcher):
    """
    Регистрация обработчиков
    """
    dp.register_message_handler(start_handler, commands=['start'])
    dp.register_message_handler(help_handler, commands=['help']) 