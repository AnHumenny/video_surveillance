import os
import smtplib
from email.mime.text import MIMEText
from celery_app import celery
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import httpx
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

@celery.task(name="tasks.health_server")
def health_server(subject: str):
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
def send_telegram_notification(cam_id: str, screenshot_path: str) -> str:
    from dotenv import load_dotenv
    load_dotenv()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logger.info("[TASK] Отсутствует токен или chat_id")
        return "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    caption = f"Движение зафиксировано на камере {cam_id}"

    try:
        with open(screenshot_path, "rb") as photo_file:
            files = {"photo": photo_file}
            data = {
                "chat_id": chat_id,
                "caption": caption
            }

            response = httpx.post(url, data=data, files=files, timeout=10)
            logger.info(f"[TASK] Telegram sendPhoto response: {response.status_code}, {response.text}")

            if response.status_code == 200:
                return "Photo sent successfully"
            else:
                return f"Failed to send photo: {response.status_code}, {response.text}"

    except Exception as e:
        logger.info(f"[TASK] Ошибка отправки фото: {e}")
        return f"Exception during Telegram sendPhoto: {e}"
