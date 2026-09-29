from logs.logging_config import get_logger
from surveillance import state

logger = get_logger()


async def cleanup():
    """Gracefully shut down the camera manager."""
    logger.info("[INFO] Application cleanup started")

    if state.camera_manager is not None:
        try:
            await state.camera_manager.shutdown()
        except Exception as e:
            logger.error(
                f"[ERROR] CameraManager shutdown failed: {e}",
                exc_info=True,
            )

    logger.info("[INFO] Application cleanup finished")
