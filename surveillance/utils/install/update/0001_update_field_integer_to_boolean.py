import asyncio
import time
from sqlalchemy import inspect, text
from logs.logging_config import get_logger
from config.config import engine

logger = get_logger()


async def fix_send_video_tg_column():
    """Change send_video_tg column from INTEGER to BOOLEAN"""

    async with engine.begin() as conn:
        def table_exists(sync_conn):
            inspector = inspect(sync_conn)
            return '_camera' in inspector.get_table_names()

        exists = await conn.run_sync(table_exists)

        if not exists:
            logger.error("[ERROR] Table '_camera' does not exist!")
            return

        result = await conn.execute(text("PRAGMA table_info(_camera)"))
        columns = result.fetchall()

        send_video_tg_column = None
        for col in columns:
            if col[1] == 'send_video_tg':
                send_video_tg_column = col
                break

        if not send_video_tg_column:
            logger.error("[ERROR] Column 'send_video_tg' not found!")
            return

        current_type = send_video_tg_column[2].upper()
        logger.info(f"[INFO] Current column type: {current_type}")

        if current_type in ('BOOLEAN', 'BOOL'):
            logger.info("[INFO] Column already has correct type (BOOLEAN)")
            return

        logger.info("[INFO] Converting send_video_tg from INTEGER to BOOLEAN...")

        columns_info = []
        for col in columns:
            col_name = col[1]
            col_type = col[2]
            col_notnull = col[3]
            col_default = col[4]

            if col_name == 'send_video_tg':
                col_type = 'BOOLEAN'

            columns_info.append({
                'name': col_name,
                'type': col_type,
                'notnull': col_notnull,
                'default': col_default
            })

        create_stmt = "CREATE TABLE _camera_new ("
        col_defs = []
        for col in columns_info:
            col_def = f'"{col["name"]}" {col["type"]}'
            if col['notnull']:
                col_def += " NOT NULL"
            if col['default']:
                col_def += f" DEFAULT {col['default']}"
            col_defs.append(col_def)

        create_stmt += ", ".join(col_defs) + ", PRIMARY KEY (id))"

        await conn.execute(text("BEGIN TRANSACTION"))

        try:
            await conn.execute(text(create_stmt))
            logger.info("[INFO] Created temporary table _camera_new")

            old_cols = [f'"{col["name"]}"' for col in columns_info]
            new_cols = old_cols.copy()

            copy_stmt = f"""
                INSERT INTO _camera_new ({', '.join(old_cols)})
                SELECT {', '.join(new_cols)} FROM _camera
            """
            await conn.execute(text(copy_stmt))
            logger.info("[INFO] Copied data to new table")

            await conn.execute(text("DROP TABLE _camera"))
            await conn.execute(text("ALTER TABLE _camera_new RENAME TO _camera"))

            await conn.execute(text("COMMIT"))
            logger.info("[INFO] Successfully converted send_video_tg to BOOLEAN")

        except Exception as e:
            await conn.execute(text("ROLLBACK"))
            logger.error(f"[ERROR] Failed to convert column: {e}")
            raise


async def verify_fix():
    """Verify that column was fixed correctly"""

    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(_camera)"))
        columns = result.fetchall()

        logger.info("[INFO] Current _camera table structure:")
        send_video_tg_found = False
        for col in columns:
            col_name = col[1]
            col_type = col[2]
            logger.info(f"  - {col_name} ({col_type})")

            if col_name == 'send_video_tg':
                send_video_tg_found = True
                if col_type.upper() in ('BOOLEAN', 'BOOL'):
                    logger.info("[INFO] ✓ send_video_tg has correct type (BOOLEAN)")
                else:
                    logger.error(f"[ERROR] send_video_tg still has type {col_type}")

        if not send_video_tg_found:
            logger.error("[ERROR] send_video_tg column not found!")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Fixing send_video_tg column type (INTEGER -> BOOLEAN)")
    logger.info("=" * 60)

    asyncio.run(fix_send_video_tg_column())
    time.sleep(1)
    asyncio.run(verify_fix())

    logger.info("=" * 60)
    logger.info("Done!")
    logger.info("=" * 60)
