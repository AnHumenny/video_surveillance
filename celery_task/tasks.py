import shutil
import requests
import os
import smtplib
import time
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from celery_task.celery_app import celery
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from surveillance.schemas.repository import Repo, TaskCelery
import httpx
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

@celery.task(name="tasks.health_server")
def health_server(subject: str):
    """Celery task to send server health status notifications via email.

    This task sends a humorous health status email to notify administrators
    that the server is operational. It serves as both a heartbeat notification
    and a connectivity check for the email notification system.
    """

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL")

    message = "I report. The server, like Grandpa Lenin, is more alive than all the living. ;)"
    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            logger.info(f"[INFO] Healthcheck log file sent to {recipient_email}")
        return "Email sent successfully"
    except Exception as e:
        return f"Error sending email: {e}"


@celery.task(name="tasks.send_screenshot_email")
def send_screenshot_email(cam_id: str, screenshot_path: str):
    """Celery task to send motion detection screenshots via email.

    This task sends an email with a screenshot attachment when motion is detected
    on a camera. The email contains the screenshot as an attachment with a subject
    line indicating which camera detected motion.
    """

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT"))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL")

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = f"Motion detected on camera {cam_id}"

    with open(screenshot_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(screenshot_path)}",
        )
        msg.attach(part)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            logger.info(f"[TASK] Screenshot sent successfully to {recipient_email}")
        return "Screenshot sent successfully"
    except Exception as e:
        return f"Error sending screenshot: {e}"


@celery.task(name="tasks.send_telegram_photo")
def send_telegram_notification(cam_id: str, screenshot_path: str, chat_id: int) -> str:
    """Celery task to send video recordings to Telegram chat.

    This task sends a video file to a specified Telegram chat with movement
    detection notification. It includes a configurable delay before sending
    to ensure the video file is fully written and available.
    """

    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            return "TELEGRAM_BOT_TOKEN not found"

        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        caption = f"Движение на камере {cam_id} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"

        with open(screenshot_path, "rb") as photo_file:
            files = {"photo": photo_file}
            data = {"chat_id": chat_id, "caption": caption}
            response = httpx.post(url, data=data, files=files, timeout=5)

            if response.status_code == 200:
                return "Photo sent successfully"
            else:
                return f"Error: {response.status_code}, {response.text}"

    except Exception as e:
        return f"Exception when sending photos: {e}"


@celery.task(name="tasks.send_telegram_video")
def send_telegram_video(cam_id: str, video_path: str, chat_id: int) -> str:
    time.sleep(int(os.getenv("BOT_SEND_VIDEO")) + 2)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return "TELEGRAM_BOT_TOKEN not found"

    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    caption = f"Движение на камере {cam_id} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"

    try:
        with open(video_path, "rb") as video_file:
            files = {"video": video_file}
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "supports_streaming": True
            }

            response = requests.post(url, data=data, files=files, timeout=int(os.getenv("BOT_SEND_VIDEO")) + 3)

        if response.status_code == 200:
            return "Video sent successfully"
        else:
            return f"Error: {response.status_code}, {response.text}"

    except Exception as e:
        return f"Exception when sending video: {e}"


def get_absolute_recordings_path(camera_id="1"):
    """Constructs the absolute filesystem path to a camera's recordings directory."""

    current_file = os.path.abspath(__file__)
    logger.debug(f"Текущий файл: {current_file}")

    current_dir = os.path.dirname(current_file)
    logger.debug(f"Текущая папка (celery_task): {current_dir}")

    project_dir = os.path.dirname(current_dir)
    logger.debug(f"Папка проекта: {project_dir}")

    recordings_path = os.path.join(project_dir, "media", "recordings", str(camera_id))
    logger.debug(f"Путь к recordings камеры {camera_id}: {recordings_path}")

    return recordings_path


@celery.task
def delete_old_folders(camera_ids, days_threshold=7):        # добавить в интерфейс админки
    """Celery task to delete old recording folders for specified cameras.

    This task removes recording folders older than the specified threshold.
    It can accept camera IDs directly or automatically discover them from
    the recordings directory structure.

    Args:
        camera_ids (List[int/str] or None): List of camera IDs to process.
            If None or empty, the task will discover camera IDs from the
            recordings directory structure.
        days_threshold (int, optional): Number of days to keep recordings.
            Folders older than this threshold will be deleted. Defaults to 7.

    Returns:
        dict: Detailed results of the cleanup operation including:
            - success (bool): Whether operation completed without errors
            - threshold_date (str): Date threshold in 'YYYY-MM-DD' format
            - days_threshold (int): Days threshold used
            - camera_ids (List[str]): Camera IDs processed
            - deleted_folders (List[dict]): Details of deleted folders
            - deleted_count (int): Number of folders deleted
            - errors (List[str]): Error messages encountered
            - error_count (int): Number of errors
            - timestamp (str): ISO timestamp of completion
    """

    logger.info("=" * 50)
    logger.info(f"НАЧАЛО ОЧИСТКИ. Порог: {days_threshold} дней")

    if camera_ids is None:
        camera_ids = []
        base_file = os.path.abspath(__file__)
        base_dir = os.path.dirname(os.path.dirname(base_file))
        recordings_base = os.path.join(base_dir, "media", "recordings")

        if os.path.exists(recordings_base):
            for item in os.listdir(recordings_base):
                item_path = os.path.join(recordings_base, item)
                if os.path.isdir(item_path) and item.isdigit():
                    camera_ids.append(item)

    camera_ids = [str(cam_id) for cam_id in camera_ids if cam_id]

    if not camera_ids:
        logger.warning(f"Нет камер для обработки")
        return {"error": "No cameras found", "camera_ids": []}

    logger.info(f"Обрабатываем камеры: {camera_ids}")

    threshold_date = datetime.now() - timedelta(days=days_threshold)
    logger.info(f"Пороговая дата: {threshold_date.strftime('%Y-%m-%d')}")

    deleted_folders = []
    errors = []

    for camera_id in camera_ids:
        try:
            camera_id_str = str(camera_id).strip()

            camera_path = get_absolute_recordings_path(camera_id_str)
            logger.info(f"\nКамера {camera_id_str}: {camera_path}")

            if not os.path.exists(camera_path):
                error_msg = f"Папка камеры {camera_id_str} не существует: {camera_path}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

            try:
                items = os.listdir(camera_path)
            except PermissionError as e:
                error_msg = f"Нет доступа к папке камеры {camera_id_str}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

            logger.info(f"Найдено папок: {len(items)}")

            for folder_name in items:
                folder_path = os.path.join(camera_path, folder_name)

                if not os.path.isdir(folder_path):
                    continue

                try:
                    folder_date = datetime.strptime(folder_name, '%Y-%m-%d')

                    if folder_date < threshold_date:
                        logger.info(f"  УДАЛЯЕМ: {folder_name} (дата: {folder_date.date()})")

                        try:
                            shutil.rmtree(folder_path)
                            deleted_folders.append({
                                'camera_id': camera_id_str,
                                'folder_name': folder_name,
                                'folder_date': folder_date.strftime('%Y-%m-%d'),
                                'path': folder_path
                            })
                            logger.info(f"Папка удалена")
                        except Exception as e:
                            error_msg = f"Ошибка при удалении {folder_path}: {str(e)}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                    else:
                        logger.debug(f"ОСТАВЛЯЕМ: {folder_name} (дата: {folder_date.date()}, еще актуальна)")

                except ValueError:
                    logger.debug(f"ПРОПУСКАЕМ: {folder_name} (не формат даты)")
                    continue

        except Exception as e:
            error_msg = f"Ошибка при обработке камеры {camera_id}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    result = {
        'success': len(errors) == 0,
        'threshold_date': threshold_date.strftime('%Y-%m-%d'),
        'days_threshold': days_threshold,
        'camera_ids': camera_ids,
        'deleted_folders': deleted_folders,
        'deleted_count': len(deleted_folders),
        'errors': errors,
        'error_count': len(errors),
        'timestamp': datetime.now().isoformat()
    }

    logger.info("\n" + "=" * 50)
    logger.info("ИТОГИ ОЧИСТКИ:")
    logger.info(f"Удалено папок: {len(deleted_folders)}")
    logger.info(f"Ошибок: {len(errors)}")

    if deleted_folders:
        logger.info("Удаленные папки:")
        for folder in deleted_folders:
            logger.info(f"  • Камера {folder['camera_id']}: {folder['folder_name']}")

    if errors:
        logger.warning("Ошибки:")
        for error in errors:
            logger.warning(f"  • {error}")

    logger.info("=" * 50)

    return result


@celery.task
def cleanup_weekly():
    """Celery task for performing weekly cleanup of old recordings.

    This scheduled task runs weekly to clean up old camera recording folders.
    It retrieves all camera IDs from the database and triggers an asynchronous
    cleanup process for each camera.
    """

    camera_ids = TaskCelery.select_cameras_ids_sync()
    return delete_old_folders.delay(camera_ids=camera_ids, days_threshold=2)
