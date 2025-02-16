import os
import logging
import ssl
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

logger = logging.getLogger(__name__)

class WebhookServer:
    """Класс для управления веб-сервером с поддержкой webhook"""
    
    def __init__(self, bot: Bot, dp: Dispatcher):
        """
        Инициализация сервера
        
        :param bot: Экземпляр бота
        :param dp: Экземпляр диспетчера
        """
        self.bot = bot
        self.dp = dp
        self.app = web.Application()
        self.webhook_path = f"/webhook/{bot.token}"
        self.webhook_url = os.getenv("WEBHOOK_URL")
        self.webapp_host = os.getenv("WEBAPP_HOST", "0.0.0.0")
        self.webapp_port = int(os.getenv("WEBAPP_PORT", 8000))
        
        # Настройки SSL
        self.ssl_cert = os.getenv("SSL_CERT")
        self.ssl_key = os.getenv("SSL_KEY")
        self.ssl_context = None
        
        # Health-check endpoint
        self.app.router.add_get("/health", self.health_check_handler)
    
    async def health_check_handler(self, request: web.Request) -> web.Response:
        """
        Обработчик health-check запросов
        
        :param request: HTTP запрос
        :return: HTTP ответ
        """
        try:
            # Получаем статус от health-check системы
            from app.utils.health_check import HealthCheck
            health_check = HealthCheck(self.bot)
            status = await health_check.check()
            
            return web.json_response(
                status,
                status=200 if status["meta"]["status"] == "healthy" else 503
            )
        except Exception as e:
            logger.error(f"Ошибка при выполнении health-check: {e}")
            return web.json_response(
                {
                    "status": "error",
                    "error": str(e)
                },
                status=500
            )
    
    def setup_ssl(self):
        """Настройка SSL для веб-сервера"""
        if self.ssl_cert and self.ssl_key:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(self.ssl_cert, self.ssl_key)
            logger.info("SSL настроен успешно")
        else:
            logger.warning("SSL сертификаты не найдены, сервер будет работать без SSL")
    
    async def setup_webhook(self):
        """Настройка webhook для бота"""
        if not self.webhook_url:
            raise ValueError("Не задан WEBHOOK_URL в переменных окружения")
        
        webhook_url = f"{self.webhook_url}{self.webhook_path}"
        
        # Удаляем старый webhook
        await self.bot.delete_webhook()
        
        # Устанавливаем новый webhook
        if self.ssl_cert:
            with open(self.ssl_cert, 'rb') as cert:
                await self.bot.set_webhook(
                    url=webhook_url,
                    certificate=cert,
                    drop_pending_updates=True
                )
        else:
            await self.bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True
            )
        
        logger.info(f"Webhook установлен: {webhook_url}")
    
    def setup_routes(self):
        """Настройка маршрутов веб-сервера"""
        # Настраиваем обработчик webhook
        SimpleRequestHandler(
            dispatcher=self.dp,
            bot=self.bot,
            secret_token=self.bot.token
        ).register(self.app, path=self.webhook_path)
        
        # Настраиваем дополнительные маршруты
        setup_application(self.app, self.dp)
    
    async def start(self):
        """Запуск веб-сервера"""
        try:
            # Настраиваем SSL
            self.setup_ssl()
            
            # Настраиваем маршруты
            self.setup_routes()
            
            # Настраиваем webhook
            await self.setup_webhook()
            
            # Запускаем веб-сервер
            runner = web.AppRunner(self.app)
            await runner.setup()
            
            site = web.TCPSite(
                runner,
                host=self.webapp_host,
                port=self.webapp_port,
                ssl_context=self.ssl_context
            )
            
            await site.start()
            
            logger.info(
                f"Веб-сервер запущен на {self.webapp_host}:{self.webapp_port}"
                f"{' с SSL' if self.ssl_context else ''}"
            )
        
        except Exception as e:
            logger.error(f"Ошибка при запуске веб-сервера: {e}")
            raise
    
    async def stop(self):
        """Остановка веб-сервера"""
        try:
            # Удаляем webhook
            await self.bot.delete_webhook()
            logger.info("Webhook удален")
            
            # Останавливаем веб-сервер
            await self.app.shutdown()
            logger.info("Веб-сервер остановлен")
        
        except Exception as e:
            logger.error(f"Ошибка при остановке веб-сервера: {e}")
            raise 