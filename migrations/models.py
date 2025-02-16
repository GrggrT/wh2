from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- Создание таблицы пользователей
        CREATE TABLE IF NOT EXISTS "users" (
            "id" SERIAL PRIMARY KEY,
            "telegram_id" BIGINT NOT NULL UNIQUE,
            "username" VARCHAR(50),
            "timezone" VARCHAR(50) NOT NULL DEFAULT 'UTC',
            "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS "idx_users_telegram_id" ON "users" ("telegram_id");
        
        -- Создание таблицы рабочих мест
        CREATE TABLE IF NOT EXISTS "workplaces" (
            "id" SERIAL PRIMARY KEY,
            "user_id" INTEGER NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            "name" VARCHAR(100) NOT NULL,
            "rate" DECIMAL(10,2) NOT NULL DEFAULT 0.0,
            "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS "idx_workplaces_user_id" ON "workplaces" ("user_id");
        
        -- Создание таблицы записей
        CREATE TABLE IF NOT EXISTS "records" (
            "id" SERIAL PRIMARY KEY,
            "user_id" INTEGER NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
            "workplace_id" INTEGER REFERENCES "workplaces" ("id") ON DELETE SET NULL,
            "start_time" TIMESTAMPTZ NOT NULL,
            "end_time" TIMESTAMPTZ,
            "description" TEXT,
            "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS "idx_records_user_id" ON "records" ("user_id");
        CREATE INDEX IF NOT EXISTS "idx_records_workplace_id" ON "records" ("workplace_id");
        CREATE INDEX IF NOT EXISTS "idx_records_start_time" ON "records" ("start_time");
        
        -- Триггер для автоматического обновления updated_at
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        CREATE TRIGGER update_records_updated_at
            BEFORE UPDATE ON records
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TRIGGER IF EXISTS update_records_updated_at ON records;
        DROP FUNCTION IF EXISTS update_updated_at_column();
        DROP TABLE IF EXISTS "records";
        DROP TABLE IF EXISTS "workplaces";
        DROP TABLE IF EXISTS "users";
    """ 