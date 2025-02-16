import asyncio
import logging
from tortoise import Tortoise, run_async
from app.db.config import TORTOISE_ORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    """Инициализация базы данных"""
    try:
        # Подключаемся к базе данных
        await Tortoise.init(config=TORTOISE_ORM)
        logger.info("Подключение к базе данных установлено")
        
        # Создаем таблицы
        await Tortoise.generate_schemas()
        logger.info("Схемы базы данных созданы")
        
        # Инициализируем Aerich
        from aerich.commands import init_db
        await init_db(
            tortoise_config=TORTOISE_ORM,
            app="models",
            location="./migrations"
        )
        logger.info("Aerich инициализирован")
        
        # Создаем и применяем миграции
        from aerich.commands import migrate, upgrade
        await migrate("models")
        await upgrade()
        logger.info("Миграции применены")
    
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    run_async(init_db()) 