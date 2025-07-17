import asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from logs.logging_config import logger
from config.config import engine

load_dotenv()

async def add_column_to_camera():
    async with engine.begin() as conn:
        result = await conn.execute(
            text("PRAGMA table_info(_camera);")
        )
        columns = [row[1] for row in result.fetchall()]

        if 'send_video_tg' not in columns:
            await conn.execute(
                text(f"ALTER TABLE _camera ADD COLUMN send_video_tg INTEGER DEFAULT 0"),
            )
            logger.info(f"[INFO] Column send_video_tg added.")
        else:
            logger.error(f"The column send_video_tg already exists.")


if __name__ == "__main__":
    asyncio.run(add_column_to_camera())
