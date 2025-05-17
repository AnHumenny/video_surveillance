from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import DeclarativeBase


class Model(DeclarativeBase):
    """Base model"""
    id = Column(Integer, primary_key=True, autoincrement=True)


class DCamera(Model):
    """Represents a camera in the database.

        Attributes:
            path_to_cam (str): path to camera ().

        Table:
            _camera: The database table name.
        """
    __tablename__ = "_camera"
    path_to_cam = Column(String(200), unique=True)
    status_cam = Column(Boolean, nullable=False)


class DUser(Model):
    """Represents a user in the database.

        Attributes:
            user (str): Unique username of the user, max length 50 characters.
            password (str): Hashed password of the user, max length 100 characters.
            status (str): user status(admin, user).

        Table:
            user: The database table name.
        """
    __tablename__ = "_user"
    user = Column(String(50), unique=True)
    password = Column(String(100))
    status = Column(String(10))


class DFindCamera(Model):
    """Represents a rout for finding camera.

    Attributes:
            cam_host (str): Path for find (a.e. 192.168.0.1).
            subnet_mask (str): subnet mask (a.e. 24).

    Table:
        _find_camera: The database table name.
    """
    __tablename__ = "_find_camera"
    cam_host = Column(String(200))
    subnet_mask = Column(String(10))
