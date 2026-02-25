from quart import render_template
from surveillance.main import camera_manager
from surveillance.schemas.repository import Cameras, User


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


async def force_start_cam(cam_id):
    """Forcing the camera to start(bot)"""
    await camera_manager.reinitialize_camera(cam_id)
