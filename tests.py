import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

db_name = os.getenv("DATABASE")
db_path = os.path.join("", f'{db_name}.db')
print(db_path)

if not os.path.exists(db_path):
    raise FileNotFoundError(f"База данных {db_path} не найдена. Убедитесь, что файл существует.")


async def main():
    pass

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