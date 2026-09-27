import os
import io
import json
import cv2
import asyncio

from quart import request, jsonify, render_template, Blueprint, Response, redirect, url_for, send_file
from datetime import datetime
from celery_task import tasks
from surveillance import state
from surveillance.cleanup import cleanup
from surveillance.schemas.repository import Cameras, User
from surveillance.camera_manager import CameraManager, logger
from surveillance.utils.jwt_utils import token_required_camera, token_required

cameras_bp = Blueprint("cameras", __name__)

@cameras_bp.route('/video/<cam_id>')
@token_required_camera
async def video_feed(cam_id):
    """Stream video feed with motion detection and optional screenshot saving."""

    if state.camera_manager is None:
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
                frame, screenshot_path, video_path = await state.camera_manager.get_frame_with_motion_detection(
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


@cameras_bp.route('/view/<cam_id>')
@token_required_camera
async def view_camera(cam_id):
    all_cameras = state.camera_manager.camera_configs
    return await render_template("camera_view.html", cam_id=cam_id, all_cameras=all_cameras)


@cameras_bp.route('/clear_count', methods=['POST'])
@token_required
async def clear_count():
    """Reset the camera counter."""

    data = await request.form
    cam_id = data.get("cam_id")
    if not cam_id:
        return "cam_id is required", 400
    points = await Cameras.select_coordinates_by_id(cam_id)
    await state.camera_manager.get_frame_with_motion_detection(
        cam_id,
        points=points,
        reset_counter=True
    )

    return redirect(url_for('cameras.view_camera', cam_id=cam_id))


@cameras_bp.route('/reinitialize/<cam_id>', methods=['POST'])
async def reinitialize_camera(cam_id):
    """Forced camera reinitialization"""

    try:
        success = await state.camera_manager.reinitialize_camera(cam_id)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": f"Failed to reinitialize camera {cam_id}"}), 500
    except Exception as er:
        return jsonify({"success": False, "error": str(er)}), 500


@cameras_bp.route('/screenshot/<cam_id>', methods=['POST'])
@token_required
async def take_screenshot(cam_id):
    """Forced screenshot"""

    if state.camera_manager is None:
        return "CameraManager not initialized", 500
    frame = await state.camera_manager.get_current_frame(cam_id)
    if frame is None:
        return "No frame available", 404
    timestamp = datetime.now()
    filename = f"camera_{cam_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
    date_str = timestamp.strftime('%Y-%m-%d')
    folder = os.path.join("media", "current", "screenshots", f"camera {cam_id}", date_str)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    cv2.imwrite(path, frame)
    return jsonify({"status": "ok", "filename": filename})


@cameras_bp.route("/camera_snapshot", methods=['GET'])
@token_required
async def camera_snapshot():
    """screenshot"""

    cam_id = request.args.get("cam_id")
    result = await Cameras.select_path_to_cam(int(cam_id))
    cap = cv2.VideoCapture(result)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return "Error receiving frame", 500
    _, buffer = cv2.imencode('.jpg', frame)
    return await send_file(io.BytesIO(buffer.tobytes()), mimetype='image/jpeg')


@cameras_bp.route("/save_camera_zone", methods=['POST'])
@token_required
async def save_camera_zone():
    """selecting alarm zone"""

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


@cameras_bp.route("/start_recording_loop/<cam_id>", methods=["POST"])
@token_required_camera
async def start_recording_loop(cam_id):
    """long recording in 30 second blocks"""

    asyncio.create_task(state.camera_manager.start_continuous_recording(cam_id))
    return jsonify({"status": "recording_started"})


@cameras_bp.route("/stop_recording_loop/<cam_id>", methods=["POST"])
@token_required_camera
async def stop_recording_loop(cam_id):
    """stop entry"""

    await state.camera_manager.stop_continuous_recording(cam_id)
    return jsonify({"status": "recording_stopped"})



@cameras_bp.route("/force_stop_cam/<cam_id>", methods=["GET"])
@token_required
async def force_stop_cam(cam_id):
    """Forcing the camera to stop"""

    asyncio.create_task(state.camera_manager._stop_camera_reader(cam_id))
    return redirect(url_for('control.control'))


@cameras_bp.route("/stop_all_cam")
@token_required
async def stop_all_cam():
    """Forcing all_cameras to stop"""

    await cleanup()
    return {"status": "all cameras stopped"}


@cameras_bp.route('/reload-cameras', methods=['GET', 'POST'])
async def reload_cameras():
    """reload all cameras"""

    try:
        state.camera_manager = CameraManager()
        await state.camera_manager.initialize()
        if request.method == 'GET':
            return redirect('index')
        return Response(
            json.dumps({
                "status": "success",
                "camera_configs": state.camera_manager.camera_configs
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
