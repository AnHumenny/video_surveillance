import asyncio
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


def run_async_task(coro):
    """Helper to run async code in sync context."""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(coro)
    loop.close()
    return result
