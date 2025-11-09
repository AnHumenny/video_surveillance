from sqlalchemy import Column, Integer, String, Boolean, BigInteger
from sqlalchemy.orm import DeclarativeBase


class Model(DeclarativeBase):
    """Base model"""
    id = Column(Integer, primary_key=True, autoincrement=True)


class DCamera(Model):
    """Represents a camera in the database.

        Attributes:
            path_to_cam (str): path to camera ().

        """
    __tablename__ = "_camera"
    path_to_cam = Column(String(200), unique=True)
    status_cam = Column(Boolean, nullable=False)
    visible_cam = Column(Boolean, nullable=True)
    screen_cam = Column(Boolean, nullable=False)
    send_email = Column(Boolean, nullable=False)
    send_tg = Column(Boolean, nullable=False)
    send_video_tg = Column(Boolean, nullable=False)
    coordinate_x1 = Column(String(12), default="0, 0")
    coordinate_x2 = Column(String(12), default="0, 0")
    coordinate_y1 = Column(String(12), default="0, 0")
    coordinate_y2 = Column(String(12), default="0, 0")


class DUser(Model):
    """Represents a user in the database.

        Attributes:
            user (str): Unique username of the user, max length 50 characters.
            password (str): Hashed password of the user, max length 100 characters.
            status (str): user status(admin, user).
            tg_id (int): users TG-ID
            active (int): users status authorization in tg-bot

        """
    __tablename__ = "_user"
    user = Column(String(50), unique=True)
    password = Column(String(100))
    status = Column(String(10))
    tg_id = Column(BigInteger, unique=True, nullable=True, default=0)
    active = Column(Integer, default=0)


class DFindCamera(Model):
    """Represents a rout for finding camera.

    Attributes:
            cam_host (str): Path for find (a.e. 192.168.0.1).
            subnet_mask (str): subnet mask (a.e. 24).

    """
    __tablename__ = "_find_camera"
    cam_host = Column(String(200))
    subnet_mask = Column(String(10))
