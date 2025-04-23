import sqlite3
import json
from sqlalchemy import select, insert, delete, and_
from sqlalchemy.exc import NoResultFound, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from schemas.database import DCamera, DUser
import os
from dotenv import load_dotenv
load_dotenv()

db_name = os.getenv("DATABASE")
db_path = os.path.join(f'{db_name}.db')

engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=True)
new_session = async_sessionmaker(engine, expire_on_commit=False)

class Repo:

    @classmethod
    async def auth_user(cls, username, password):
        """Checks if a user exists with the given username and password.

            Args:
                cls: Class reference (unused).
                username (str): Username to check.
                password (str): Password to check (expected to be hashed).

            Returns:
               bool: True if user exists with matching credentials, None if not found.

            Raises:
                SQLAlchemyError: If query execution fails.
                Exception: For unexpected errors.
            """
        async with new_session() as session:
            q = select(DUser).where(and_(DUser.user == username, DUser.password == password))
            result = await session.execute(q)
            answer = result.scalar()
            if answer is None:
                return None
            return answer

    @classmethod
    async def select_users(cls):
        """Select all users.

            Args:
                cls: Class reference (unused).

            Returns:
                list of value: str

            Raises:
                SQLAlchemyError: If query execution fails.
                Exception: For unexpected errors.
            """
        async with new_session() as session:
            q = select(DUser)
            result = await session.execute(q)
            return result.scalars().all()

    @classmethod
    async def select_cameras(cls):
        """Select all cameras.

            Args:
                cls: Class reference (unused).

            Returns:
                list of value: str

            Raises:
                SQLAlchemyError: If query execution fails.
                Exception: For unexpected errors.
            """
        async with new_session() as session:
            q = select(DCamera)
            result = await session.execute(q)
            return result.scalars().all()

    @classmethod
    async def select_all_cam(cls):
        """Select all cameras from database.

            Args:
                cls: Class reference (unused).

            Raises:
                Exception: If insertion fails, with rollback performed.
            """
        async with new_session() as session:
            try:
                q = select(DCamera)
                result = await session.execute(q)
                cameras = result.scalars().all()
                return cameras
            except Exception as e:
                print(f"Ошибка: {e}")
                raise e

    @classmethod
    async def select_all_users(cls):
        """Select all users from database, returning only id and user fields.

        Args:
            cls: Class reference (unused).

        Returns:
            List of tuples containing (id, user) for each user.

        Raises:
            Exception: If query fails, with rollback performed.
        """
        async with new_session() as session:
            try:
                q = select(DUser.id, DUser.user)
                result = await session.execute(q)
                users = result.all()
                return users
            except Exception as e:
                print(f"Ошибка: {e}")
                raise e


    @classmethod
    async def add_new_cam(cls, new_cam):
        """Inserts a new camera into the DCamera table.

            Args:
                cls: Class reference (unused).
                new_cam: str (e.g. rtsp://user:password@192.168.1.34:554/h265).

            Raises:
                Exception: If insertion fails, with rollback performed.
            """
        print("Добавляем новую камеру", new_cam)
        async with new_session() as session:
            async with session.begin():
                try:
                    q = insert(DCamera).values(path_to_cam=new_cam)
                    await session.execute(q)
                    await session.commit()
                    return f"Камера {new_cam} успешно добавлена!"
                except IntegrityError as e:
                    await session.rollback()
                    print(f"Ошибка: Камера с адресом {new_cam} уже существует", e)
                    return False
                except Exception as e:
                    await session.rollback()
                    print(f"Ошибка: {e}")
                    return e

    @classmethod
    async def add_new_user(cls, user, password):
        """Inserts a new user into the DUser table.

            Args:
                cls: Class reference (unused).
                user: str
                password: str (e.g. r'^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&+=])(?=S+$).{8,20}$').

            Raises:
                Exception: If insertion fails, with rollback performed.
            """
        async with new_session() as session:
            async with session.begin():
                try:
                    q = insert(DUser).values(user=user, password=password)
                    await session.execute(q)
                    await session.commit()
                    return f"Пользователь {user} успешно добавлена!"
                except IntegrityError as e:
                    print(f"Ошибка: {e}")
                    await session.rollback()
                    return False
                except Exception as e:
                    await session.rollback()
                    print(f"Ошибка: {e}")
                    return e


    @classmethod
    async def drop_camera(cls, ssid):
        """Deletes a camera record from the DCamera table by ID.

            Args:
                cls: Class reference (unused).
                ssid: ID of the camera record to delete (converted to int).

            Returns:
                str: Success message if deletion succeeds, error message if record not found,
                     False if an exception occurs.

            Raises:
                ValueError: If ssid cannot be converted to an integer.
                NoResultFound: If no record matches the given ID.
                IntegrityError: If deletion violates database constraints.
                SQLAlchemyError: If other database errors occur.
            """
        async with new_session() as session:
            ssid = int(ssid)
            try:
                query = select(DCamera).where(DCamera.id == int(ssid)) # type: ignore
                result = await session.execute(query)
                record = result.scalar_one_or_none()
                if record is None:
                    return f"Камера с указанным идентификатором {ssid} не найдена."
                delete_query = delete(DCamera).where(DCamera.id == int(ssid))  # type: ignore
                await session.execute(delete_query)
                await session.commit()
                return f"Камера с идентификатором {ssid} успешно удалёна!"
            except (ValueError, NoResultFound, IntegrityError, SQLAlchemyError) as e:
                print("error", e)
                await session.rollback()
                return False

    @classmethod
    async def drop_user(cls, ssid):
        """Deletes a user record from the DUser table by ID.

            Args:
                cls: Class reference (unused).
                ssid: ID of the user record to delete (converted to int).

            Returns:
                str: Success message if deletion succeeds, error message if record not found,
                     False if an exception occurs.

            Raises:
                ValueError: If ssid cannot be converted to an integer.
                NoResultFound: If no record matches the given ID.
                IntegrityError: If deletion violates database constraints.
                SQLAlchemyError: If other database errors occur.
            """
        async with new_session() as session:
            ssid = int(ssid)
            try:
                query = select(DUser).where(DUser.id == int(ssid))  # type: ignore
                result = await session.execute(query)
                record = result.scalar_one_or_none()
                if record is None:
                    return f"Пользователь с указанным идентификатором {ssid} не найдена."
                delete_query = delete(DUser).where(DUser.id == int(ssid))  # type: ignore
                await session.execute(delete_query)
                await session.commit()
                return f"Пользователь с идентификатором {ssid} успешно удалёна!"
            except (ValueError, NoResultFound, IntegrityError, SQLAlchemyError) as e:
                print("error", e)
                await session.rollback()
                return False


    @staticmethod
    def select_all_cameras_to_json():
        """Синхронная выборка всех камер из таблицы _camera в формате JSON-словаря."""
        path_to_database = os.path.join(".", f"{os.getenv('DATABASE')}.db")
        try:
            conn = sqlite3.connect(path_to_database)
            cursor = conn.cursor()
            q = "SELECT id, path_to_cam FROM _camera"
            cursor.execute(q)
            result = cursor.fetchall()
            json_result = {str(row[0]): row[1] for row in result}
            conn.close()
            return json.dumps(json_result, ensure_ascii=False)
        except sqlite3.Error as e:
            print(f"Ошибка базы данных: {e}")
            return json.dumps({})
