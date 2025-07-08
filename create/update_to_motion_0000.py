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

        if 'screen_cam' not in columns:
            await conn.execute(
                text("ALTER TABLE _camera ADD COLUMN screen_cam INTEGER DEFAULT 0")
            )
            logger.info("[INFO]Column added.")
        else:
            logger.error("[ERROR] The column already exists.")

if __name__ == "__main__":
    asyncio.run(add_column_to_camera())
