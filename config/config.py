from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import os
from logs.logging_config import get_logger
logger = get_logger()

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
db_path = os.path.join(base_dir, f'{os.getenv("DATABASE")}.db')

logger.info(f"Database path: {db_path}")

engine = create_async_engine(
    f"sqlite+aiosqlite:///{db_path}",
    echo=False,
    connect_args={"check_same_thread": False}
)

new_session = async_sessionmaker(engine, expire_on_commit=False)
