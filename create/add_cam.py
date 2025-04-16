import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

name_db = os.getenv("DB_CAMERA")
if not name_db:
    raise ValueError("Переменная DB_CAMERA не задана в .env")

camera_info = "rtsp://user:!password@192.168.1.34:554/h265"  # Временно, до увязки с БД

def insert_into_camera():
    """Добавляем камеру в таблицу _camera."""
    camera_table = "_camera"
    db_path = os.path.join('..', f'{name_db}.db')
    try:
        conn = sqlite3.connect(db_path)
        sql = f'''INSERT INTO {camera_table} (path_to_cam) VALUES (?)'''
        conn.execute(sql, (camera_info,))
        conn.commit()
        print(f'Камера {camera_info} добавлена!')
    except sqlite3.Error as e:
        print(f'Ошибка при добавлении камеры: {e}')
    finally:
        conn.close()

insert_into_camera()