import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
import logging

load_dotenv()

logger = logging.getLogger(__name__)

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

        if 'send_tg' not in columns:
            await conn.execute(
                text("ALTER TABLE _camera ADD COLUMN send_tg INTEGER DEFAULT 0"),
            )
            logger.info(f"[INFO] Column send_tg added.")
        else:
            logger.error(f"The column send_tg already exists.")


if __name__ == "__main__":
    asyncio.run(add_column_to_camera())
