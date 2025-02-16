import pytest
from unittest.mock import Mock, patch, mock_open
from aiohttp import web
from aiogram import Bot, Dispatcher
from app.utils.webhook import WebhookServer

@pytest.fixture
def mock_bot():
    """Фикстура для создания мок-объекта бота"""
    bot = Mock(spec=Bot)
    bot.token = "test_token"
    bot.delete_webhook = Mock()
    bot.set_webhook = Mock()
    return bot

@pytest.fixture
def mock_dp():
    """Фикстура для создания мок-объекта диспетчера"""
    return Mock(spec=Dispatcher)

@pytest.fixture
def webhook_server(mock_bot, mock_dp):
    """Фикстура для создания объекта WebhookServer"""
    with patch.dict('os.environ', {
        'WEBHOOK_URL': 'https://example.com',
        'WEBAPP_HOST': 'localhost',
        'WEBAPP_PORT': '8000'
    }):
        return WebhookServer(mock_bot, mock_dp)

@pytest.mark.asyncio
async def test_health_check_handler(webhook_server, mock_bot):
    """Тест обработчика health-check"""
    # Мокаем объект Request
    request = Mock()
    
    # Мокаем HealthCheck
    mock_status = {
        "meta": {
            "status": "healthy",
            "timestamp": "2024-03-20T12:00:00Z"
        }
    }
    
    with patch('app.utils.health_check.HealthCheck') as MockHealthCheck:
        MockHealthCheck.return_value.check.return_value = mock_status
        
        # Тест успешного запроса
        response = await webhook_server.health_check_handler(request)
        assert response.status == 200
        assert await response.json() == mock_status
        
        # Тест с ошибкой
        MockHealthCheck.return_value.check.side_effect = Exception("Test error")
        response = await webhook_server.health_check_handler(request)
        assert response.status == 500
        response_json = await response.json()
        assert response_json["status"] == "error"
        assert "Test error" in response_json["error"]

def test_setup_ssl(webhook_server):
    """Тест настройки SSL"""
    # Тест без SSL сертификатов
    webhook_server.setup_ssl()
    assert webhook_server.ssl_context is None
    
    # Тест с SSL сертификатами
    with patch.dict('os.environ', {
        'SSL_CERT': 'cert.pem',
        'SSL_KEY': 'key.pem'
    }), patch('ssl.create_default_context') as mock_ssl:
        webhook_server.ssl_cert = 'cert.pem'
        webhook_server.ssl_key = 'key.pem'
        webhook_server.setup_ssl()
        
        mock_ssl.assert_called_once()
        mock_ssl.return_value.load_cert_chain.assert_called_once_with(
            'cert.pem',
            'key.pem'
        )

@pytest.mark.asyncio
async def test_setup_webhook(webhook_server, mock_bot):
    """Тест настройки webhook"""
    # Тест без SSL
    await webhook_server.setup_webhook()
    
    mock_bot.delete_webhook.assert_called_once()
    mock_bot.set_webhook.assert_called_once_with(
        url=f"https://example.com/webhook/{mock_bot.token}",
        drop_pending_updates=True
    )
    
    # Тест с SSL
    mock_bot.reset_mock()
    webhook_server.ssl_cert = 'cert.pem'
    
    with patch('builtins.open', mock_open(read_data='test cert')):
        await webhook_server.setup_webhook()
        
        mock_bot.set_webhook.assert_called_once()
        call_kwargs = mock_bot.set_webhook.call_args[1]
        assert 'certificate' in call_kwargs

def test_setup_routes(webhook_server):
    """Тест настройки маршрутов"""
    with patch('aiogram.webhook.aiohttp_server.SimpleRequestHandler') as MockHandler, \
         patch('aiogram.webhook.aiohttp_server.setup_application') as mock_setup:
        
        webhook_server.setup_routes()
        
        # Проверяем создание обработчика webhook
        MockHandler.assert_called_once_with(
            dispatcher=webhook_server.dp,
            bot=webhook_server.bot,
            secret_token=webhook_server.bot.token
        )
        
        # Проверяем регистрацию маршрутов
        MockHandler.return_value.register.assert_called_once_with(
            webhook_server.app,
            path=webhook_server.webhook_path
        )
        
        # Проверяем настройку приложения
        mock_setup.assert_called_once_with(webhook_server.app, webhook_server.dp)

@pytest.mark.asyncio
async def test_start_server(webhook_server):
    """Тест запуска сервера"""
    with patch('aiohttp.web.AppRunner') as MockRunner, \
         patch('aiohttp.web.TCPSite') as MockSite:
        
        # Мокаем методы
        webhook_server.setup_ssl = Mock()
        webhook_server.setup_routes = Mock()
        webhook_server.setup_webhook = Mock()
        
        # Запускаем сервер
        await webhook_server.start()
        
        # Проверяем вызовы методов
        webhook_server.setup_ssl.assert_called_once()
        webhook_server.setup_routes.assert_called_once()
        webhook_server.setup_webhook.assert_called_once()
        
        # Проверяем создание и запуск сервера
        MockRunner.assert_called_once_with(webhook_server.app)
        MockRunner.return_value.setup.assert_called_once()
        MockSite.assert_called_once()
        MockSite.return_value.start.assert_called_once()

@pytest.mark.asyncio
async def test_stop_server(webhook_server):
    """Тест остановки сервера"""
    await webhook_server.stop()
    
    # Проверяем удаление webhook
    webhook_server.bot.delete_webhook.assert_called_once()
    
    # Проверяем остановку сервера
    webhook_server.app.shutdown.assert_called_once()

@pytest.mark.asyncio
async def test_error_handling(webhook_server, mock_bot):
    """Тест обработки ошибок"""
    # Тест ошибки при запуске
    mock_bot.set_webhook.side_effect = Exception("Test error")
    
    with pytest.raises(Exception) as exc_info:
        await webhook_server.start()
    assert "Test error" in str(exc_info.value)
    
    # Тест ошибки при остановке
    mock_bot.delete_webhook.side_effect = Exception("Test error")
    
    with pytest.raises(Exception) as exc_info:
        await webhook_server.stop()
    assert "Test error" in str(exc_info.value) 