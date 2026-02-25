from aiogram.fsm.state import StatesGroup, State

user_temp_passwords = {}

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
