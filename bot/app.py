import asyncio
import datetime
import hashlib
import logging
from functools import wraps
from aiogram import Bot, Dispatcher, types
import os
import jwt
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command, StateFilter
from bot import lists
from schemas.repository import Repo
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

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
        if status == "admin":
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
    result = await Repo.auth_user_bot(username, encoded_password)
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
        await state.update_data(jwt_token=token, chat_id=message.chat.id)

        await state.clear()
        await state.update_data(jwt_token=token)
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


@dp.message(Command("exit"))
async def cmd_logout(message: types.Message, state: FSMContext):
    """exit"""
    await state.clear()
    tg_id = message.from_user.id
    await Repo.exit_user_bot(tg_id)

    await message.answer("Вы вышли из системы. Чтобы снова войти, используйте /start.")


async def main():
    """start"""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
