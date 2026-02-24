import re

PASSWORD_PATTERN = r"^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&+=])(?=\S+$).{8,20}$"

async def mask_rtsp_credentials(url: str) -> str:
    return re.sub(r'//(.*?):(.*?)@', r'//****:****@', url)


async def check_rtsp(path_to_cam):
    """checking camera on rtsp."""
    q = path_to_cam[0:4]
    if q != "rtsp":
        return False
    return True
