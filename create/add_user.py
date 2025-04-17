import hashlib
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

name_db = os.getenv("DATABASE")
password = hashlib.sha256(os.getenv("PASSWORD").encode()).hexdigest()   #временно, до увязки с БД
user_info = ["1", f"{password}", "user"]  #временно, до увязки с БД


def insert_into_user():
    """Добавляем первичного пользователя(данные берём из .env)"""
    user_table = "_user"
    db_path = os.path.join("..", f'{name_db}.db')
    try:
        conn = sqlite3.connect(db_path)
        sql = f'''INSERT INTO {user_table} (user, password, status) VALUES (?, ?, ?)'''
        conn.execute(sql, user_info)
        conn.commit()
        print(f'Пользователь {user_info[0]} добавлен!')
    except sqlite3.Error as e:
        print(f'Ошибка при добавлении пользователя: {e}')
    finally:
        conn.close()

insert_into_user()