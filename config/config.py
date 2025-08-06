from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

import os
import logging

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
db_path = os.path.join(base_dir, f'{os.getenv("DATABASE")}.db')
bot_db_path = os.path.join(base_dir, f'{os.getenv("DATABASE")}.db')

logging.info(f"Global DB path: {db_path}")
logging.info(f"Bot DB path: {bot_db_path}")

engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=True)
engine_bot = create_async_engine(f"sqlite+aiosqlite:///{bot_db_path}", echo=True)

new_session = async_sessionmaker(engine, expire_on_commit=False)
bot_session = async_sessionmaker(engine_bot, expire_on_commit=False)