import hashlib
import sqlite3
import os
import time
from dotenv import load_dotenv

load_dotenv()

name_db = os.getenv("DATABASE")


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
            find_cam = "_find_camera"

            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {user_table}(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user VARCHAR(20) UNIQUE,
                    password VARCHAR(100), 
                    status VARCHAR(20)
                );
            ''')
            print(f'Таблица {user_table} успешно создана!')
            time.sleep(1)
            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {camera_table}(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path_to_cam VARCHAR(100) UNIQUE,
                    status_cam BOOL,
                    visible_cam BOOL
                );
            ''')
            print(f'Таблица {camera_table} успешно создана!')
            time.sleep(1)

            conn.execute(f'''
                            CREATE TABLE IF NOT EXISTS {find_cam}(
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                cam_host VARCHAR(100),
                                subnet_mask VARCHAR(10)
                            );
                        ''')
            print(f'Таблица {camera_table} успешно создана!')
            time.sleep(1)
            conn.commit()
        except sqlite3.Error as e:
            print(f'Ошибка при создании базы данных или таблиц: {e}')
        finally:
            conn.close()
    else:
        print(f'База данных {name_db}.db уже существует по пути: {os.path.abspath(db_path)}')

password = hashlib.sha256(os.getenv("PASSWORD").encode()).hexdigest()
user_info = [os.getenv("ADMIN"), f"{password}", "admin"]
find_cam_info = [os.getenv("CAM_HOST"), os.getenv("SUBNET_MASK")]

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

def insert_into_find_cam():
    """Добавляем первичные данные маршрута к камере (данные берём из .env)"""
    user_table = "_find_camera"
    db_path = os.path.join('..', f'{name_db}.db')
    try:
        conn = sqlite3.connect(db_path)
        sql = f'''INSERT INTO {user_table} (cam_host, subnet_mask) VALUES (?, ?)'''
        conn.execute(sql, find_cam_info)
        conn.commit()
        print(f'Маршрут {find_cam_info} добавлен!')
    except sqlite3.Error as e:
        print(f'Ошибка при добавлении пользователя: {e}')
    finally:
        conn.close()

create_db()
time.sleep(1)
insert_into_user()
time.sleep(1)
insert_into_find_cam()
