import os


def get_absolute_logs_path():
    """Returns absolute path to logs directory."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def get_absolute_recordings_path(camera_id="1"):
    """Returns absolute path to camera recordings directory."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "media", "recordings", str(camera_id)
    )
