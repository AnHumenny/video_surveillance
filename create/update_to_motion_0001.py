import asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from logs.logging_config import logger
from config.config import engine

load_dotenv()

async def add_column_cam_to_camera():
    async with engine.begin() as conn:
        result = await conn.execute(
            text("PRAGMA table_info(_camera);")
        )
        columns = [row[1] for row in result.fetchall()]

        if 'send_email' not in columns:
            await conn.execute(
                text("ALTER TABLE _camera ADD COLUMN send_email INTEGER DEFAULT 0"),
            )
            logger.info("[INFO] Column send_email added.")
        else:
            logger.error("[ERROR] The column send_email already exists.")


if __name__ == "__main__":
    asyncio.run(add_column_cam_to_camera())
