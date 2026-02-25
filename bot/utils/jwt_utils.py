import datetime
import os
from functools import wraps

import jwt
from aiogram import types
from aiogram.fsm.context import FSMContext


async def create_jwt_token(data):
    """Create token"""
    token = jwt.encode({
        **data,
        'exp': datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
    }, os.getenv("SECRET_KEY"), algorithm='HS256')
    return token


async def decode_jwt_token(token):
    """Decode token"""
    try:
        decoded_data = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=['HS256'])
        return decoded_data
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(func):
    """Check token in status admin"""
    @wraps(func)
    async def wrapper(message: types.Message, state: FSMContext, *args, **kwargs):
        data = await state.get_data()
        token = data.get("jwt_token")
        status = data.get("status")
        if not token:
            await message.answer("Нет сохранённого токена. Пройдите авторизацию через /start.")
            return None
        if status != "admin":
            await message.answer("Недостаточно прав доступа.")
            return None
        decoded_data = await decode_jwt_token(token)
        if decoded_data:
            return await func(message, state=state, *args, **kwargs)
        else:
            await message.answer("Токен недействителен или истёк. Авторизуйтесь снова.")
            return None
    return wrapper
