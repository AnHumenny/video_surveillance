import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy import insert, text, select
from sqlalchemy.exc import IntegrityError

from schemas.database import DCamera
from schemas.repository import Repo, new_session

load_dotenv()

db_name = os.getenv("DATABASE")
db_path = os.path.join("", f'{db_name}.db')
print(db_path)

if not os.path.exists(db_path):
    raise FileNotFoundError(f"База данных {db_path} не найдена. Убедитесь, что файл существует.")

async def main():
    async with new_session() as session:
        try:
            q = select(DCamera)
            result = await session.execute(q)
            cameras = result.scalars().all()
            print("Все камеры:", [x for x in cameras])
            for row in cameras:
                print(row.path_to_cam)
            return cameras
        except Exception as e:
            print(f"Ошибка: {e}")
            raise e

if __name__ == "__main__":
    asyncio.run(main())


# async def all_cameras():
#     try:
#         cameras = await Repo.select_cameras()
#         for row in cameras:
#             print(row.id, ":", row.path_to_cam)
#     except Exception as e:
#         print(f"Ошибка: {e}")

# async def all_users():
#     try:
#         users = await Repo.select_users()
#         for row in users:
#             print(row.id, ":", row.user, ":", row.password, ":", row.status)
#     except Exception as e:
#         print(f"Ошибка: {e}")


# new_cam = "rtsp://user:password@192.269.1.33:554/h265"
# async def main(path_to_cam: str):
#     print("Добавляем новую камеру", new_cam)
#     async with new_session() as session:
#         async with session.begin():
#             try:
#                 q = insert(DCamera).values(path_to_cam=new_cam)
#                 await session.execute(q)
#                 await session.commit()
#                 return f"Камера {new_cam} успешно добавлена!"
#             except IntegrityError as e:
#                 await session.rollback()
#                 print(f"Ошибка: Камера с адресом {new_cam} уже существует", e)
#                 return ValueError(f"Камера с адресом {new_cam} уже существует")
#             except Exception as e:
#                 await session.rollback()
#                 print(f"Ошибка: {e}")
#                 return e
