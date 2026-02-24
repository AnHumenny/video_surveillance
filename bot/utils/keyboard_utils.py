from aiogram.types import InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder


def create_password_keyboard(user_temp_passwords_dict, user_id):
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

    builder.adjust(3, 3, 3, 2, 2, 2)
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


async def show_letters_keyboard(callback: CallbackQuery, keyboard_type: str, user_temp_passwords_dict: dict):
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

    builder.button(text="123", callback_data="pass_mode_digits")
    builder.button(text="⌫", callback_data="pass_back")
    builder.button(text="✅", callback_data="pass_enter")
    builder.button(text="❌", callback_data="pass_cancel")

    builder.adjust(6, 6, 6, 6, 4)

    masked_password = "•" * len(user_temp_passwords_dict.get(callback.from_user.id, ""))
    await callback.message.edit_text(
        f"Введите пароль:\n\nПароль: {masked_password}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()
