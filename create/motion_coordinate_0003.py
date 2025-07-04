import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from logs.logging_config import logger

load_dotenv()


base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
db_path = os.path.join(base_dir, f'{os.getenv("DATABASE")}.db')
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=True)
new_session = async_sessionmaker(engine, expire_on_commit=False)


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
