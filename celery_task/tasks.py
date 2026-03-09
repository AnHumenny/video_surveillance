import os
import sys
from celery_task.celery_app import celery
from celery_task.cleanup_service import delete_old_folders, delete_old_log_files
from celery_task.messages_utils import send_health_email, send_screenshot, send_telegram_photo_service, \
    send_telegram_video_service
from celery_task.path_utils import run_async_task
from surveillance.schemas.repository import OldFiles
from dotenv import load_dotenv
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logger = logging.getLogger(__name__)

load_dotenv()

@celery.task(name="tasks.health_server")
def health_server(subject: str):
    """Celery task for server health check."""
    logger.info(f"Sending health check: {subject}")
    result = send_health_email(subject)
    logger.info(f"Result: {result}")
    return result


@celery.task(name="tasks.send_screenshot_email")
def send_screenshot_email(cam_id: str, screenshot_path: str):
    """Celery task to send screenshots."""
    return send_screenshot(cam_id, screenshot_path)


@celery.task(name="tasks.send_telegram_photo")
def send_telegram_notification(cam_id: str, screenshot_path: str, chat_id: int) -> str:
    """Celery task to send photo to Telegram."""
    return send_telegram_photo_service(cam_id, screenshot_path, chat_id)


@celery.task(name="tasks.send_telegram_video")
def send_telegram_video(cam_id: str, video_path: str, chat_id: int) -> str:
    """Celery task to send video to Telegram."""
    return send_telegram_video_service(cam_id, video_path, chat_id)


@celery.task
def video_cleanup_weekly():
    """Celery task for performing weekly cleanup of old recordings."""

    cleanup_enabled = run_async_task(OldFiles.select_status_old_video())

    if not cleanup_enabled:
        logger.info("Weekly video cleanup is disabled")
        return {'success': True, 'skipped': True, 'reason': 'disabled'}

    logger.info("Weekly video cleanup started")
    return delete_old_folders()


@celery.task
def delete_logs_weekly():
    """Celery task for performing weekly cleanup of old logs."""

    logs_enabled = run_async_task(OldFiles.select_status_old_logs())

    if not logs_enabled:
        logger.info("Weekly logs cleanup is disabled")
        return {'success': True, 'skipped': True, 'reason': 'disabled'}

    logger.info("Weekly logs cleanup started")
    return delete_old_log_files()
