import os
import io
import subprocess

from hypercorn.config import Config
from hypercorn.asyncio import serve
import hashlib
import json
import re
import cv2
import nmap
import asyncio
from quart import (Quart, request, jsonify, render_template, make_response, Response, redirect, url_for, session, flash,
                   get_flashed_messages, send_file)
import signal
from functools import wraps
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from celery_task import tasks
from surveillance.schemas.repository import Cameras, User
from surveillance.camera_manager import CameraManager
from logs.logging_config import get_logger
logger = get_logger()


load_dotenv()
script_dir = os.path.dirname(os.path.abspath(__file__))

os.environ[
    "OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|buffer_size;4194304|timeout;10000000|flags;discardcorrupt"

app = Quart(__name__)
app.secret_key = os.urandom(24)

app.template_folder = "templates"
camera_manager: CameraManager = CameraManager()

@app.before_serving
async def setup_camera_manager():
    global camera_manager
    camera_manager = CameraManager()
    if not CameraManager():
        return
    await camera_manager.initialize()


async def generate_frames(cap):
    """frame streaming generator"""
    while True:
        try:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            size_video = os.getenv("SIZE_VIDEO")
            if size_video:
                width, height = map(int, size_video.split(","))
            else:
                width, height = 1280, 720
            frame = cv2.resize(frame, (width, height))
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ret:
                continue

            frame_data = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
            await asyncio.sleep(0.03)

        except Exception as err:
            break


def hash_password(password: str) -> str:
    """hashing password."""
    return hashlib.sha256(password.encode()).hexdigest()


def token_required(f):
    """checking the token by validation (admin(control panel))"""
    @wraps(f)
    async def decorated(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return jsonify({"message": "No token"}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            if data['status'] != 'admin':
                return jsonify({"message": "Insufficient rights"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401
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
    """Stream video feed with motion detection and optional screenshot saving."""
    if camera_manager is None:
        return "CameraManager not initialized", 500
    allowed_ids = await User.get_allowed_chat_ids()

    async def stream():
        config = await Cameras.select_cam_config(cam_id)

        show_zone = config.get("status_cam", True)
        save_screenshot = config.get("screen_cam", False)
        send_email = config.get("send_email", False)
        send_tg = config.get("send_tg", False)
        send_video_tg = config.get("send_video_tg", False)

        empty_in_row = 0
        max_empty = 10

        points = await Cameras.select_coordinates_by_id(cam_id)

        try:
            while True:
                frame, screenshot_path, video_path = await camera_manager.get_frame_with_motion_detection(
                    cam_id=cam_id,
                    save_screenshot=save_screenshot,
                    send_video_tg=send_video_tg,
                    points=points,
                    show_zone=show_zone
                )

                if frame is None:
                    empty_in_row += 1
                    if empty_in_row >= max_empty:
                        break
                    await asyncio.sleep(0.05)
                    continue

                empty_in_row = 0

                if send_email and screenshot_path:
                    tasks.send_screenshot_email.delay(cam_id, screenshot_path)

                if send_tg and screenshot_path:
                    for chat_id in allowed_ids:
                        tasks.send_telegram_notification.delay(cam_id, screenshot_path, chat_id)

                if send_video_tg and video_path:
                    for chat_id in allowed_ids:
                        tasks.send_telegram_video.delay(cam_id, video_path, chat_id)

                width, height = map(int, os.getenv("SIZE_VIDEO").split(","))
                frame = cv2.resize(frame, (width, height))
                ret, buf = cv2.imencode('.jpg', frame)
                if not ret:
                    continue

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
                await asyncio.sleep(0.033)

        except Exception as error:
            logger.error(f"[ERROR] Streaming error for camera {cam_id}: {error}")

    return Response(stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/view/<cam_id>')
@token_required_camera
async def view_camera(cam_id):
    all_cameras = camera_manager.camera_configs
    return await render_template("camera_view.html", cam_id=cam_id, all_cameras=all_cameras)


@app.route('/update_route', methods=['GET', 'POST'])
@token_required
async def update_route():
    """Update rout for find_camera."""
    form_data = await request.form
    cam_host = form_data.get("cam_host")
    subnet_mask = form_data.get("subnet_mask")
    await Cameras.update_find_camera(cam_host, subnet_mask)
    return redirect(url_for('control'))


@app.route('/clear_count', methods=['POST'])
@token_required
async def clear_count():
    """Reset the camera counter."""
    data = await request.form
    cam_id = data.get("cam_id")
    if not cam_id:
        return "cam_id is required", 400
    points = await Cameras.select_coordinates_by_id(cam_id)
    await camera_manager.get_frame_with_motion_detection(
        cam_id,
        points=points,
        reset_counter=True
    )

    return redirect(url_for('view_camera', cam_id=cam_id))


@app.route('/scan_network_for_rtsp')
@token_required
async def scan_network_for_rtsp():
    """Scan the local network to find devices with open RTSP port."""
    network_range = await Cameras.select_find_cam()
    rtsp_not_found = [f"Within the specified range {network_range} no cameras found!"]
    if not network_range:
        return jsonify(rtsp_not_found)
    list_rtsp = await Cameras.select_ip_cameras()
    try:
        nm = nmap.PortScanner()
        nm.scan(hosts=network_range, arguments='-p 554,8554 --open')
    except Exception as errors:
        return jsonify({'error': f'Nmap scan failed: {str(errors)}'}), 500
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
    return jsonify(rtsp_devices)


def mask_rtsp_credentials(url: str) -> str:
    return re.sub(r'//(.*?):(.*?)@', r'//****:****@', url)


@app.route('/control')
@token_required
async def control():
    """control panel."""
    all_cameras = await Cameras.select_all_cam()
    all_users = await User.select_all_users()
    current_range = await Cameras.select_find_cam()
    masked_urls = {cam.id: mask_rtsp_credentials(cam.path_to_cam) for cam in all_cameras}
    user_host = os.getenv("HOST")
    user_port = os.getenv("PORT")
    messages = get_flashed_messages(with_categories=True)
    return await render_template('control.html', all_cameras=all_cameras, all_users=all_users,
                                 host=user_host, port=user_port, messages=messages, status='admin',
                                 current_range=current_range, masked_urls=masked_urls)


async def list_all_cameras():
    """list of all cameras."""
    q = await Cameras.select_all_cam()
    if not q:
        return {"message": "Камер не найдено!"}
    return await render_template('control.html', status='admin')


@app.route('/delete_camera/<int:ssid>', methods=['GET', 'POST'])
@token_required
async def delete_camera(ssid):
    """deleting camera by id"""
    success = await Cameras.drop_camera(ssid)
    if success:
        return redirect(url_for('control'))
    return jsonify({"error": "Camera not found"}), 404


@app.route('/delete_user/<int:ssid>', methods=['GET'])
@token_required
async def delete_user(ssid):
    """deleting a user by id."""
    if ssid == 1:
        await flash("Superadmin is not deleted", "admin_not_deleted")
        return redirect(url_for('control'))
    success = await User.drop_user(ssid)
    if success:
        await flash("User successfully deleted", "user_deleted")
        return redirect(url_for('control'))
    return jsonify({"error": "User not found"}), 404


@app.route('/add_camera', methods=['POST', 'GET'])
@token_required
async def add_new_camera():
    """add new camera."""
    form_data = await request.form
    new_cam = form_data.get("new_cam")
    motion_detection = 1 if form_data.get("motion_detection") else 0
    visible_cam = 1 if form_data.get("visible_cam") else 0
    screen_cam = 1 if form_data.get("screen_cam") else 0

    send_email = 1 if form_data.get("send_email") else 0
    send_tg = 1 if form_data.get("send_tg") else 0
    if not new_cam:
        await flash("Camera URL not specified!", "error")
        return redirect(url_for("control"))
    query = await check_rtsp(new_cam)
    if query is False:
        await flash("Error: Invalid RTSP URL", "rtsp_error")
        return redirect(url_for("control"))
    q = await Cameras.add_new_cam(new_cam, int(motion_detection), int(visible_cam), int(screen_cam),
                               int(send_email), int(send_tg))
    if q is False:
        await flash("Camera not added: such URL already exists or an error occurred!",
                    "camera_error")
        return redirect(url_for("control"))
    await flash("Camera added successfully!", "camera_success")
    return redirect(url_for("control"))


async def select_all_users():
    """list of all users"""
    q = User.select_all_users()
    return q


PASSWORD_PATTERN = r"^(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&+=])(?=\S+$).{8,20}$"

@app.route('/add_user', methods=['POST', 'GET'])
@token_required
async def add_new_user():
    """adding the new user."""
    form_data = await request.form
    user = form_data.get("new_user")
    password = form_data.get("new_password")
    status = form_data.get("status")
    tg_id = form_data.get("tg_id")
    active = form_data.get("active")
    if not re.match(PASSWORD_PATTERN, password):
        await flash("Password structure does not match!", "password_error")
        return redirect(url_for("control"))
    pswrd = hash_password(password)
    q = await User.add_new_user(user, pswrd, status, tg_id, active)
    if q is False:
        await flash("This user already exists!", "user_error")
        return redirect(url_for("control"))
    await flash("User added successfully!", "user_success")
    return redirect(url_for("control"))


@app.route('/edit_cam', methods=['POST', 'GET'])
@token_required
async def edit_cam():
    """editing the path to camera."""
    form_data = await request.form
    ssid = form_data.get("cameraId")
    path_to_cam = form_data.get("cameraPath")
    motion_detection = 1 if form_data.get("motion_detect") else 0
    visible_camera = 1 if form_data.get("visible_camera") else 0
    screen_cam = 1 if form_data.get("screen_cam") else 0
    send_mail = 1 if form_data.get("send_mail") else 0
    send_telegram = 1 if form_data.get("send_telegram") else 0
    send_video_tg = 1 if form_data.get("send_video_tg") else 0
    query = await check_rtsp(path_to_cam)
    if query is False:
        await flash("Error: Incorrect RTSP URL", "rtsp_error")
        return redirect(url_for("control"))
    await Cameras.edit_camera(ssid, path_to_cam, motion_detection, visible_camera, screen_cam,
                           send_mail, send_telegram, send_video_tg,
                           )
    await flash("Camera updated successfully!", "user_success")
    return redirect(url_for("control"))


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
            logger.info("Token expired")
        except jwt.InvalidTokenError as f:
            logger.error(f"Invalid token: {str(f)}")
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
    user = await User.auth_user(username, hashed_password)

    if user:
        status = user.status  # type: ignore

        token = jwt.encode(
            {
                'username': username,
                'status': status,
                'exp': datetime.now(timezone.utc) + timedelta(hours=int(os.getenv("TOKEN_TIME_AUTHORIZATION")))
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
    except ValueError as v:
        return Response(
            json.dumps({"error": str(v)}),
            mimetype='application/json',
            status=500
        )
    except Exception as w:
        return Response(
            json.dumps({"error": f"Error during reboot CameraManager: {str(w)}"}),
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
    except Exception as er:
        return jsonify({"success": False, "error": str(er)}), 500


@app.route('/screenshot/<cam_id>', methods=['POST'])
@token_required
async def take_screenshot(cam_id):
    """Forced screenshot"""
    if camera_manager is None:
        return "CameraManager not initialized", 500
    frame = await camera_manager.get_current_frame(cam_id)
    if frame is None:
        return "No frame available", 404
    timestamp = datetime.now()
    filename = f"camera_{cam_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
    date_str = timestamp.strftime('%Y-%m-%d')
    folder = os.path.join("screenshots", "current", f"camera {cam_id}", date_str)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    cv2.imwrite(path, frame)
    return jsonify({"status": "ok", "filename": filename})


@app.route("/camera_snapshot", methods=['GET'])
@token_required
async def camera_snapshot():
    cam_id = request.args.get("cam_id")
    result = await Cameras.select_path_to_cam(int(cam_id))
    cap = cv2.VideoCapture(result)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return "Error receiving frame", 500
    _, buffer = cv2.imencode('.jpg', frame)
    return await send_file(io.BytesIO(buffer.tobytes()), mimetype='image/jpeg')


@app.route("/save_camera_zone", methods=['POST'])
@token_required
async def save_camera_zone():
    data = await request.get_json()
    points = data.get("points")
    cam_id = data.get("cam_id")

    try:
        processed_points = []
        for point in points:
            if not isinstance(point, dict) or 'x' not in point or 'y' not in point:
                return jsonify({"message": "Invalid coordinate format, expected{'x': int, 'y': int}"}), 400
            x, y = int(point['x']), int(point['y'])
            processed_points.append((x, y))
    except (ValueError, TypeError):
        return jsonify({"message": "Coordinates must be integers."}), 400

    coordinates = []
    for i, (x, y) in enumerate(processed_points, 1):
        var_name = f"coord_{i}"
        exec(f"{var_name} = ({x}, {y})")
        coordinates.append((x, y))

    update_data = {
        "cam_id": cam_id,
        "coordinate_x1": f"{coordinates[0][0]}, {coordinates[0][1]}",
        "coordinate_y1": f"{coordinates[0][0]}, {coordinates[0][1]}",
        "coordinate_x2": f"{coordinates[2][0]}, {coordinates[2][1]}",
        "coordinate_y2": f"{coordinates[2][0]}, {coordinates[2][1]}",
    }

    result = await Cameras.update_coord(**update_data)

    if result is False:
        return jsonify({"message": "Coordinate update error"}), 500
    elif isinstance(result, Exception):
        return jsonify({"message": f"Error: {str(result)}"}), 500
    else:
        return jsonify({"message": result, "coordinates": coordinates}), 200


@app.route("/start_recording_loop/<cam_id>", methods=["POST"])
@token_required_camera
async def start_recording_loop(cam_id):
    """long recording in 30 second blocks"""
    asyncio.create_task(camera_manager.start_continuous_recording(cam_id))
    return jsonify({"status": "recording_started"})


@app.route("/stop_recording_loop/<cam_id>", methods=["POST"])
@token_required_camera
async def stop_recording_loop(cam_id):
    """stop entry"""
    await camera_manager.stop_continuous_recording(cam_id)
    return jsonify({"status": "recording_stopped"})


async def force_start_cam(cam_id):
    """Forcing the camera to start(bot)"""
    await camera_manager.reinitialize_camera(cam_id)


@token_required
@app.route("/force_stop_cam/<cam_id>", methods=["GET"])
async def force_stop_cam(cam_id):
    """Forcing the camera to stop"""
    asyncio.create_task(camera_manager._stop_camera_reader(cam_id))
    return redirect(url_for('control'))


@token_required
@app.route("/stop_all_cam")
async def stop_all_cam():
    """Forcing all_cameras to stop"""
    await cleanup()
    return {"status": "all cameras stopped"}


@token_required
@app.route("/health_server", methods=["POST"])
async def health_server():
    if request.content_type == 'application/json':
        data = await request.get_json()
    else:
        data = await request.form
    subject = data.get("subject", "I`m server.")
    health = tasks.health_server.delay(subject)
    return jsonify({"task_id": health.id}, "success")


@token_required_camera
@app.route('/logout')
async def logout():
    """exit."""
    resp = redirect(url_for('login'))
    resp.delete_cookie("token", path="/", secure=True, httponly=True, samesite="Lax")
    resp.delete_cookie("csrftoken", path="/", secure=True, httponly=True, samesite="None")
    session.pop('token', None)
    return resp

shutdown_event = asyncio.Event()

def handle_shutdown():
    """signal handler for application shutdown."""
    shutdown_event.set()


async def shutdown_trigger():
    """awaitable shutdown trigger for Hypercorn."""
    await shutdown_event.wait()
    logger.info("[INFO] Shutdown signal received, Hypercorn exiting...")


async def cleanup():
    """Shutdown"""
    logger.info("[INFO] Shutdown...")
    stop_sh_path = os.path.join(script_dir, "../stop.sh")
    subprocess.run([stop_sh_path])


async def main(host: str, port: int, debug: bool = False):
    config = Config()
    config.bind = [f"{host}:{port}"]
    config.debug = debug

    success = await camera_manager.load_camera_configs()
    if success:
        await camera_manager.initialize()
    else:
        logger.info("Cameras not initialized, app continues to launch.")

    try:
        await serve(app, config, shutdown_trigger=shutdown_trigger)
    finally:
        logger.info("[INFO] All cameras stopped.")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, loop.stop)  # noqa:ARG
    except (NotImplementedError, RuntimeError) as e:
        logger.warning(f"[WARNING] Could not set signal handler: {e}")

    try:
        loop.run_until_complete(
            main(
                host=os.getenv('HOST', '0.0.0.0'),
                port=int(os.getenv("PORT", 8080))
            )
        )
    except KeyboardInterrupt:
        logger.info("[INFO] Received interrupt signal")
    except Exception as e:
        logger.error(f"[ERROR] Application error: {e}")
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                logger.info("[INFO] Cancelling pending tasks")
                for task in pending:
                    task.cancel()

                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        finally:
            loop.close()
            logger.info("[INFO] Event loop closed")
