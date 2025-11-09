import os
import asyncio
import hashlib
import time
from dotenv import load_dotenv
from sqlalchemy.future import select
from surveillance.schemas.database import Model, DUser, DFindCamera
from logs.logging_config import logger
from config.config import engine, new_session

load_dotenv()

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
    logger.info("[INFO] Tables successfully added or already exists!")


async def insert_into_user():
    """Adding a primary user"""
    async with new_session() as session:
        async with session.begin():
            user_info["tg_id"] = os.getenv("TELEGRAM_CHAT_ID")
            user_info["active"] = "1"
            stmt = select(DUser).where(DUser.user == user_info["user"])
            result = await session.execute(stmt)
            if result.scalar():
                logger.error(f"[ERROR] User {user_info['user']} already exist!")
                return
            session.add(DUser(**user_info))
            logger.info(f"[INFO] User {user_info['user']} added!")


async def insert_into_find_cam():
    """Adding a Primary Route Range to Search for Cameras"""
    async with new_session() as session:
        async with session.begin():
            stmt = select(DFindCamera).where(DFindCamera.cam_host == find_cam_info["cam_host"])
            result = await session.execute(stmt)
            if result.scalar():
                logger.error(f"[ERROR] Route {find_cam_info['cam_host']} already exist.")
                return
            session.add(DFindCamera(**find_cam_info))
            logger.info(f"[INFO] Route {find_cam_info} added!")


if __name__ == "__main__":
    asyncio.run(create_db())
    time.sleep(1)
    asyncio.run(insert_into_user())
    time.sleep(1)
    asyncio.run(insert_into_find_cam())
