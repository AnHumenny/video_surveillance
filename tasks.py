import requests
import os
import smtplib
import time
from email.mime.text import MIMEText
from datetime import datetime
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
def send_telegram_notification(cam_id: str, screenshot_path: str, chat_id: int) -> str:
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

            response = requests.post(url, data=data, files=files, timeout=int(os.getenv("BOT_SEND_VIDEO")) + 4)

        if response.status_code == 200:
            return "Video sent successfully"
        else:
            return f"Error: {response.status_code}, {response.text}"

    except Exception as e:
        return f"Exception when sending video: {e}"
