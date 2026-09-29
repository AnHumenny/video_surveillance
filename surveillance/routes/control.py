import os
import re
import nmap

from quart import request, jsonify, render_template, Blueprint, redirect, url_for,  flash, get_flashed_messages
from surveillance.schemas.repository import Cameras, User, OldFiles
from surveillance.utils.rtsp_utils import mask_rtsp_credentials, check_rtsp, PASSWORD_PATTERN
from surveillance.utils.hash_utils import hash_password
from surveillance.utils.jwt_utils import token_required

control_bp = Blueprint("control", __name__)

@control_bp.route('/control')
@token_required
async def control():
    """control panel."""

    all_cameras = await Cameras.select_all_cam()
    all_users = await User.select_all_users()
    current_range = await Cameras.select_find_cam()
    old_files_weekly = await OldFiles.select_status_old_video()
    old_files_logs = await OldFiles.select_status_old_logs()
    masked_urls = {cam.id: mask_rtsp_credentials(cam.path_to_cam) for cam in all_cameras}
    user_host = os.getenv("HOST")
    user_port = os.getenv("PORT")

    messages = get_flashed_messages(with_categories=True)
    return await render_template('control.html', all_cameras=all_cameras, all_users=all_users,
                                 host=user_host, port=user_port, messages=messages, status='admin',
                                 current_range=current_range, masked_urls=masked_urls,
                                 old_files_weekly=old_files_weekly, old_files_logs=old_files_logs)


@control_bp.route('/update_route', methods=['GET', 'POST'])
@token_required
async def update_route():
    """Update rout for find_camera."""

    form_data = await request.form
    cam_host = form_data.get("cam_host")
    subnet_mask = form_data.get("subnet_mask")
    await Cameras.update_find_camera(cam_host, subnet_mask)
    return redirect(url_for('control.control'))


@control_bp.route('/scan_network_for_rtsp')
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


@control_bp.route('/delete_camera/<int:ssid>', methods=['GET', 'POST'])
@token_required
async def delete_camera(ssid):
    """deleting camera by id"""

    success = await Cameras.drop_camera(ssid)
    if success:
        return redirect(url_for('control.control'))
    return jsonify({"error": "Camera not found"}), 404


@control_bp.route('/delete_user/<int:ssid>', methods=['GET'])
@token_required
async def delete_user(ssid):
    """deleting a user by id."""

    if ssid == 1:
        await flash("Superadmin is not deleted", "admin_not_deleted")
        return redirect(url_for('control.control'))
    success = await User.drop_user(ssid)
    if success:
        await flash("User successfully deleted", "user_deleted")
        return redirect(url_for('control.control'))
    return jsonify({"error": "User not found"}), 404


@control_bp.route('/add_camera', methods=['POST', 'GET'])
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
        return redirect(url_for("control.control"))
    query = await check_rtsp(new_cam)
    if query is False:
        await flash("Error: Invalid RTSP URL", "rtsp_error")
        return redirect(url_for("control.control"))
    q = await Cameras.add_new_cam(new_cam, int(motion_detection), int(visible_cam), int(screen_cam),
                               int(send_email), int(send_tg))
    if q is False:
        await flash("Camera not added: such URL already exists or an error occurred!",
                    "camera_error")
        return redirect(url_for("control.control"))
    await flash("Camera added successfully!", "camera_success")
    return redirect(url_for("control.control"))


@control_bp.route('/add_user', methods=['POST', 'GET'])
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
        return redirect(url_for("control.control"))
    pswrd = hash_password(password)
    q = await User.add_new_user(user, pswrd, status, tg_id, active)
    if q is False:
        await flash("This user already exists!", "user_error")
        return redirect(url_for("control.control"))
    await flash("User added successfully!", "user_success")
    return redirect(url_for("control.control"))


@control_bp.route('/edit_cam', methods=['POST', 'GET'])
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
        return redirect(url_for("control.control"))
    await Cameras.edit_camera(ssid, path_to_cam, motion_detection, visible_camera, screen_cam,
                           send_mail, send_telegram, send_video_tg,
                           )
    await flash("Camera updated successfully!", "user_success")
    return redirect(url_for("control.control"))


@control_bp.route('/celery_old_video', methods=['POST'])
@token_required
async def celery_old_video():
    """editing status celery task."""

    form_data = await request.form
    old_video = form_data.get("weekly_recordings_cleanup")

    await OldFiles.celery_old_video(old_video)
    return redirect(url_for("control.control"))


@control_bp.route('/celery_old_logs_cleanup', methods=['POST'])
@token_required
async def celery_old_logs_cleanup():
    """editing status celery task."""

    form_data = await request.form
    old_logs = form_data.get("old_logs_cleanup")

    await OldFiles.celery_old_logs(old_logs)
    return redirect(url_for("control.control"))
