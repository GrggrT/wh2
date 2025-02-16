import os
from typing import Dict, Any

# Получаем URL базы данных из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задан в переменных окружения")

# Конфигурация Tortoise ORM
TORTOISE_ORM: Dict[str, Any] = {
    "connections": {
        "default": DATABASE_URL
    },
    "apps": {
        "models": {
            "models": ["app.db.models", "aerich.models"],
            "default_connection": "default"
        }
    },
    "use_tz": True,
    "timezone": "UTC"
}

# Настройки подключения
DB_CONFIG = {
    "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),
    "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
    "pool_pre_ping": True,
    "echo": os.getenv("DB_ECHO", "false").lower() == "true"
}

# Настройки миграций
MIGRATIONS_CONFIG = {
    "location": "./migrations",
    "src_folder": "./app"
} 