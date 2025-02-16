#!/usr/bin/env python3
import os
import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from tortoise import Tortoise
from dotenv import load_dotenv

# Импорт обработчиков
from app.handlers import (
    start,
    workplaces,
    add_record,
    reports,
    settings,
    calendar
)

# Импорт middleware
from app.middlewares.error_handler import ErrorHandlerMiddleware
from app.middlewares.rate_limiter import RateLimiterMiddleware

# Импорт утилит
from app.utils.health_check import HealthCheck
from app.utils.scheduler import setup_scheduler
from app.utils.webhook import WebhookServer

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получение конфигурации из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
TIMEZONE_DB_API_KEY = os.getenv("TIMEZONE_DB_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Проверка обязательных переменных
if not BOT_TOKEN:
    raise ValueError("Не задан BOT_TOKEN в переменных окружения")
if not DATABASE_URL:
    raise ValueError("Не задан DATABASE_URL в переменных окружения")
if not ADMIN_ID:
    raise ValueError("Не задан ADMIN_ID в переменных окружения")
if not TIMEZONE_DB_API_KEY:
    raise ValueError("Не задан TIMEZONE_DB_API_KEY в переменных окружения")

async def on_startup(dp: Dispatcher):
    """
    Действия при запуске бота
    """
    try:
        # Инициализация базы данных
        await Tortoise.init(
            db_url=DATABASE_URL,
            modules={'models': ['app.db.models']}
        )
        await Tortoise.generate_schemas()
        logger.info("База данных инициализирована")

        # Инициализация планировщика задач
        scheduler = setup_scheduler(dp.bot)
        logger.info("Планировщик задач инициализирован")

        # Отправка уведомления администратору о запуске бота
        await dp.bot.send_message(
            ADMIN_ID,
            "🚀 Бот запущен и готов к работе!\n\n"
            f"Версия API: {(await dp.bot.get_me()).username}\n"
            f"База данных: подключена\n"
            f"Планировщик: активен\n"
            f"Режим логирования: {os.getenv('LOG_LEVEL', 'INFO')}"
        )

        # Запуск мониторинга состояния
        health_check = HealthCheck(dp.bot)
        asyncio.create_task(health_check.start_monitoring())
        logger.info("Мониторинг состояния запущен")

    except Exception as e:
        logger.error(f"Ошибка при инициализации: {e}")
        # Отправка уведомления об ошибке администратору
        await dp.bot.send_message(
            ADMIN_ID,
            f"❌ Ошибка при запуске бота:\n{str(e)}"
        )
        raise

async def on_shutdown(dp: Dispatcher):
    """
    Действия при остановке бота
    """
    try:
        # Отправка уведомления администратору
        await dp.bot.send_message(
            ADMIN_ID,
            "🔴 Бот останавливается..."
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о выключении: {e}")
    
    # Остановка планировщика
    from app.utils.scheduler import scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("Планировщик задач остановлен")
    
    # Закрытие соединений с базой данных
    await Tortoise.close_connections()
    logger.info("Соединения с базой данных закрыты")

def register_handlers(dp: Dispatcher):
    """
    Регистрация всех обработчиков
    """
    # Регистрация обработчиков команд
    start.register_handlers(dp)
    workplaces.register_handlers(dp)
    add_record.register_handlers(dp)
    reports.register_handlers(dp)
    settings.register_handlers(dp)
    calendar.register_handlers(dp)

async def main():
    """
    Основная функция запуска бота
    """
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()  # Для хранения состояний FSM
    dp = Dispatcher(bot, storage=storage)

    # Установка middleware
    dp.middleware.setup(LoggingMiddleware())
    dp.middleware.setup(ErrorHandlerMiddleware())
    dp.middleware.setup(RateLimiterMiddleware())

    # Регистрация обработчиков
    register_handlers(dp)

    # Установка функций запуска и завершения
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запуск бота
    try:
        logger.info("Бот запущен")
        
        # Проверяем режим работы
        webhook_url = os.getenv("WEBHOOK_URL")
        if webhook_url:
            # Webhook режим
            logger.info("Запуск в режиме webhook")
            webhook_server = WebhookServer(bot, dp)
            await webhook_server.start()
            
            # Ждем завершения
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                await webhook_server.stop()
        else:
            # Long polling режим
            logger.info("Запуск в режиме long polling")
            await dp.start_polling()
    
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}")
        # Отправка уведомления об ошибке администратору
        await bot.send_message(
            ADMIN_ID,
            f"❌ Критическая ошибка в работе бота:\n{str(e)}"
        )
        raise
    finally:
        logger.info("Бот остановлен")
        await dp.storage.close()
        await dp.storage.wait_closed()
        await bot.session.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен по команде пользователя")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
        raise 