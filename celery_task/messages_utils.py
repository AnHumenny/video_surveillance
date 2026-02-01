import os
import smtplib
import time
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import httpx
import requests


def send_health_email(subject: str) -> str:
    """Send server health check email."""
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
            return f"Email sent to {recipient_email}"
    except Exception as e:
        return f"Error sending email: {e}"


def send_screenshot(cam_id, screenshot_path):
    """Send screenshot email - все в одной функции."""
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT") or 587)
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

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)

    return "Sent"


def get_telegram_config():
    """Get Telegram bot configuration."""
    return {
        'token': os.getenv("TELEGRAM_BOT_TOKEN"),
        'default_chat_id': os.getenv("TELEGRAM_CHAT_ID")  # если нужно
    }


def send_telegram_photo_service(cam_id: str, screenshot_path: str, chat_id: int) -> str:
    """Send photo to Telegram chat."""
    config = get_telegram_config()

    if not config['token']:
        return "TELEGRAM_BOT_TOKEN not found"

    url = f"https://api.telegram.org/bot{config['token']}/sendPhoto"
    caption = f"Движение на камере {cam_id} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"

    try:
        with open(screenshot_path, "rb") as photo_file:
            files = {"photo": photo_file}
            data = {"chat_id": chat_id, "caption": caption}
            response = httpx.post(url, data=data, files=files, timeout=5)

            if response.status_code == 200:
                return f"Photo sent to chat {chat_id}"
            else:
                return f"Telegram API error: {response.status_code}, {response.text}"

    except FileNotFoundError:
        return f"File not found: {screenshot_path}"
    except Exception as e:
        return f"Error sending photo: {e}"


def get_telegram_config_video():
    """Get Telegram bot configuration."""
    return {
        'token': os.getenv("TELEGRAM_BOT_TOKEN"),
        'video_delay': int(os.getenv("BOT_SEND_VIDEO", 5)) + 2,
        'timeout': int(os.getenv("BOT_SEND_VIDEO", 5)) + 3,
    }


def send_telegram_video_service(cam_id: str, video_path: str, chat_id: int) -> str:
    """Send video to Telegram chat."""
    config = get_telegram_config_video()

    if not config['token']:
        return "TELEGRAM_BOT_TOKEN not found"

    time.sleep(config['video_delay'])

    url = f"https://api.telegram.org/bot{config['token']}/sendVideo"
    caption = f"Движение на камере {cam_id} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"

    try:
        with open(video_path, "rb") as video_file:
            files = {"video": video_file}
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "supports_streaming": True
            }

            response = requests.post(url, data=data, files=files, timeout=config['timeout'])

            if response.status_code == 200:
                return f"Video sent to chat {chat_id}"
            else:
                return f"Telegram API error: {response.status_code}, {response.text}"

    except FileNotFoundError:
        return f"Video file not found: {video_path}"
    except Exception as e:
        return f"Error sending video: {e}"
