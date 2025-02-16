import asyncio
import logging
from tortoise import Tortoise, run_async
from app.db.config import TORTOISE_ORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_db():
    """Проверка подключения к базе данных"""
    try:
        # Подключаемся к базе данных
        await Tortoise.init(config=TORTOISE_ORM)
        logger.info("Подключение к базе данных установлено")
        
        # Проверяем подключение
        conn = Tortoise.get_connection("default")
        await conn.execute_query("SELECT 1")
        logger.info("Тестовый запрос выполнен успешно")
        
        # Проверяем таблицы
        tables = await conn.execute_query("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        logger.info("Найденные таблицы:")
        for table in tables[0]:
            logger.info(f"- {table[0]}")
        
        # Проверяем индексы
        indexes = await conn.execute_query("""
            SELECT tablename, indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public'
        """)
        logger.info("Найденные индексы:")
        for index in indexes[0]:
            logger.info(f"- {index[0]}: {index[1]}")
        
        # Проверяем статистику
        stats = await conn.execute_query("""
            SELECT relname as table_name,
                   n_live_tup as row_count
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
        """)
        logger.info("Статистика таблиц:")
        for stat in stats[0]:
            logger.info(f"- {stat[0]}: {stat[1]} строк")
    
    except Exception as e:
        logger.error(f"Ошибка при проверке базы данных: {e}")
        raise
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    run_async(check_db()) 