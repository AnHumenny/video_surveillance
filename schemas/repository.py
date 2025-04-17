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

    #проверить
    @classmethod
    async def insert_new_camera(cls, items):
        """Inserts a new camera into the DBook table.

            Args:
                cls: Class reference (unused).
                items: Dictionary or list of dictionaries with book data to insert.

            Raises:
                Exception: If insertion fails, with rollback performed.
            """
        async with new_session() as session:
            async with session.begin():
                try:
                    q = insert(DCamera).values(items)
                    await session.execute(q)
                    await session.commit()
                    return
                except Exception as e:
                    await session.rollback()
                    raise e

    # проверить
    @classmethod
    async def drop_camera(cls, ssid):
        """Deletes a book record from the DCamera table by ID.

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
        ssid = int(ssid)
        async with new_session() as session:
            try:
                query = select(DCamera).where(DCamera.id == int(ssid))
                result = await session.execute(query)
                record = result.scalar_one_or_none()
                if record is None:
                    return f"Запись с указанным идентификатором {ssid} не найдена."
                delete_query = delete(DCamera).where(DCamera.id == int(ssid))
                await session.execute(delete_query)
                await session.commit()
                return f"Файл с указанным идентификатором {ssid} успешно удалён!"

            except (ValueError, NoResultFound, IntegrityError, SQLAlchemyError) as e:
                print("error", e)
                await session.rollback()
                return False
