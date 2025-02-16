import pytest
from datetime import datetime
from aiogram import types
from app.middlewares.error_handler import ErrorHandlerMiddleware
from app.middlewares.rate_limiter import RateLimiterMiddleware

@pytest.fixture
def message():
    """Фикстура для создания тестового сообщения"""
    params = {
        "message_id": 1,
        "date": datetime.now(),
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
        "text": "/test"
    }
    return types.Message(**params)

@pytest.mark.asyncio
async def test_error_handler_middleware():
    """Тест обработчика ошибок"""
    middleware = ErrorHandlerMiddleware()
    
    # Тестовый обработчик, который вызывает ошибку
    async def error_handler(message, data):
        raise ValueError("Test error")
    
    # Тестовый обработчик без ошибок
    async def success_handler(message, data):
        return "Success"
    
    # Тест обработки ошибки
    result = await middleware(error_handler, message, {"bot": None})
    assert result is True  # Middleware должен вернуть True, чтобы остановить обработку
    
    # Тест успешного выполнения
    result = await middleware(success_handler, message, {})
    assert result == "Success"

@pytest.mark.asyncio
async def test_rate_limiter_middleware():
    """Тест ограничителя запросов"""
    middleware = RateLimiterMiddleware()
    
    # Тестовый обработчик
    async def test_handler(message, data):
        return "Success"
    
    message = types.Message(**{
        "message_id": 1,
        "date": datetime.now(),
        "chat": {"id": 123456789, "type": "private"},
        "from": {"id": 123456789, "is_bot": False},
        "text": "/test"
    })
    
    # Тест первого запроса (должен пройти)
    result = await middleware(test_handler, message, {})
    assert result == "Success"
    
    # Создаем много запросов для превышения лимита
    for _ in range(30):
        await middleware(test_handler, message, {})
    
    # Тест превышения лимита
    result = await middleware(test_handler, message, {})
    assert result is True  # Middleware должен вернуть True при превышении лимита

@pytest.mark.asyncio
async def test_rate_limiter_different_commands():
    """Тест ограничителя запросов для разных команд"""
    middleware = RateLimiterMiddleware()
    
    async def test_handler(message, data):
        return "Success"
    
    # Создаем сообщения с разными командами
    message1 = types.Message(**{
        "message_id": 1,
        "date": datetime.now(),
        "chat": {"id": 123456789, "type": "private"},
        "from": {"id": 123456789, "is_bot": False},
        "text": "/command1"
    })
    
    message2 = types.Message(**{
        "message_id": 2,
        "date": datetime.now(),
        "chat": {"id": 123456789, "type": "private"},
        "from": {"id": 123456789, "is_bot": False},
        "text": "/command2"
    })
    
    # Тест независимости лимитов разных команд
    for _ in range(middleware.limits['default'][0]):  # Достигаем лимита для command1
        result = await middleware(test_handler, message1, {})
        assert result == "Success"
    
    # Проверяем, что command2 все еще работает
    result = await middleware(test_handler, message2, {})
    assert result == "Success"
    
    # Проверяем, что command1 заблокирована
    result = await middleware(test_handler, message1, {})
    assert result is True

@pytest.mark.asyncio
async def test_rate_limiter_cleanup():
    """Тест очистки старых запросов в ограничителе"""
    middleware = RateLimiterMiddleware()
    
    async def test_handler(message, data):
        return "Success"
    
    message = types.Message(**{
        "message_id": 1,
        "date": datetime.now(),
        "chat": {"id": 123456789, "type": "private"},
        "from": {"id": 123456789, "is_bot": False},
        "text": "/test"
    })
    
    # Заполняем историю запросов
    for _ in range(middleware.limits['default'][0] - 1):
        result = await middleware(test_handler, message, {})
        assert result == "Success"
    
    # Очищаем старые запросы (имитируем прошествие времени)
    user_id = message.from_user.id
    command = middleware._get_command(message)
    middleware.last_requests[user_id][command] = []
    
    # Проверяем, что можно снова делать запросы
    result = await middleware(test_handler, message, {})
    assert result == "Success" 