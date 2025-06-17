import os
import asyncio
import hashlib
import time
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from schemas.database import Model, DUser, DFindCamera

load_dotenv()

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
db_path = os.path.join(base_dir, f'{os.getenv("DATABASE")}.db')
engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=True)
new_session = async_sessionmaker(engine, expire_on_commit=False)

password = hashlib.sha256(os.getenv("PASSWORD").encode()).hexdigest()
user_info = {
    "user": os.getenv("ADMIN"),
    "password": password,
    "status": "admin"
}
find_cam_info = {
    "cam_host": os.getenv("CAM_HOST"),
    "subnet_mask": os.getenv("SUBNET_MASK")
}


async def create_db():
    """Create a database and tables (if they do not exist)"""
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)
    print("[INFO] Таблицы успешно созданы или уже существуют.")

async def insert_into_user():
    """Adding a primary user"""
    async with new_session() as session:
        async with session.begin():
            stmt = select(DUser).where(DUser.user == user_info["user"])
            result = await session.execute(stmt)
            if result.scalar():
                print(f"[INFO] Пользователь {user_info['user']} уже существует.")
                return
            session.add(DUser(**user_info))
            print(f"[INFO] Пользователь {user_info['user']} добавлен!")


async def insert_into_find_cam():
    """Adding a Primary Route Range to Search for Cameras"""
    async with new_session() as session:
        async with session.begin():
            stmt = select(DFindCamera).where(DFindCamera.cam_host == find_cam_info["cam_host"])
            result = await session.execute(stmt)
            if result.scalar():
                print(f"[INFO] Маршрут {find_cam_info['cam_host']} уже существует.")
                return
            session.add(DFindCamera(**find_cam_info))
            print(f"[INFO] Маршрут {find_cam_info} добавлен!")

if __name__ == "__main__":
    asyncio.run(create_db())
    time.sleep(1)
    asyncio.run(insert_into_user())
    time.sleep(1)
    asyncio.run(insert_into_find_cam())
