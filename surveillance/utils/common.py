import re
from quart import render_template
from surveillance.schemas.repository import Cameras, User


def mask_rtsp_credentials(url: str) -> str:
    return re.sub(r'//(.*?):(.*?)@', r'//****:****@', url)


async def check_rtsp(path_to_cam):
    """checking camera on rtsp."""
    q = path_to_cam[0:4]
    if q != "rtsp":
        return False
    return True


async def list_all_cameras():
    """list of all cameras."""
    q = await Cameras.select_all_cam()
    if not q:
        return {"message": "Камер не найдено!"}
    return await render_template('control.html', status='admin')


async def select_all_users():
    """list of all users"""
    q = User.select_all_users()
    return q


PASSWORD_PATTERN = r"^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&+=])(?=\S+$).{8,20}$"
