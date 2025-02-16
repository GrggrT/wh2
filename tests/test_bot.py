import pytest
from aiogram import Bot, Dispatcher, types
from app.bot import register_handlers
from app.handlers.start import start_handler
from app.handlers.settings import settings_handler
from app.db.models import User

@pytest.fixture
async def bot():
    """Фикстура для создания тестового бота"""
    bot = Bot(token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    try:
        yield bot
    finally:
        await bot.close()

@pytest.fixture
async def dp(bot):
    """Фикстура для создания тестового диспетчера"""
    dp = Dispatcher(bot)
    register_handlers(dp)
    return dp

@pytest.fixture
def message(bot):
    """Фикстура для создания тестового сообщения"""
    params = {
        "message_id": 1,
        "date": 1635528460,
        "chat": {
            "id": 123456789,
            "type": "private",
            "username": "test_user",
            "first_name": "Test",
            "last_name": "User"
        },
        "from": {
            "id": 123456789,
            "is_bot": False,
            "username": "test_user",
            "first_name": "Test",
            "last_name": "User",
            "language_code": "ru"
        },
        "text": "/start"
    }
    return types.Message(**params)

@pytest.mark.asyncio
async def test_start_command(message, bot):
    """Тест команды /start"""
    # Создаем тестового пользователя
    user = await User.create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        timezone="Europe/Moscow"
    )
    
    # Вызываем обработчик команды /start
    response = await start_handler(message)
    
    # Проверяем, что ответ содержит нужный текст
    assert "Добро пожаловать" in response.text
    assert message.from_user.first_name in response.text
    
    # Очищаем тестовые данные
    await user.delete()

@pytest.mark.asyncio
async def test_settings_command(message, bot):
    """Тест команды /settings"""
    # Создаем тестового пользователя
    user = await User.create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        timezone="Europe/Moscow"
    )
    
    # Меняем текст сообщения на /settings
    message.text = "/settings"
    
    # Вызываем обработчик команды /settings
    response = await settings_handler(message)
    
    # Проверяем, что ответ содержит нужный текст
    assert "Настройки" in response.text
    assert "Часовой пояс" in response.text
    
    # Очищаем тестовые данные
    await user.delete() 