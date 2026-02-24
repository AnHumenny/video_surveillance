import asyncio
from typing import Dict, Callable

from aiogram import Bot, Dispatcher, types, F
import os
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, WebAppInfo, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from bot.utils.jwt_utils import token_required
from bot.utils.keyboard_utils import create_password_keyboard, create_letters_keyboard
from bot.utils.password_utils import process_final_password, update_password_display
from bot.utils.storage import AuthStates, user_temp_passwords
from bot.utils.lists import send

from surveillance.schemas.repository import Userbot, Cameras
from surveillance.utils.common import force_start_cam

API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

load_dotenv()

@dp.callback_query(F.data.startswith("pass_"), AuthStates.waiting_for_password)
async def process_password_input(callback: types.CallbackQuery, state: FSMContext):
    """Password entry processing via buttons."""
    user_id = callback.from_user.id
    full_data = callback.data
    action = full_data.split("_")[1]

    if user_id not in user_temp_passwords:
        user_temp_passwords[user_id] = ""

    if full_data.startswith("pass_mode_"):
        mode = full_data.split("_")[2]
        if mode == "digits":
            keyboard = create_password_keyboard(user_temp_passwords, user_id)
        elif mode == "letters":
            keyboard = await create_letters_keyboard("letters")
        elif mode == "caps":
            keyboard = await create_letters_keyboard("caps")

        masked_password = "•" * len(user_temp_passwords[user_id])
        await callback.message.edit_text(
            f"Введите пароль:\n\nПароль: {masked_password}",
            reply_markup=keyboard
        )
        await callback.answer()
        return

    if action == "back":
        user_temp_passwords[user_id] = user_temp_passwords[user_id][:-1]
    elif action == "enter":
        await process_final_password(callback, state)
        return
    elif action == "cancel":
        await callback.message.edit_text("❌ Ввод пароля отменен")
        await state.clear()
        if user_id in user_temp_passwords:
            del user_temp_passwords[user_id]
        return
    else:
        if len(user_temp_passwords[user_id]) < 20:
            symbol = action
            user_temp_passwords[user_id] += symbol

    await update_password_display(callback)


@dp.message(StateFilter(None), Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    """Start(enter login)"""
    await message.answer("Введите логин:")
    await state.set_state(AuthStates.waiting_for_login)


@dp.message(AuthStates.waiting_for_login)
async def process_login(message: types.Message, state: FSMContext):
    """Switching to entering the password via the keyboard."""
    await state.update_data(username=message.text)

    user_temp_passwords[message.from_user.id] = ""

    keyboard = create_password_keyboard(user_temp_passwords, message.from_user.id)
    await message.answer(
        "Теперь введите пароль используя кнопки ниже:\n\n"
        "Пароль: ••••••",
        reply_markup=keyboard
    )
    await state.set_state(AuthStates.waiting_for_password)


@dp.message(Command("help"))
@token_required
async def cmd_help(message: types.Message, state: FSMContext):
    """help"""
    await message.answer("\n".join(send) if isinstance(send, list) else send)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть админ-панель",
                    web_app=WebAppInfo(url=os.getenv("CLOUDFIRE_URL", "https://example.com")))
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
    camera_objects = await Cameras.select_all_cam()
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
    camera_objects = await Cameras.select_all_cam()
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
    await message.answer("Включить/отключить видео в ТГ:", reply_markup=builder.as_markup())


@dp.message(Command("reinit"))
@token_required
async def reinit_cam(message: types.Message, state: FSMContext):
    """Reinitialize the selected camera"""
    camera_objects = await Cameras.select_all_cam()
    camera_ids = [str(cam.id) for cam in camera_objects]

    await state.update_data(camera_ids=camera_ids)

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔧 Перезапуск камеры", callback_data="-"))

    for cam_id in camera_ids:
        builder.row(
            types.InlineKeyboardButton(text=f"🔁 cam {cam_id}", callback_data=f"reinit_camera:{cam_id}"),
        )
    await message.answer("Реинициализировать камеру:", reply_markup=builder.as_markup())


@dp.callback_query(lambda c: c.data and c.data.split(":")[0] in CALLBACK_ACTIONS.keys())
@token_required
async def action_cam(callback: types.CallbackQuery, state: FSMContext):
    action, cam_id = callback.data.split(":", 1)

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
