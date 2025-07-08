import asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from logs.logging_config import logger

load_dotenv()

from config.config import engine

async def add_column_to_user():
    any_added = False
    async with engine.begin() as conn:
        result = await conn.execute(
            text("PRAGMA table_info(_user);")
        )
        columns = [row[1] for row in result.fetchall()]

        if 'tg_id' not in columns:
            await conn.execute(
                text("ALTER TABLE _user ADD COLUMN tg_id INTEGER DEFAULT 0"),
            )
            await conn.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_tg_id ON _user(tg_id)")
            )
            any_added = True

        if 'active' not in columns:
            await conn.execute(
                text("ALTER TABLE _user ADD COLUMN active INTEGER DEFAULT 0"),
            )
            any_added = True

        if not any_added:
            logger.warning("[INFO] Поля tg_id, active уже существуют.")
        else:
            logger.info("[INFO] Добавлены новые колонки в таблицу _user.")

if __name__ == "__main__":
    asyncio.run(add_column_to_user())
