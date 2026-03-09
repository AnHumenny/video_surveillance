from sqlalchemy import Column, Integer, String, Boolean, BigInteger
from sqlalchemy.orm import DeclarativeBase


class Model(DeclarativeBase):
    """Base model"""
    id = Column(Integer, primary_key=True, autoincrement=True)


class DCamera(Model):
    """Represents a camera in the database.

    Attributes:
        path_to_cam (str): path to camera.
        status_cam (bool): camera status (online/offline)
        visible_cam (bool): camera visibility in interface
        screen_cam (bool): screen capture enabled
        send_email (bool): send alerts via email
        send_tg (bool): send alerts via Telegram
        send_video_tg (bool): send video via Telegram
        coordinate_x1 (str): first X coordinate for detection zone
        coordinate_x2 (str): second X coordinate for detection zone
        coordinate_y1 (str): first Y coordinate for detection zone
        coordinate_y2 (str): second Y coordinate for detection zone
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


class DOperationOldFiles(Model):
    """Represents a camera in the database.

        Attributes:
            weekly_recordings_cleanup (bool): automatic weekly cleanup of recordings
            old_logs_cleanup (bool): automatic cleanup of old logs
        """

    __tablename__ = "_old_files"
    weekly_recordings_cleanup = Column(Boolean, nullable=False, default=False)
    old_logs_cleanup = Column(Boolean, nullable=False, default=False)
