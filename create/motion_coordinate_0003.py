import asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from logs.logging_config import logger

load_dotenv()

from config.config import engine

async def add_column_to_camera():
    async with engine.begin() as conn:
        result = await conn.execute(
            text("PRAGMA table_info(_camera);")
        )
        columns = [row[1] for row in result.fetchall()]

        if 'coordinate_x1' not in columns:
            await conn.execute(
                text("ALTER TABLE _camera ADD COLUMN coordinate_x1 TEXT DEFAULT '0, 0'"),
            )
            any_added = True
        if 'coordinate_x2' not in columns:
            await conn.execute(
                text("ALTER TABLE _camera ADD COLUMN coordinate_x2 TEXT DEFAULT '0, 0'"),
            )
            any_added = True
        if 'coordinate_y1' not in columns:
            await conn.execute(
                text("ALTER TABLE _camera ADD COLUMN coordinate_y1 TEXT DEFAULT '0, 0'"),
            )
            any_added = True
        if 'coordinate_y2' not in columns:
            await conn.execute(
                text("ALTER TABLE _camera ADD COLUMN coordinate_y2 TEXT DEFAULT '0, 0'"),
            )
            any_added = True
        if not any_added:
            logger.warning("[INFO] Все координатные колонки уже существуют.")


if __name__ == "__main__":
    asyncio.run(add_column_to_camera())
