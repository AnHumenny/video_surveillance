import hashlib
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

name_db = os.getenv("DB_CAMERA")


def create_db():
    """Создаём базу данных и таблицы в родительской директории"""
    db_path = os.path.join('..', f'{name_db}.db')
    find_db = os.path.isfile(db_path)
    if not find_db:
        try:
            conn = sqlite3.connect(db_path)
            print(f'База данных {name_db}.db создана по пути: {os.path.abspath(db_path)}')

            user_table = "_user"
            camera_table = "_camera"

            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {user_table}(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user VARCHAR(20) UNIQUE,
                    password VARCHAR(100), 
                    status VARCHAR(20)
                );
            ''')
            print(f'Таблица {user_table} успешно создана!')

            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {camera_table}(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path_to_cam VARCHAR(20) UNIQUE
                );
            ''')
            print(f'Таблица {camera_table} успешно создана!')

            conn.commit()
        except sqlite3.Error as e:
            print(f'Ошибка при создании базы данных или таблиц: {e}')
        finally:
            conn.close()
    else:
        print(f'База данных {name_db}.db уже существует по пути: {os.path.abspath(db_path)}')

password = hashlib.sha256(os.getenv("PASSWORD").encode()).hexdigest()
user_info = [os.getenv("ADMIN"), f"{password}", "admin"]

def insert_into_user():
    """Добавляем первичного пользователя(данные берём из .env)"""
    user_table = "_user"
    db_path = os.path.join('..', f'{name_db}.db')
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

create_db()
insert_into_user()
