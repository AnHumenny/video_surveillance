import asyncio
import time
from sqlalchemy import inspect, text
from logs.logging_config import get_logger
from config.config import engine

logger = get_logger()


async def create_old_files_table():
    """Create _old_files table if it doesn't exist"""
    async with engine.begin() as conn:
        def table_exists(sync_conn):
            inspector = inspect(sync_conn)
            return '_old_files' in inspector.get_table_names()

        exists = await conn.run_sync(table_exists)

        if exists:
            logger.info("[INFO] Table '_old_files' already exists!")
            return

        await conn.execute(text("""
            CREATE TABLE _old_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weekly_recordings_cleanup BOOLEAN NOT NULL DEFAULT 0,
                old_logs_cleanup BOOLEAN NOT NULL DEFAULT 0
            )
        """))

        await conn.execute(text("""
            INSERT INTO _old_files (weekly_recordings_cleanup, old_logs_cleanup) 
            VALUES (0, 0)
        """))

        logger.info("[INFO] Table '_old_files' created successfully with default values!")


async def verify_table():
    """Verify that table was created correctly"""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='_old_files'"))
        row = result.first()

        if row:
            logger.info("[INFO] Table '_old_files' exists")

            result = await conn.execute(text("PRAGMA table_info(_old_files)"))
            columns = result.fetchall()
            logger.info("[INFO] Table structure:")
            for col in columns:
                logger.info(f"  - {col[1]} ({col[2]})")

            result = await conn.execute(text("SELECT COUNT(*) FROM _old_files"))
            count = result.scalar()
            logger.info(f"[INFO] Records in table: {count}")
        else:
            logger.error("[ERROR] Table '_old_files' was not created!")


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Creating _old_files table...")
    logger.info("=" * 50)

    asyncio.run(create_old_files_table())
    time.sleep(1)
    asyncio.run(verify_table())

    logger.info("=" * 50)
    logger.info("Done!")
    logger.info("=" * 50)
