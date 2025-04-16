from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Model(DeclarativeBase):
    """Base model"""
    id = Column(Integer, primary_key=True, autoincrement=True)


class DCamera(Model):
    """Represents a book in the database.

        Attributes:
            path_to_cam (str): path to camera ().

        Table:
            _camera: The database table name.
        """
    __tablename__ = "_camera"
    path_to_cam = Column(String(200), unique=True)


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
