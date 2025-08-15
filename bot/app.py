import asyncio
import datetime
import hashlib
import logging
from functools import wraps
from typing import Dict, Callable

from aiogram import Bot, Dispatcher, types
import os
import jwt
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, WebAppInfo, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from main import force_start_cam

from bot import lists
from schemas.repository import  Userbot, Repo
from dotenv import load_dotenv

API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

load_dotenv()

class AuthStates(StatesGroup):
    """States for authentication and output"""
    waiting_for_login = State()
    waiting_for_password = State()

class Form(StatesGroup):
    """Token (state: FSMContext)"""
    waiting_for_token = State()

class Info:
    """Variables for throwing"""
    count = 0


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
        print("Token has expired.")
        return None
    except jwt.InvalidTokenError:
        print("Invalid token.")
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


@dp.message(StateFilter(None), Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    """Start(enter login)"""
    await message.answer("Введите логин:")
    await state.set_state(AuthStates.waiting_for_login)


@dp.message(AuthStates.waiting_for_login)
async def process_login(message: types.Message, state: FSMContext):
    """Start(enter password)"""
    await state.update_data(username=message.text)
    await message.answer("Теперь введите пароль:")
    await state.set_state(AuthStates.waiting_for_password)


def hash_password(password: str) -> str:
    """hashing password."""
    return hashlib.sha256(password.encode()).hexdigest()


@dp.message(AuthStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    """Authorization"""
    user_data = await state.get_data()
    username = user_data.get('username')
    password = message.text
    encoded_password = hash_password(password)
    result = await Userbot.auth_user_bot(username, encoded_password)
    if result is None:
        Info.count += 1
        if Info.count == 3:
            await message.answer(
                text="Неверный пароль. Ты заблокирован на 60 секунд."
            )
            await asyncio.sleep(60)
            await message.answer(
                text="нажми /start"
            )
            Info.count = 0
            await state.clear()
            return

    if result:
        user_payload = {
            'login': result.user,
            'status': result.status,
        }
        token = await create_jwt_token(user_payload)

        await state.clear()
        await state.update_data(jwt_token=token, status=result.status, chat_id=message.chat.id)
        await message.answer(
            text=f"Добро пожаловать, {result.user}!\nТеперь можешь написать /help."
        )
        return
    await message.answer(text="Не зашло с паролем :(")
    await state.set_state(AuthStates.waiting_for_login)


@dp.message(Command("help"))
@token_required
async def cmd_start(message: types.Message, state: FSMContext):
    """help"""
    await message.answer(*lists.send)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть админ-панель",
                    web_app=WebAppInfo(url=os.getenv("CLOUDFIRE_URL")))
            ]
        ]
    )
    await message.answer("Вход в админ-панель:", reply_markup=keyboard)


CALLBACK_ACTIONS: Dict[str, Callable] = {
    "reinit_camera": force_start_cam,
    "movie_on": Userbot.movie_off,
    "movie_off": Userbot.movie_on,
    "screen_on": Userbot.screen_off,
    "screen_off": Userbot.screen_on,
}

@dp.message(Command("screen"))
@token_required
async def screen(message: types.Message, state: FSMContext):
    """Enable/disable sending screenshot to TG"""
    camera_objects = await Repo.select_all_cam()
    camera_ids = [str(cam.id) for cam in camera_objects]

    await state.update_data(camera_ids=camera_ids)
    builder = InlineKeyboardBuilder()

    for cam in camera_objects:
        cam_id = str(cam.id)
        if cam.send_tg:
            builder.row(
                types.InlineKeyboardButton(text=f"📷 Screen to TG from cam {cam_id} ON",
                                           callback_data=f"screen_on:{cam_id}"),
            )
        else:
            builder.row(
                types.InlineKeyboardButton(text=f" 📷 Screen to TG from cam {cam_id} OFF",
                                            callback_data=f"screen_off:{cam_id}"),
            )
    await message.answer("Включить/отключить скрин в ТГ:", reply_markup=builder.as_markup())


@dp.message(Command("movie"))
@token_required
async def movie(message: types.Message, state: FSMContext):
    """Enable/disable sending short videos to TG"""
    camera_objects = await Repo.select_all_cam()
    camera_ids = [str(cam.id) for cam in camera_objects]

    await state.update_data(camera_ids=camera_ids)
    builder = InlineKeyboardBuilder()

    for cam in camera_objects:
        cam_id = str(cam.id)
        if cam.send_video_tg:
            builder.row(
                types.InlineKeyboardButton(text=f"🎥  Movie to TG from cam {cam_id}  ON",
                                           callback_data=f"movie_on:{cam_id}"),
            )
        else:
            builder.row(
                types.InlineKeyboardButton(text=f" 🎥 Movie to TG from cam {cam_id} OFF",
                                           callback_data=f"movie_off:{cam_id}"),
            )
    await message.answer("Включить/отключить скрин в ТГ:", reply_markup=builder.as_markup())


@dp.message(Command("reinit"))
@token_required
async def reinit_cam(message: types.Message, state: FSMContext):
    """Reinitialize the selected camera"""
    camera_objects = await Repo.select_all_cam()
    camera_ids = [str(cam.id) for cam in camera_objects]

    await state.update_data(camera_ids=camera_ids)

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔧 Перезапуск камеры", callback_data="-"))

    for cam_id in camera_ids:
        builder.row(
            types.InlineKeyboardButton(text=f"🔁 cam {cam_id}", callback_data=f"reinit_camera:{cam_id}"),
        )
    await message.answer("Реинициализировать камеру:", reply_markup=builder.as_markup())


@dp.callback_query(lambda c: c.data.startswith(tuple(CALLBACK_ACTIONS.keys())), token_required)
@token_required
async def action_cam(callback: types.CallbackQuery, state: FSMContext):
    action, cam_id = callback.data.split(":", 1)

    if action not in CALLBACK_ACTIONS:
        await callback.message.answer("Неизвестное действие.")
        return

    data = await state.get_data()
    valid_ids = data.get("camera_ids", [])
    if cam_id not in valid_ids:
        await callback.message.answer("Камера не найдена или устарела.")
        return

    try:
        action_func = CALLBACK_ACTIONS[action]
        result = await action_func(cam_id)
        if action == "reinit_camera":
            await asyncio.sleep(3)
        await callback.message.answer(result["message"])
    except ValueError as e:
        await callback.message.answer(f"Ошибка: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error in {action} for camera {cam_id}: {str(e)}")
        await callback.message.answer("Произошла непредвиденная ошибка.")

@dp.message(Command("exit"))
@token_required
async def cmd_logout(message: types.Message, state: FSMContext):
    """exit"""
    await state.clear()
    tg_id = message.from_user.id
    await Userbot.exit_user_bot(tg_id)
    await message.answer("Вы вышли из системы. Чтобы снова войти, используйте /start.")


async def main():
    """Start bot polling."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
