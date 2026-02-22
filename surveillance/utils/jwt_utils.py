import os
from datetime import datetime, timezone, timedelta
from functools import wraps
import jwt
from quart import request, jsonify, current_app


def create_token(username: str, status: str) -> str:
    """Create JWT token for user."""
    token_time = int(os.getenv("TOKEN_TIME_AUTHORIZATION", 24))  # значение по умолчанию 24 часа

    payload = {
        'username': username,
        'status': status,
        'exp': datetime.now(timezone.utc) + timedelta(hours=token_time)
    }

    token = jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    return token


def token_required(f):
    """checking the token by validation (admin(control panel))"""
    @wraps(f)
    async def decorated(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return jsonify({"message": "No token"}), 401
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
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
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            if data['status'] not in ['admin', 'user']:
                return jsonify({"message": "Insufficient rights"}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401
        return await f(*args, **kwargs)
    return decorated
