import asyncio
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from bot.utils.jwt_utils import create_jwt_token
from bot.utils.storage import user_temp_passwords, Info, AuthStates
from surveillance.schemas.repository import Userbot
from surveillance.utils.hash_utils import hash_password


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
            await callback.message.answer(text="Нажми /start")
            Info.count = 0
            await state.clear()
            return
        else:
            await callback.message.answer(text=f"Неверный пароль. Осталось попыток: {3 - Info.count}")
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
        await callback.message.answer(text="Ошибка авторизации.")
        await state.set_state(AuthStates.waiting_for_login)


async def update_password_display(callback: CallbackQuery):
    """Updates the masked password display."""
    from bot.utils.keyboard_utils import create_password_keyboard
    from bot.utils.storage import user_temp_passwords

    user_id = callback.from_user.id
    current_password = user_temp_passwords.get(user_id, "")

    masked_password = "•" * len(current_password) if current_password else "••••••"

    keyboard = create_password_keyboard(user_temp_passwords, user_id)

    await callback.message.edit_text(
        f"Введите пароль используя кнопки ниже:\n\n"
        f"Пароль: {masked_password}",
        reply_markup=keyboard
    )
    await callback.answer()
