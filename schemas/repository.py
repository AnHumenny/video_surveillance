import sqlite3
import json
from sqlalchemy import select, insert, delete, and_, update, Select
from sqlalchemy.exc import NoResultFound, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from schemas.database import DCamera, DUser, DFindCamera
import os
import re
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
    async def select_ip_cameras(cls):
        """Select field ip from cameras.

            Args:
                cls: Class reference (unused).

            Returns:
                list of value: str (a.e. 192.168.0.1)

            Raises:
                SQLAlchemyError: If query execution fails.
                Exception: For unexpected errors.
            """
        try:
            async with new_session() as session:
                q = select(DCamera.path_to_cam)
                result = await session.execute(q)
                paths = result.scalars().all()

                ip_addresses = set()
                for path in paths:
                    if path:
                        match = re.search(r'@([^/]+/[^/]+)', path)
                        if match:
                            ip_addresses.add(match.group(1).split('/')[0])
                        else:
                            ip_addresses.add(None)
                    else:
                        ip_addresses.add(None)
                return ip_addresses

        except SQLAlchemyError as e:
            raise SQLAlchemyError(f"Database query failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")

    @classmethod
    async def select_find_cam(cls):
        """Select from _find_camera.

            Args:
                cls: Class reference (unused).

            Returns:
                answer: str

            Raises:
                SQLAlchemyError: If query execution fails.
                Exception: For unexpected errors.
            """
        async with new_session() as session:
            q = select(DFindCamera.cam_host, DFindCamera.subnet_mask)
            result = await session.execute(q)
            answer = ','.join(f"{row.cam_host}/{row.subnet_mask}" for row in result)
            return answer if answer else None

    @classmethod
    async def update_find_camera(cls, cam_host, subnet_mask):
        """Edit find_to_camera.

            Args:
                cls: Class reference (unused).
                cam_host: str
                subnet_mask: bool

            Returns:
                200 if ok

            """
        async with (new_session() as session):
            try:
                q = update(DFindCamera).where(DFindCamera.id == 1  # type: ignore
                                          ).values(cam_host=cam_host, subnet_mask=subnet_mask)
                await session.execute(q)
                await session.commit()
                return f"Роут {cam_host} успешно обновлен!"
            except IntegrityError as e:
                await session.rollback()
                print(f"Ошибка: Роут с адресом {cam_host} не обновился", e)
                return False

            except Exception as e:
                await session.rollback()
                print(f"Ошибка: {e}")
                return e



    @classmethod
    async def edit_camera(cls, ssid, path_to_cam, motion_detection):
        """Edit path to camera.

            Args:
                cls: Class reference (unused).
                ssid: int
                path_to_cam: str
                motion_detection: bool

            Returns:
                200 if ok

            """
        async with (new_session() as session):
            ssid = int(ssid)
            try:
                q = update(DCamera).where(DCamera.id == int(ssid)    # type: ignore
                                          ).values(path_to_cam=path_to_cam, status_cam=motion_detection)
                await session.execute(q)
                await session.commit()
                return f"Камера {ssid} успешно обновлена!"
            except IntegrityError as e:
                await session.rollback()
                print(f"Ошибка: Камера с адресом {ssid} не обновилась", e)
                return False

            except Exception as e:
                await session.rollback()
                print(f"Ошибка: {e}")
                return e


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
    async def select_bool_cam(cls, ssid):
        """Select status_cam from status_cam, returning 1 or 0."""
        async with new_session() as session:
            try:
                q = Select(DCamera.status_cam).where(DCamera.id == ssid)   # type: ignore
                result = await session.execute(q)
                answer = result.scalar()
                return answer
            except IntegrityError as e:
                return e


    @classmethod
    async def select_all_users(cls):
        """Select all users from database, returning id, user, status fields.

        Args:
            cls: Class reference (unused).

        Returns:
            List of tuples containing (id, user, status) for each user.

        Raises:
            Exception: If query fails, with rollback performed.
        """
        async with new_session() as session:
            try:
                q = select(DUser.id, DUser.user, DUser.status)
                result = await session.execute(q)
                users = result.all()
                return users
            except Exception as e:
                print(f"Ошибка: {e}")
                raise e


    @classmethod
    async def add_new_cam(cls, new_cam, motion_detection):
        """Inserts a new camera into the DCamera table.

            Args:
                cls: Class reference (unused).
                new_cam: str (e.g. rtsp://user:password@192.168.1.34:554/h265).

            Raises:
                Exception: If insertion fails, with rollback performed.
                :param path to new_cam:
                :param motion_detection: False or True (motion detection)
            """
        async with new_session() as session:
            async with session.begin():
                try:
                    q = insert(DCamera).values(path_to_cam=new_cam, status_cam=motion_detection)
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
    async def add_new_user(cls, user, password, status):
        """Inserts a new user into the DUser table.

            Args:
                cls: Class reference (unused).
                user: str
                password: str (e.g. r'^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&+=])(?=S+$).{8,20}$').
                status: str

            Raises:
                Exception: If insertion fails, with rollback performed.
            """
        async with new_session() as session:
            async with session.begin():
                try:
                    q = insert(DUser).values(user=user, password=password, status=status)
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

    @classmethod
    async def check_cam(cls, check_cam):
        """Check path_to_cam if not exist in DCamera.

            Args:
                cls: Class reference (unused).
                check_cam: str (e.g. rtsp://user:password@192.168.1.34:554/h265).
            """
        async with new_session() as session:
            async with session.begin():
                try:
                    q = select(DCamera).where(path_to_cam=check_cam)
                    if q is None:
                        return False
                    return True
                except ValueError as e:
                    return e
