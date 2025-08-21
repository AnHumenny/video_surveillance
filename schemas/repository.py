import logging
import sqlite3
import json
from typing import Any
from sqlalchemy import select, insert, delete, and_, update, Select
from sqlalchemy.exc import NoResultFound, IntegrityError, SQLAlchemyError
from schemas.database import DCamera, DUser, DFindCamera
import os
import re
from logs.logging_config import logger
from config.config import new_session, bot_session


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
    async def select_id_cameras(cls):
        """Select id cameras."""
        async with new_session() as session:
            q = select(DCamera.id)
            result = await session.execute(q)
            return result.scalars().all()

    @classmethod
    async def select_path_to_cam(cls, cam_id: int):
        """Select path_to_cam for a specific camera by ID."""
        async with new_session() as session:
            q = select(DCamera.path_to_cam).where(DCamera.id == cam_id)
            result = await session.execute(q)
            return result.scalar_one_or_none()


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
                return f"Route {cam_host} updated succesfully!"
            except IntegrityError as e:
                await session.rollback()
                logger.error(f"[ERROR] Error: route with adresses {cam_host} not updated", e)
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"[ERROR] Error: {e}")
                return e

    @classmethod
    async def update_coord(cls, cam_id, **kwargs):
        """Update coordinates camera"""
        async with new_session() as session:
            try:
                coordinate_x1 = kwargs.get("coordinate_x1")
                coordinate_y1 = kwargs.get("coordinate_y1")
                coordinate_x2 = kwargs.get("coordinate_x2")
                coordinate_y2 = kwargs.get("coordinate_y2")

                if any(x is None for x in [coordinate_x1, coordinate_y1, coordinate_x2, coordinate_y2]):
                    raise ValueError("The required coordinates are missing!")

                q = (
                    update(DCamera)
                    .where(DCamera.id == cam_id)
                    .values(
                        coordinate_x1=coordinate_x1,
                        coordinate_y1=coordinate_y1,
                        coordinate_x2=coordinate_x2,
                        coordinate_y2=coordinate_y2
                    )
                )
                await session.execute(q)
                await session.commit()
                return f"Coordinates {cam_id} updates succesfully!!"
            except IntegrityError as e:
                await session.rollback()
                logger.error(f"[ERROR] Error: coordinates {cam_id} not updated", e)
                return False
            except Exception as e:
                await session.rollback()
                logger.error(f"[ERROR] Error: {e}")
                return e

    @classmethod
    async def edit_camera(cls, ssid, path_to_cam, motion_detection, visible_camera, screen_cam,
                          send_mail, send_telegram, send_video_tg
                          ):
        """Edit path to camera.

            Args:
                cls: Class reference (unused).
                ssid: int
                path_to_cam: str
                motion_detection: bool
                visible_camera: bool
                screen_cam: bool
                send_mail: bool
                send_telegram: bool
                send_video_tg: bool
            """
        async with (new_session() as session):
            ssid = int(ssid)
            try:
                q = update(DCamera).where(DCamera.id == int(ssid)    # type: ignore
                                          ).values(path_to_cam=path_to_cam,
                                                   status_cam=motion_detection,
                                                   visible_cam=visible_camera,
                                                   screen_cam=screen_cam,
                                                   send_email=send_mail,
                                                   send_tg=send_telegram,
                                                   send_video_tg=send_video_tg,
                                                   )
                await session.execute(q)
                await session.commit()
                return f"Camera {ssid} updated succesfully!"
            except IntegrityError as e:
                await session.rollback()
                logger.error(f"[ERROR] Error: Camera with addresses {ssid} not updated", e)
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"[ERROR] Error: {e}")
                return e


    @classmethod
    async def select_all_cam(cls):
        """Select all cameras from the database.

        Args:
            cls: Class reference.

        Returns:
             List of DCamera instances.

        Raises:
            Exception: If database query fails.
        """
        async with new_session() as session:
            try:
                q = select(DCamera)
                result = await session.execute(q)
                cameras = result.scalars().all()
                return cameras
            except Exception as e:
                logger.error(f"[ERROR] Ошибка: {e}")
                raise e

    @classmethod
    async def select_cam_config(cls, ssid):
        """
        Select status_cam and screen from DCamera.
        Returns: dict with 'status_cam' and 'screen'.
        """
        async with new_session() as session:
            try:
                q = Select(
                    DCamera.status_cam, DCamera.screen_cam, DCamera.send_email, DCamera.send_tg,
                    DCamera.send_video_tg, ).where(DCamera.id == ssid, DCamera.visible_cam == True)
                result = await session.execute(q)
                row = result.first()
                if row:
                    return {"status_cam": row[0], "screen": row[1], "send_email": row[2], "send_tg": row[3]}
                return {"status_cam": False, "screen": False}
            except IntegrityError as e:
                logger.error(f"[ERROR] [DB ERROR] {e}")
                return {"status_cam": False, "screen": False}

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
                logger.error(f"[ERROR] Ошибка: {e}")
                raise e


    @classmethod
    async def add_new_cam(cls, new_cam, motion_detection, visible_cam, screen_cam, send_email, send_tg):
        """Inserts a new camera into the DCamera table.

            Args:
                cls: Class reference (unused).
                new_cam: str (e.g. rtsp://user:password@192.168.1.34:554/h265).

            Raises:
                Exception: If insertion fails, with rollback performed.
                :param path to new_cam: False or True (default == True)
                :param motion_detection: False or True (motion detection)
                :param screen_cam: False or True
                :param send_email: False or True
                :param visible_cam: False or True
                :param send_tg: False or True
            """
        async with new_session() as session:
            async with session.begin():
                try:
                    q = insert(DCamera).values(path_to_cam=new_cam,
                                               status_cam=motion_detection,
                                               visible_cam=visible_cam,
                                               screen_cam=screen_cam,
                                               send_email=send_email,
                                               send_tg=send_tg,
                                               )
                    await session.execute(q)
                    await session.commit()
                    return f"Камера {new_cam} успешно добавлена!"
                except IntegrityError as e:
                    await session.rollback()
                    logger.error(f"[ERROR] Ошибка: Камера с адресом {new_cam} уже существует", e)
                    return False
                except Exception as e:
                    await session.rollback()
                    logger.error(f"[ERROR] Ошибка: {e}")
                    return e

    @classmethod
    async def add_new_user(cls, user, password, status, tg_id, active):
        """Inserts a new user into the DUser table.

            Args:
                cls: Class reference (unused).
                user: str
                password: str (e.g. r'^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&+=])(?=S+$).{8,20}$').
                status: str
                tg_id: int
                active: bool

            Raises:
                Exception: If insertion fails, with rollback performed.
            """
        async with new_session() as session:
            async with session.begin():
                try:
                    q = insert(DUser).values(user=user, password=password, status=status,
                                             tg_id=int(tg_id), active=active)
                    await session.execute(q)
                    await session.commit()
                    return f"Пользователь {user} успешно добавлена!"
                except IntegrityError as e:
                    logger.error(f"[ERROR] Ошибка: {e}")
                    await session.rollback()
                    return False
                except Exception as e:
                    await session.rollback()
                    logger.error(f"[ERROR] Ошибка: {e}")
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
                logger.error("[ERROR]", e)
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
                logger.error("[ERROR]", e)
                await session.rollback()
                return False


    @staticmethod
    def select_all_cameras_to_json():
        """Синхронная выборка всех камер из таблицы _camera в формате JSON-словаря."""
        path_to_database = os.path.join(".", f"{os.getenv('DATABASE')}.db")
        try:
            conn = sqlite3.connect(path_to_database)
            cursor = conn.cursor()
            q = "SELECT id, path_to_cam, visible_cam FROM _camera WHERE visible_cam = True"
            cursor.execute(q)
            result = cursor.fetchall()
            json_result = {str(row[0]): row[1] for row in result}
            conn.close()
            return json.dumps(json_result, ensure_ascii=False)
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка базы данных: {e}")
            return json.dumps({})

    @staticmethod
    def reinit_camera(cam_id):
        """Синхронная выборка одной активной камеры по id, возвращает JSON."""
        path_to_database = os.path.join(".", f"{os.getenv('DATABASE')}.db")
        try:
            with sqlite3.connect(path_to_database) as conn:
                cursor = conn.cursor()
                query = """
                    SELECT id, path_to_cam, visible_cam
                    FROM _camera 
                    WHERE id = ? AND visible_cam = 1
                """
                cursor.execute(query, (cam_id,))
                result = cursor.fetchone()
                if result:
                    return json.dumps({
                        str(result[0]): result[1]
                    }, ensure_ascii=False)
                return json.dumps({})
        except sqlite3.Error as e:
            logger.error(f"[ERROR] Ошибка базы данных: {e}")
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

    @classmethod
    async def select_coordinates_by_id(cls, cam_id: int) -> list[Any] | list[tuple[int, ...]]:
        """Get alarm zone coordinates by camera ID.

            Args:
                cam_id (int): Camera ID.

            Returns:
                list[tuple(int, int)]: List of tuples of coordinates in the form (x, y), for example:
                [(230, 440), (485, 440), (230, 575), (485, 575)]
        """
        async with new_session() as session:
            try:
                q = select(
                    DCamera.coordinate_x1, DCamera.coordinate_x2,
                    DCamera.coordinate_y1, DCamera.coordinate_y2
                ).where(DCamera.id == cam_id)
                result = await session.execute(q)
                row = result.first()
                if row and all(row):
                    def parse(coord_str):
                        return tuple(map(int, coord_str.split(',')))
                    x1 = parse(row[0])
                    x2 = parse(row[1])
                    y1 = parse(row[2])
                    y2 = parse(row[3])
                    return [x1, x2, y1, y2]
                return []
            except Exception as e:
                logger.error(f"[ERROR] Failed to fetch coordinates: {e}")
                return []

    @classmethod
    async def get_allowed_chat_ids(cls) -> list[int]:
        """Select all users from DB where active is True"""
        async with bot_session() as session:
            result = await session.execute(
                select(DUser.tg_id).where(DUser.active == True)
            )
            return [row[0] for row in result.all() if row[0] is not None]


class Userbot:

    @classmethod
    async def auth_user_bot(cls, username, password):
        """Authenticates the user by username and password."""
        async with bot_session() as session:
            q = select(DUser).where(and_(DUser.user == username, DUser.password == password))
            result = await session.execute(q)
            answer = result.scalars().first()
            if answer is None:
                return None
            answer.active = 1
            await session.commit()
            return answer

    @classmethod
    async def movie_on(cls, cam_id):
        """Movie to TG ON"""
        async with bot_session() as session:
            try:
                query = (
                    update(DCamera)
                    .where(DCamera.id == int(cam_id))
                    .values(status_cam=True, send_video_tg=True)
                )
                await session.execute(query)
                await session.commit()
                return {"status": "ok", "message": f"Видео по камере {cam_id} включёно."}
            except Exception as e:
                await session.rollback()
                logging.error(f"Ошибка при запросе {cam_id}: {e}")
                raise

    @classmethod
    async def movie_off(cls, cam_id):
        """Movie to TG OFF"""
        async with bot_session() as session:
            try:
                query = (
                    update(DCamera)
                    .where(DCamera.id == int(cam_id))
                    .values(status_cam=False, send_video_tg=False)
                )
                await session.execute(query)
                await session.commit()
                return {"status": "ok", "message": f"Видео по камере {cam_id} отключёно."}
            except Exception as e:
                await session.rollback()
                logging.error(f"Ошибка при запросе {cam_id}: {e}")
                raise

    @classmethod
    async def screen_on(cls, cam_id: str) -> dict:
        """Screen to TG ON"""
        async with bot_session() as session:
            try:
                query = (
                    update(DCamera)
                    .where(DCamera.id == int(cam_id))
                    .values(status_cam=True, screen_cam=True, send_tg=True)
                )
                await session.execute(query)
                await session.commit()
                return {"status": "ok", "message": f"Скриншот по камере {cam_id} включён."}
            except Exception as e:
                await session.rollback()
                logging.error(f"Ошибка при запросе {cam_id}: {e}")
                raise

    @classmethod
    async def screen_off(cls, cam_id: str):
        """Screen to TG OFF"""
        async with bot_session() as session:
            try:
                query = (
                    update(DCamera)
                    .where(DCamera.id == int(cam_id))
                    .values(status_cam=False, screen_cam=False, send_tg=False)
                )
                await session.execute(query)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logging.error(f"Ошибка при запросе {cam_id}: {e}")
                raise

    @classmethod
    async def exit_user_bot(cls, tg_id):
        """Exit from bot."""
        async with bot_session() as session:
            q = select(DUser).where(and_(DUser.tg_id == tg_id))
            result = await session.execute(q)
            answer = result.scalars().first()
            if answer is None:
                return None
            answer.active = 0
            await session.commit()
            return answer