import hashlib
import json
import re
import cv2
import os
import asyncio
from quart import Quart, request, jsonify, render_template, make_response, Response, redirect, url_for, session, flash, \
    get_flashed_messages
import signal
import sys
from functools import wraps
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from schemas.repository import Repo
from camera_manager import CameraManager

load_dotenv()

os.environ[
    "OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|buffer_size;4194304|timeout;10000000|flags;discardcorrupt"

app = Quart(__name__)
app.secret_key = os.urandom(24)

app.template_folder = "templates"
camera_manager = CameraManager()

@app.before_serving
async def setup_camera_manager():
    global camera_manager
    camera_manager = CameraManager()
    await camera_manager.initialize()

@app.after_serving
async def shutdown_camera_manager():
    global camera_manager
    if camera_manager:
        await camera_manager.cleanup()


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


def generate_token(username, status):
    """генерация токена"""
    payload = {
        'user': username,
        'status': status,
        'exp': datetime.now(timezone.UTC) + timedelta(hours=1)
    }
    return jwt.encode(payload, os.getenv("SECRET_KEY"), algorithm='HS256')


def verify_token(token):
    """верификация токена"""
    if not token:
        return False, None
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=['HS256'])
        status = payload.get('status')
        return True, status
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
        return False, None


def hash_password(password: str) -> str:
    """Хеширование пароля."""
    return hashlib.sha256(password.encode()).hexdigest()


def token_required(f):
    """проверка валидности токена"""
    @wraps(f)
    async def decorated(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return jsonify({"message": "Токен отсутствует"}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            if data['status'] != 'admin':
                return jsonify({"message": "Недостаточно прав"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Токен истек"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Неверный токен"}), 401
        return await f(*args, **kwargs)
    return decorated


@app.route('/video/<cam_id>')
@token_required
async def video_feed(cam_id):
    """Маршрут для видеопотока с выбранной камеры."""
    if camera_manager is None:
        return "CameraManager не инициализирован", 500
    cap = await camera_manager.get_camera(cam_id)
    if not cap:
        return "Камера не найдена или недоступна", 404
    async def stream():
        try:
            async for frame in generate_frames(cap, cam_id):
                yield frame
        except Exception as e:
            print(f"Ошибка стриминга для камеры {cam_id}: {e}")
    return Response(stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/control')
@token_required
async def control():
    """Панель управления."""
    all_cameras = await Repo.select_all_cam()
    all_users = await Repo.select_all_users()
    user_host = os.getenv("HOST")
    user_port = os.getenv("PORT")
    messages = get_flashed_messages(with_categories=True)
    return await render_template('control.html', all_cameras=all_cameras, all_users=all_users,
                                 host=user_host, port=user_port, messages=messages, status='admin')

async def list_all_cameras():
    """Список всех камер."""
    q = await Repo.select_all_cam()
    if not q:
        return {"message": "Камер не найдено!"}
    return await render_template('control.html', status='admin')


@app.route('/delete_camera/<int:ssid>', methods=['GET', 'POST'])
async def delete_camera(ssid):
    """Удаление камеры по id"""
    success = await Repo.drop_camera(ssid)
    if success:
        return redirect(url_for('control'))
    return jsonify({"error": "Камера не найдена"}), 404


@app.route('/delete_user/<int:ssid>', methods=['GET'])
async def delete_user(ssid):
    """Удаление пользователя по id."""
    if ssid == 1:
        await flash("Суперадмин не удаляется", "admin_not_deleted")
        return redirect(url_for('control'))
    success = await Repo.drop_user(ssid)
    if success:
        await flash("Пользователь успешно удалён", "user_deleted")
        return redirect(url_for('control'))
    return jsonify({"error": "Пользователь не найден"}), 404


@app.route('/edit_camera')    #в доработку
async def edit_camera():
    """Редактирование маршрута камеры."""
    return redirect(url_for('control'))


async def check_rtsp(path_to_cam):
    """Проверка на rtsp."""
    q = path_to_cam[0:4]
    if q != "rtsp":
        return False
    return True


@app.route('/add_camera', methods=['POST', 'GET'])
async def add_new_camera():
    """Добавить новую камеру."""
    form_data = await request.form
    new_cam = form_data.get("new_cam")
    if not new_cam:
        await flash("URL камеры не указан!", "error")
        return redirect(url_for("control"))
    query = await check_rtsp(new_cam)
    if query is False:
        await flash("Ошибка: Некорректный RTSP URL", "rtsp_error")
        return redirect(url_for("control"))
    q = await Repo.add_new_cam(new_cam)
    if q is False:
        await flash("Камера не добавлена: такой URL уже существует или произошла ошибка!",
                    "camera_error")
        return redirect(url_for("control"))
    await flash("Камера успешно добавлена!", "camera_success")
    return redirect(url_for("control"))


async def select_all_users():
    """Список всех пользователей"""
    q = Repo.select_all_users()
    return q


PASSWORD_PATTERN = r"^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&+=])(?=\S+$).{8,20}$"

@app.route('/add_user', methods=['POST', 'GET'])
async def add_new_user():
    """Добавить нового пользователя."""
    form_data = await request.form
    user = form_data.get("new_user")
    password = form_data.get("new_password")
    if not re.match(PASSWORD_PATTERN, password):
        await flash("Длина пароля не соответствует!", "password_error")
        return redirect(url_for("control"))
    pswrd = hash_password(password)
    q = await Repo.add_new_user(user, pswrd)
    if q is False:
        await flash("Такой пользователь уже существует!", "user_error")
        return redirect(url_for("control"))
    await flash("Пользователь успешно добавлен!", "user_success")
    return redirect(url_for("control"))


@app.route('/logout')
async def logout():
    """Выход"""
    session.pop('token', None)
    return redirect(url_for('login'))


@app.route('/', methods=['GET'])
async def index():
    """Главная страница с выбором камер."""
    token = request.cookies.get('token')
    if token:
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            username = payload.get('username')
            status = payload.get('status')
            if username and status:
                response = await render_template(
                    "index.html",
                    camera_configs=camera_manager.camera_configs,
                    username=username,
                    status=status
                )
                return response
        except jwt.ExpiredSignatureError:
            print("Токен просрочен")
        except jwt.InvalidTokenError as e:
            print(f"Невалидный токен: {str(e)}")
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
async def login():
    """Авторизация."""
    if request.method == 'GET':
        return await render_template('login.html')

    form_data = await request.form
    username = form_data.get('user')
    password = form_data.get('password')
    hashed_password = hash_password(password)
    user = await Repo.auth_user(username, hashed_password)
    if user:
        status = user.status  # type: ignore
        if user is None:
            return jsonify({"message": "Статус пользователя не определен"}), 401

        token = jwt.encode(
            {
                'username': username,
                'status': status,
                'exp': datetime.utcnow() + timedelta(hours=1)
            },
            app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        response = await render_template(
            "index.html",
            camera_configs=camera_manager.camera_configs,
            username=username,
            status=status
        )
        response = await make_response(response)
        response.set_cookie('token', token, httponly=True, secure=True)
        return response
    return jsonify({"message": "Ошибка доступа"}), 401


@app.route('/reload-cameras', methods=['GET', 'POST'])
async def reload_cameras():
    global camera_manager
    try:
        if camera_manager:
            await camera_manager.cleanup()
        camera_manager = CameraManager()
        await camera_manager.initialize()
        if request.method == 'GET':
            return redirect('index')
        return Response(
            json.dumps({
                "status": "success",
                "camera_configs": camera_manager.camera_configs
            }, ensure_ascii=False),
            mimetype='application/json',
            status=200
        )
    except ValueError as e:
        return Response(
            json.dumps({"error": str(e)}),
            mimetype='application/json',
            status=500
        )
    except Exception as e:
        return Response(
            json.dumps({"error": f"Ошибка при перезагрузке CameraManager: {str(e)}"}),
            mimetype='application/json',
            status=500
        )


async def cleanup():
    """Очистка ресурсов при завершении"""
    await camera_manager.cleanup()


async def main():
    """Основная функция для запуска приложения"""
    try:
        await app.run_task(host=os.getenv("HOST"), port=int(os.getenv("PORT")))
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
