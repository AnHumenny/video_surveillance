import hashlib
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

name_db = os.getenv("DATABASE")
password = hashlib.sha256(os.getenv("PASSWORD").encode()).hexdigest()
user_info = ["admin", f"{password}", "test"]


def insert_into_user():
    """Добавляем пользователя"""
    user_table = "_user"
    base_dir = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, f'{name_db}.db')
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
