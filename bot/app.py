import asyncio
from typing import Dict, Callable

from aiogram import Bot, Dispatcher, types, F
import os
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, WebAppInfo, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.jwt_utils import create_jwt_token, token_required
from surveillance.main import force_start_cam

from bot.utils import lists
from surveillance.schemas.repository import  Userbot, Cameras
from dotenv import load_dotenv

from surveillance.utils.hash_utils import hash_password

API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

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


async def create_password_keyboard() -> InlineKeyboardMarkup:
    """Creates the main keyboard for entering the password."""
    builder = InlineKeyboardBuilder()

    for i in range(1, 10):
        builder.button(text=str(i), callback_data=f"pass_{i}")
    builder.button(text="0", callback_data="pass_0")

    builder.button(text="a-z", callback_data="pass_mode_letters")
    builder.button(text="A-Z", callback_data="pass_mode_caps")

    builder.button(text="⌫", callback_data="pass_back")
    builder.button(text="✅", callback_data="pass_enter")
    builder.button(text="❌", callback_data="pass_cancel")

    builder.adjust(3, 3, 3, 3)
    return builder.as_markup()


async def create_letters_keyboard(mode: str = "letters") -> InlineKeyboardMarkup:
    """Creates an alphabetic keyboard."""
    builder = InlineKeyboardBuilder()

    if mode == "letters":
        letters = "abcdefghijklmnopqrstuvwxyz"
    else:
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for i in range(0, len(letters), 8):
        row_letters = letters[i:i + 8]
        for letter in row_letters:
            builder.button(text=letter, callback_data=f"pass_{letter}")

    builder.button(text="123", callback_data="pass_mode_digits")
    builder.button(text="⌫", callback_data="pass_back")
    builder.button(text="✅", callback_data="pass_enter")
    builder.button(text="❌", callback_data="pass_cancel")

    builder.adjust(8, 8, 8, 2, 2, 2)
    return builder.as_markup()


async def create_special_keyboard() -> InlineKeyboardMarkup:
    """Creates a keyboard with special characters."""
    builder = InlineKeyboardBuilder()

    special_chars = "!@#$%^&*()-_=+[]{}|;:,.<>?/~"

    for i in range(0, len(special_chars), 6):
        row_chars = special_chars[i:i + 6]
        for char in row_chars:
            builder.button(text=char, callback_data=f"pass_{char}")

    builder.button(text="123", callback_data="pass_mode_digits")
    builder.button(text="ABC", callback_data="pass_mode_letters")
    builder.button(text="⌫", callback_data="pass_back")
    builder.button(text="✅", callback_data="pass_enter")
    builder.button(text="❌", callback_data="pass_cancel")

    builder.adjust(6, 6, 6, 6, 5)
    return builder.as_markup()

user_temp_passwords = {}

@dp.callback_query(F.data.startswith("pass_"), AuthStates.waiting_for_password)
async def process_password_input(callback: CallbackQuery, state: FSMContext):
    """Password entry processing via buttons."""
    user_id = callback.from_user.id
    full_data = callback.data
    action = full_data.split("_")[1]

    if user_id not in user_temp_passwords:
        user_temp_passwords[user_id] = ""

    if full_data.startswith("pass_mode_"):
        mode = full_data.split("_")[2]
        if mode == "digits":
            keyboard = await create_password_keyboard()
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
        del user_temp_passwords[user_id]
        return
    else:
        if len(user_temp_passwords[user_id]) < 20:
            symbol = full_data[5:]
            user_temp_passwords[user_id] += symbol

    await update_password_display(callback)


async def update_password_display(callback: CallbackQuery):
    """Updates the masked password display."""
    user_id = callback.from_user.id
    current_password = user_temp_passwords.get(user_id, "")

    masked_password = "•" * len(current_password) if current_password else "••••••"

    keyboard = await create_password_keyboard()

    await callback.message.edit_text(
        f"Введите пароль используя кнопки ниже:\n\n"
        f"Пароль: {masked_password}",
        reply_markup=keyboard
    )
    await callback.answer()


async def show_letters_keyboard(callback: CallbackQuery, keyboard_type: str):
    """Shows the alphabetic keyboard."""
    builder = InlineKeyboardBuilder()

    if keyboard_type == "letters":
        letters = "abcdefghijklmnopqrstuvwxyz"
    else:
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for i in range(0, len(letters), 6):
        row_letters = letters[i:i + 6]
        for letter in row_letters:
            builder.button(text=letter, callback_data=f"pass_{letter}")

    builder.button(text="123", callback_data="pass_switch_digits")
    builder.button(text="⌫", callback_data="pass_back")
    builder.button(text="✅", callback_data="pass_enter")
    builder.button(text="❌", callback_data="pass_cancel")

    builder.adjust(6, 6, 6, 6, 4)

    masked_password = "•" * len(user_temp_passwords.get(callback.from_user.id, ""))
    await callback.message.edit_text(
        f"Введите пароль:\n\nПароль: {masked_password}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


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

    keyboard = await create_password_keyboard()
    await message.answer(
        "Теперь введите пароль используя кнопки ниже:\n\n"
        "Пароль: ••••••",
        reply_markup=keyboard
    )
    await state.set_state(AuthStates.waiting_for_password)


@dp.callback_query(F.data.startswith("pass_"), AuthStates.waiting_for_password)
async def process_password_input(callback: CallbackQuery, state: FSMContext):
    """Password entry processing via buttons."""
    user_id = callback.from_user.id
    action = callback.data.split("_")[1]

    if user_id not in user_temp_passwords:
        user_temp_passwords[user_id] = ""

    if action == "back":
        user_temp_passwords[user_id] = user_temp_passwords[user_id][:-1]
    elif action == "enter":
        await process_final_password(callback, state)
        return
    elif action == "cancel":
        await callback.message.edit_text("❌ Ввод пароля отменен")
        await state.clear()
        del user_temp_passwords[user_id]
        return
    else:
        if len(user_temp_passwords[user_id]) < 20:
            user_temp_passwords[user_id] += action

    masked_password = "•" * len(user_temp_passwords[user_id])
    if not masked_password:
        masked_password = "••••••"

    keyboard = await create_password_keyboard()

    await callback.message.edit_text(
        f"Введите пароль используя кнопки ниже:\n\n"
        f"Пароль: {masked_password}",
        reply_markup=keyboard
    )
    await callback.answer()


async def process_final_password(callback: CallbackQuery, state: FSMContext):
    """Final password processing."""
    user_id = callback.from_user.id
    password = user_temp_passwords.get(user_id, "")

    if not password:
        await callback.answer("Пароль не может быть пустым!", show_alert=True)
        return

    if user_id in user_temp_passwords:
        del user_temp_passwords[user_id]

    user_data = await state.get_data()
    username = user_data.get('username')
    encoded_password = hash_password(password)

    await callback.message.edit_reply_markup(reply_markup=None)

    result = await Userbot.auth_user_bot(username, encoded_password)

    if result is None:
        Info.count += 1
        if Info.count == 3:
            await callback.message.answer(
                text="Неверный пароль. Ты заблокирован на 60 секунд."
            )
            await asyncio.sleep(60)
            await callback.message.answer(text="нажми /start")
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
        await state.update_data(jwt_token=token, status=result.status, chat_id=callback.message.chat.id)
        await callback.message.answer(
            text=f"Добро пожаловать, {result.user}!\nТеперь можешь написать /help."
        )
    else:
        await callback.message.answer(text="Не зашло с паролем :(")
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
    await message.answer("Включить/отключить скрин в ТГ:", reply_markup=builder.as_markup())


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
