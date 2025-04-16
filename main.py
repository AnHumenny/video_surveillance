import hashlib
import cv2
import os
import time
import asyncio
import json
from quart import Quart, Response, render_template, request, redirect, jsonify, url_for, session
import signal
import sys
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature, BadData
from dotenv import load_dotenv
from schemas.repository import Repo

load_dotenv()

os.environ[
    "OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|buffer_size;4194304|timeout;10000000|flags;discardcorrupt"

app = Quart(__name__)
app.secret_key = os.urandom(24)
serializer = URLSafeTimedSerializer(app.secret_key)

app.template_folder = "templates"

class CameraManager:
    def __init__(self):
        """инициализация класса"""
        camera_config_json = os.getenv("CAMERA_CONFIG")
        if not camera_config_json:
            raise ValueError("CAMERA_CONFIG не найден в .env")

        try:
            self.camera_configs = json.loads(camera_config_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка парсинга CAMERA_CONFIG: {e}")

        print("Конфигурация камер:")
        for cam_id, url in self.camera_configs.items():
            print(f"Камера {cam_id}: {url}")

        self.cameras = {}
        self._initialize_cameras()

    def _initialize_cameras(self):
        """инициализация камеры"""
        for cam_id, url in self.camera_configs.items():
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                print(f"Не удалось открыть камеру {cam_id}.")
                cap.release()
            else:
                print(f"Инициализация камеры {cam_id}...")
                self.cameras[cam_id] = cap
                time.sleep(1)

    def get_camera(self, cam_id):
        """получить данные с камеры"""
        if cam_id not in self.cameras:
            return None
        cap = self.cameras[cam_id]
        if not cap.isOpened():
            print(f"Камера {cam_id} отключена, пытаюсь переподключиться...")
            cap.release()
            cap = cv2.VideoCapture(self.camera_configs[cam_id], cv2.CAP_FFMPEG)
            if cap.isOpened():
                self.cameras[cam_id] = cap
                print(f"Камера {cam_id} переподключена.")
                time.sleep(2)
            else:
                print(f"Не удалось переподключить камеру {cam_id}.")
                return None
        return cap

    def cleanup(self):
        """Итерация по камерам, проверка и освобождение камеры, очистка словаря"""
        for cam in self.cameras.values():
            if cam.isOpened():
                cam.release()
        self.cameras.clear()

camera_manager = CameraManager()

async def generate_frames(cap, cam_id):
    """Генератор для потоковой передачи кадров"""
    while True:
        try:
            ret, frame = cap.read()
            if not ret or frame is None:
                print(f"Кадр отброшен для камеры {cam_id}")
                break

            size_video = os.getenv("SIZE_VIDEO")
            if size_video:
                width, height = map(int, size_video.split(","))
            else:
                width, height = 1280, 720
            frame = cv2.resize(frame, (width, height))
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ret:
                print(f"Ошибка кодирования кадра для камеры {cam_id}")
                continue

            frame_data = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
            await asyncio.sleep(0.03)

        except Exception as e:
            print(f"Ошибка в генераторе кадров для камеры {cam_id}: {e}")
            break

def generate_token(username):
    return serializer.dumps(username)

def verify_token(token):
    """Верификация токена"""
    try:
        username = serializer.loads(token, max_age=3600)
        return username
    except SignatureExpired:
        print("Токен истек.")
        return None
    except BadSignature:
        print("Недействительная подпись токена.")
        return None
    except BadData:
        print("Некорректные данные токена.")
        return None
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None


@app.route('/video/<cam_id>')
async def video_feed(cam_id):
    """Маршрут для видеопотока с выбранной камеры"""
    cap = camera_manager.get_camera(cam_id)
    if not cap:
        return "Камера не найдена или недоступна", 404

    async def stream():
        try:
            async for frame in generate_frames(cap, cam_id):
                yield frame
        except Exception as e:
            print(f"Ошибка стриминга для камеры {cam_id}: {e}")

    return Response(stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


def hash_password(password: str) -> str:
    """Хеширование пароля."""
    return hashlib.sha256(password.encode()).hexdigest()


@app.route('/login', methods=['GET', 'POST'])
async def login():
    """Авторизация."""
    form_data = await request.form
    username = form_data.get('user')
    password = form_data.get('password')
    hashed_password = hash_password(password)
    answer = await Repo.auth_user(username, hashed_password)
    print("answer", answer)
    token = session.get('token')  # Извлечение токена из сессии
    access = verify_token(token)
    if access:
        return await render_template("index.html", camera_configs=camera_manager.camera_configs,
                                     access=access)
    if answer is True:
        token = generate_token(username)
        session['token'] = token
        return redirect(url_for('index'))
    return jsonify({"message": "Ошибка доступа"}), 401


@app.route('/')
async def index():
    """Главная страница с выбором камер"""
    token = session.get('token')
    access = verify_token(token)
    return await render_template("index.html", camera_configs=camera_manager.camera_configs,
                                 access=access)


async def cleanup():
    """Очистка ресурсов при завершении"""
    print("Завершение работы...")
    camera_manager.cleanup()

async def main():
    """Основная функция для запуска приложения"""
    try:
        await app.run_task(host='0.0.0.0', port=8001)
    except asyncio.CancelledError:
        await cleanup()

if __name__ == '__main__':
    def handle_shutdown(sig, frame):
        """Обработчик сигналов для завершения"""
        asyncio.create_task(cleanup())
        sys.exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_shutdown)

    asyncio.run(main())
