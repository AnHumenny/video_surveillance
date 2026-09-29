import os
from hypercorn.config import Config
from hypercorn.asyncio import serve
import asyncio
from quart import Quart
import signal

from surveillance import state
from logs.logging_config import get_logger

from surveillance.routes.auth import auth_bp
from surveillance.routes.cameras import cameras_bp
from surveillance.routes.control import control_bp
from surveillance.routes.api import api_bp

from surveillance.cleanup import cleanup

logger = get_logger()

logger.info(f"MAIN MODULE LOADED - PID: {os.getpid()} - PROCESS: {os.getpid()}")

script_dir = os.path.dirname(os.path.abspath(__file__))

os.environ[
    "OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|buffer_size;4194304|timeout;10000000|flags;discardcorrupt"

app = Quart(__name__)
app.secret_key = os.urandom(24)

app.template_folder = "templates"


@app.before_serving
async def setup_camera_manager():
    if not state.camera_manager:
        return

    await state.camera_manager.initialize()

shutdown_event = asyncio.Event()

app.register_blueprint(auth_bp)
app.register_blueprint(cameras_bp)
app.register_blueprint(control_bp)
app.register_blueprint(api_bp)


def _request_shutdown():
    """Signal-safe helper to set the shutdown event."""
    shutdown_event.set()

async def handle_shutdown():
    """signal handler for application shutdown."""
    _request_shutdown()


async def shutdown_trigger():
    """awaitable shutdown trigger for Hypercorn."""
    await shutdown_event.wait()
    logger.info("[INFO] Shutdown signal received, Hypercorn exiting...")


async def main(host: str, port: int, debug: bool = False):
    config = Config()
    config.bind = [f"{host}:{port}"]
    config.debug = debug

    success = await state.camera_manager.load_camera_configs()
    if success:
        await state.camera_manager.initialize()
    else:
        logger.info("Cameras not initialized, app continues to launch.")

    try:
        await serve(app, config, shutdown_trigger=shutdown_trigger)
    finally:
        await cleanup()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _on_signal():
        try:
            loop.call_soon_threadsafe(_request_shutdown)
        except RuntimeError:
            _request_shutdown()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _request_shutdown)
            except (NotImplementedError, RuntimeError):
                signal.signal(sig, _on_signal)
    except (NotImplementedError, RuntimeError) as e:
        logger.warning(f"[WARNING] Could not set signal handler: {e}")

    try:
        loop.run_until_complete(
            main(
                host=os.getenv('HOST', '0.0.0.0'),
                port=int(os.getenv("PORT", 8080))
            )
        )
    except KeyboardInterrupt:
        logger.info("[INFO] Received interrupt signal")
        _request_shutdown()
    except Exception as e:
        logger.error(f"[ERROR] Application error: {e}")
    finally:
        try:
            loop.run_until_complete(cleanup())
        except Exception as e:
            logger.error(f"[ERROR] Cleanup error: {e}")
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                logger.info("[INFO] Cancelling pending tasks")
                for task in pending:
                    task.cancel()
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        finally:
            loop.close()
            logger.info("[INFO] Event loop closed")
