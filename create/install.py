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



#
# def wiev_info():
#     name_db = input('name DB: ')
#     name_table = input('name table: ')
#     conn = sqlite3.connect(name_db+'.db')
#     result = conn.execute(f'SELECT * FROM {name_table}')
#     for row in result:
#         print(*row)
#     conn.close()
#
# def add_tables():
#     name_db = input('name DB: ')
#     name_table = input('name table: ')
#     conn = sqlite3.connect(name_db+'.db')
#     conn.execute(f'''
#                  CREATE TABLE IF NOT EXISTS {name_table}(
#                      id INTEGER PRIMARY KEY AUTOINCREMENT,
#                      name VARCHAR(20),
#                      full_name VARCHAR(20),
#                      age INTEGER(2)
#                  );
#                  ''')
#     print(f'the tables {name_table} has been added!')
#     conn.commit()
#     conn.close()
#
#
# def view_tables():
#     base_name = input('name DB: ')
#     conn = sqlite3.Connection(base_name+'.db')
#     select_tables = conn.execute(f'SELECT name FROM main')
#     for row in select_tables:
#         print(*row)
#
#
# n = int(input("1-создать БД, 2-добавить инфу, 3-посмотреть существующую информацию, 4-добавить таблицу,"
#               "5-посмотреть таблицы:"))
# if n == 1:
#     start()
# if n == 2:
#     insert_into()
# if n == 3:
#     wiev_info()
# if n == 4:
#     add_tables()
# if n == 5:
#     view_tables()