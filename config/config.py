import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
db_path = os.path.join(base_dir, f'{os.getenv("DATABASE")}.db')
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=True)
new_session = async_sessionmaker(engine, expire_on_commit=False)

# ALLOWED_CHAT_IDS = [int(s.strip()) for s in os.getenv("TELEGRAM_CHAT_RECIPIENT", "").split(",") if s.strip().isdigit()]
