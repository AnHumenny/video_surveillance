import os
from hypercorn.config import Config
from hypercorn.asyncio import serve
import hashlib
import json
import re
import cv2
import nmap
import asyncio
from quart import (Quart, request, jsonify, render_template, make_response, Response, redirect, url_for, session, flash,
    get_flashed_messages)
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
    if not CameraManager():
        return
    await camera_manager.initialize()

@app.after_serving
async def shutdown_camera_manager():
    global camera_manager
    if camera_manager:
        await camera_manager.cleanup()


async def generate_frames(cap, cam_id):
    """frame streaming generator"""
    while True:
        try:
            ret, frame = cap.read()
            if not ret or frame is None:
                print(f"The frame is discarded for the camera {cam_id}")
                break
            size_video = os.getenv("SIZE_VIDEO")
            if size_video:
                width, height = map(int, size_video.split(","))
            else:
                width, height = 1280, 720
            frame = cv2.resize(frame, (width, height))
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ret:
                print(f"Frame encoding error for camera {cam_id}")
                continue

            frame_data = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
            await asyncio.sleep(0.03)

        except Exception as e:
            print(f"Frame encoding error for camera {cam_id}: {e}")
            break


def generate_token(username, status):
    """generation token"""
    payload = {
        'user': username,
        'status': status,
        'exp': datetime.now(datetime.UTC) + timedelta(hours=1)
    }
    return jwt.encode(payload, os.getenv("SECRET_KEY"), algorithm='HS256')


def verify_token(token):
    """verification token"""
    if not token:
        return False, None
    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=['HS256'])
        status = payload.get('status')
        return True, status
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
        return False, None


def hash_password(password: str) -> str:
    """hashing password."""
    return hashlib.sha256(password.encode()).hexdigest()


def token_required(f):
    """checking the token by validation (admin(control panel))"""
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


def token_required_camera(f):
    """checking the token by validation (admin, user(cameras))"""
    @wraps(f)
    async def decorated(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return jsonify({"message": "No token"}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            if data['status'] not in ['admin', 'user']:
                return jsonify({"message": "Insufficient rights"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401
        return await f(*args, **kwargs)
    return decorated


async def check_rtsp(path_to_cam):
    """checking camera on rtsp."""
    q = path_to_cam[0:4]
    if q != "rtsp":
        return False
    return True


@app.route('/video/<cam_id>')
@token_required_camera
async def video_feed(cam_id):
    """Stream video feed with motion detection for the specified camera."""
    if camera_manager is None:
        return "CameraManager not initialization", 500

    async def stream():
        status_cam = await Repo.select_bool_cam(cam_id)
        try:
            while True:
                frame = await camera_manager.get_frame_with_motion_detection(cam_id, status_cam)
                if frame is None:
                    print(f"Failed to get frame for camera {cam_id}")
                    break

                frame = cv2.resize(frame, (1280, 720))      # принудительное снижение
                ret, buffer = cv2.imencode('.jpg', frame)
                if not ret:
                    print(f"Frame encoding error for camera {cam_id}")
                    continue
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

                await asyncio.sleep(0.033)  # ~30 FPS

        except Exception as e:
            print(f"Streaming error for camera {cam_id}: {e}")

    cap = await camera_manager.get_camera(cam_id)

    if not cap:
        return "Camera not found or unavailable", 404

    return Response(stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/update_route', methods=['GET', 'POST'])
@token_required
async def update_route():
    """Update rout for find_camera."""
    form_data = await request.form
    cam_host = form_data.get("cam_host")
    subnet_mask = form_data.get("subnet_mask")
    await Repo.update_find_camera(cam_host, subnet_mask)
    return redirect(url_for('control'))


@app.route('/scan_network_for_rtsp')
@token_required
async def scan_network_for_rtsp():
    """Scan the local network to find devices with open RTSP port."""
    network_range = await Repo.select_find_cam()
    rtsp_not_found = [f"Within the specified range {network_range} no cameras found!"]
    if not network_range:
        return jsonify(rtsp_not_found)
    list_rtsp = await Repo.select_ip_cameras()
    try:
        nm = nmap.PortScanner()
        nm.scan(hosts=network_range, arguments='-p 554,8554 --open')
    except Exception as e:
        return jsonify({'error': f'Nmap scan failed: {str(e)}'}), 500
    rtsp_devices = []
    for host in nm.all_hosts():
        for port in [554, 8554]:
            if (
                'tcp' in nm[host]
                and port in nm[host]['tcp']
                and nm[host]['tcp'][port]['state'] == 'open'
            ):
                check_url = f"{host}:{port}"
                if check_url not in list_rtsp:
                    rtsp_devices.append({
                        'ip': host,
                        'port': port,
                    })
                    print(f"[DEBUG] Found potential RTSP device at {host}:{port}")
    return jsonify(rtsp_devices)

def mask_rtsp_credentials(url: str) -> str:
    return re.sub(r'//(.*?):(.*?)@', r'//****:****@', url)

@app.route('/control')
@token_required
async def control():
    """control panel."""
    all_cameras = await Repo.select_all_cam()
    all_users = await Repo.select_all_users()
    current_range = await Repo.select_find_cam()
    masked_urls = {cam.id: mask_rtsp_credentials(cam.path_to_cam) for cam in all_cameras}
    user_host = os.getenv("HOST")
    user_port = os.getenv("PORT")
    messages = get_flashed_messages(with_categories=True)
    return await render_template('control.html', all_cameras=all_cameras, all_users=all_users,
                                 host=user_host, port=user_port, messages=messages, status='admin',
                                 current_range=current_range, masked_urls=masked_urls )

async def list_all_cameras():
    """list of all cameras."""
    q = await Repo.select_all_cam()
    if not q:
        return {"message": "Камер не найдено!"}
    return await render_template('control.html', status='admin')


@app.route('/delete_camera/<int:ssid>', methods=['GET', 'POST'])
async def delete_camera(ssid):
    """deleting camera by id"""
    success = await Repo.drop_camera(ssid)
    if success:
        return redirect(url_for('control'))
    return jsonify({"error": "Camera not found"}), 404


@app.route('/delete_user/<int:ssid>', methods=['GET'])
async def delete_user(ssid):
    """deleting a user by id."""
    if ssid == 1:
        await flash("Superadmin is not deleted", "admin_not_deleted")
        return redirect(url_for('control'))
    success = await Repo.drop_user(ssid)
    if success:
        await flash("User successfully deleted", "user_deleted")
        return redirect(url_for('control'))
    return jsonify({"error": "User not found"}), 404


@app.route('/add_camera', methods=['POST', 'GET'])
async def add_new_camera():
    """add new camera."""
    form_data = await request.form
    new_cam = form_data.get("new_cam")
    motion_detection = 1 if form_data.get("motion_detection") else 0
    visible_cam = 1 if form_data.get("visible_cam") else 0
    if not new_cam:
        await flash("Camera URL not specified!", "error")
        return redirect(url_for("control"))
    query = await check_rtsp(new_cam)
    if query is False:
        await flash("Error: Invalid RTSP URL", "rtsp_error")
        return redirect(url_for("control"))
    q = await Repo.add_new_cam(new_cam, int(motion_detection), int(visible_cam))
    if q is False:
        await flash("Camera not added: such URL already exists or an error occurred!",
                    "camera_error")
        return redirect(url_for("control"))
    await flash("Camera added successfully!", "camera_success")
    return redirect(url_for("control"))


async def select_all_users():
    """list of all users"""
    q = Repo.select_all_users()
    return q


PASSWORD_PATTERN = r"^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&+=])(?=\S+$).{8,20}$"

@app.route('/add_user', methods=['POST', 'GET'])
async def add_new_user():
    """adding the new user."""
    form_data = await request.form
    user = form_data.get("new_user")
    password = form_data.get("new_password")
    status = form_data.get("status")
    if not re.match(PASSWORD_PATTERN, password):
        await flash("Password structure does not match!", "password_error")
        return redirect(url_for("control"))
    pswrd = hash_password(password)
    q = await Repo.add_new_user(user, pswrd, status)
    if q is False:
        await flash("This user already exists!", "user_error")
        return redirect(url_for("control"))
    await flash("User added successfully!", "user_success")
    return redirect(url_for("control"))


@app.route('/edit_cam', methods=['POST', 'GET'])
async def edit_cam():
    """editing the path to camera."""
    form_data = await request.form
    ssid = form_data.get("cameraId")
    path_to_cam = form_data.get("cameraPath")
    motion_detection = 1 if form_data.get("motion_detect") else 0
    visible_camera = 1 if form_data.get("visible_camera") else 0
    query = await check_rtsp(path_to_cam)
    if query is False:
        await flash("Error: Incorrect RTSP URL", "rtsp_error")
        return redirect(url_for("control"))
    await Repo.edit_camera(ssid, path_to_cam, motion_detection, visible_camera)
    await flash("User added successfully!", "user_success")
    return redirect(url_for("control"))


@app.route('/logout')
async def logout():
    """exit"""
    session.pop('token', None)
    return redirect(url_for('login'))


@app.route('/', methods=['GET'])
async def index():
    """main page with camera selection."""
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
            print("Token expired")
        except jwt.InvalidTokenError as e:
            print(f"Invalid token: {str(e)}")
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
async def login():
    """Authorization."""
    if request.method == 'GET':
        return await render_template('login.html')

    form_data = await request.form
    username = form_data.get('user')
    password = form_data.get('password')
    hashed_password = hash_password(password)
    user = await Repo.auth_user(username, hashed_password)

    if user:
        status = user.status  # type: ignore

        token = jwt.encode(
            {
                'username': username,
                'status': status,
                'exp': datetime.now(timezone.utc) + timedelta(hours=1)
            },
            app.config['SECRET_KEY'],
            algorithm='HS256'
        )

        rendered = await render_template(
            "index.html",
            camera_configs=camera_manager.camera_configs,
            username=username,
            status=status
        )

        response = await make_response(rendered)
        response.set_cookie(
            'token',
            token,
            httponly=True,
            secure=False,
            samesite="Lax"
        )
        return response

    return jsonify({"message": "Access error"}), 401


@app.route('/reload-cameras', methods=['GET', 'POST'])
async def reload_cameras():
    """reload all cameras"""
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
            json.dumps({"error": f"Error during reboot CameraManager: {str(e)}"}),
            mimetype='application/json',
            status=500
        )

@app.route('/reinitialize/<cam_id>', methods=['POST'])
async def reinitialize_camera(cam_id):
    """Forced camera reinitialization"""
    try:
        success = await camera_manager.reinitialize_camera(cam_id)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": f"Failed to reinitialize camera {cam_id}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


async def cleanup():
    """Clearing resources on completion"""
    await camera_manager.cleanup()


async def main(host: str, port: int, debug: bool = False):
    config = Config()
    config.bind = [f"{host}:{port}"]
    config.debug = debug
    success = await camera_manager.load_camera_configs()
    if success:
        await camera_manager.initialize()
    else:
        print("Cameras not initialized, app continues to launch.")
    try:
        await serve(app, config)
    except asyncio.CancelledError:
        print("Server interrupted, shutting down...")
        await cleanup()


if __name__ == '__main__':
    def handle_shutdown(sig, frame):
        """Signal handler for completion"""
        asyncio.create_task(cleanup())
        sys.exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_shutdown)

    asyncio.run(main(host=os.getenv('HOST'), port=int(os.getenv("PORT"))))
