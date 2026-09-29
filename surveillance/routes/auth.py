import os

from quart import Blueprint, request, jsonify, render_template, make_response, redirect, url_for, session
import jwt

from surveillance.schemas.repository import User
from surveillance.state import camera_manager
from surveillance.utils.hash_utils import hash_password
from surveillance.utils.jwt_utils import token_required_camera, create_token
from logs.logging_config import get_logger

logger = get_logger()

auth_bp = Blueprint("auth", __name__)

@auth_bp.route('/', methods=['GET'])
async def index():
    """main page with camera selection."""

    token = request.cookies.get('token')
    if token:
        try:
            payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=['HS256'])
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
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
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

        token = create_token(username, status)

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



@auth_bp.route('/logout')
@token_required_camera
async def logout():
    """exit."""

    resp = redirect(url_for('auth.login'))
    resp.delete_cookie("token", path="/", secure=True, httponly=True, samesite="Lax")
    resp.delete_cookie("csrftoken", path="/", secure=True, httponly=True, samesite="None")
    session.pop('token', None)
    return resp
