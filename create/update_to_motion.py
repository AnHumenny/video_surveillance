import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

load_dotenv()

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
db_path = os.path.join(base_dir, f'{os.getenv("DATABASE")}.db')
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=True)
new_session = async_sessionmaker(engine, expire_on_commit=False)

from sqlalchemy import text

async def add_column_screen_cam_to_camera():
    async with engine.begin() as conn:
        result = await conn.execute(
            text("PRAGMA table_info(_camera);")
        )
        columns = [row[1] for row in result]

        if 'new_column_name' not in columns:
            await conn.execute(
                text("ALTER TABLE _camera ADD COLUMN screen_cam INTEGER DEFAULT 0")
            )
            print("Column added.")
        else:
            print("The column already exists.")

if __name__ == "__main__":
    asyncio.run(add_column_screen_cam_to_camera())
