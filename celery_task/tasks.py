from celery_task.celery_app import celery
from celery_task.cleanup_service import delete_old_folders, delete_old_log_files
from celery_task.messages_utils import send_health_email, send_screenshot, send_telegram_photo_service, \
    send_telegram_video_service
from surveillance.schemas.repository import TaskCelery
from dotenv import load_dotenv
import logging

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
def video_cleanup_weekly():                  # добавить в интерфейс админки
    """Celery task for performing weekly cleanup of old recordings."""
    # bool да/нет из админки
    return delete_old_folders()


@celery.task
def delete_logs_weekly():             # добавить в интерфейс админки
    """Celery task for performing weekly cleanup of old logs. """
    # bool да/нет из админки
    delete_old_log_files()
