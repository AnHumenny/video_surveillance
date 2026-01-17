# Система видеонаблюдения на Python

Проект реализует видеонаблюдение с использованием `OpenCV`, `Quart`, `nmap` и других современных библиотек. 
Может запускаться как в Docker, так и локально. Поддерживает сканирование выбранного диапазона сети 
на наличие rtsp-потоков, детекцию движения, запись по запросу, отправку видеозахвата (движение) и/или 
скриншотов на указанный email или в ТГ-бота (aiogram). Сохранённые скриншоты и видео сортируются в 
папки по датам съёмки. Использует SQLite в качестве базы данных.

## Установка

### 1. Установите системные зависимости

### **Linux**
Эти зависимости нужны **до установки Python-библиотек**, особенно `opencv-python`.

```bash
sudo apt update
```
```bash
sudo apt install -y libgl1 nmap ffmpeg
```

### **Windows**
Установите Python 3.12+ (обязательно выберите опцию "Add Python to PATH")

Установите Nmap для Windows

Для OpenCV может понадобиться установить Microsoft Visual C++ Redistributable

### 2. Настройка Python окружения

#### Создайте и активируйте виртуальное окружение
```bash
 python3 -m venv .venv
``` 

### Linux/macOS
```bash
 source .venv/bin/activate
```

### Windows (PowerShell)
```bash
.venv\Scripts\activate
```

### Установите Python-зависимости
```bash
 pip install --upgrade pip
```
```bash
 pip install -r requirements.txt
```

### 3. Настройка переменных окружения
Создайте файл .env в корне проекта 

#### Создайте и копируйте .env
```bash
 cp env_example.txt .env
```

### 4. Инициализация приложения
Из корневой директории приложения выполните:

``` bash 
 python3 -m create.install
```

Запуск
1. Подготовка скрипта запуска
bash
chmod +x start.sh
2. Запуск системы
``` bash
 ./start.sh
```

Скрипт запускает:

- Основной сервер (main.py)

- Telegram-бота (bot/app.py)

- Celery worker (celery_app.celery)

### Альтернативный запуск вручную

#### Запуск основного сервера
``` bash
 python main.py
```
#### Запуск Telegram-бота (в отдельном терминале)
``` bash
 python -m bot.app
```
#### Запуск Celery worker (в отдельном терминале)
``` bash
 celery -A celery_app.celery worker --loglevel=info

```
### Структура проекта
```
video_surveillance/
├── .venv/                              # Виртуальное окружение Python
├── bot/                                # Telegram-бот
│   ├── __init__.py
│   ├── app.py
│   └── lists.py
│
├── celery_task/                        # Celery задачи
│   ├── __init__.py
│   ├── celery_app.py
│   └── tasks.py
│
├── config/                             # Конфигурация
│   ├── __init__.py
│   └── config.py
│
├── create/                             # Скрипты инициализации
│   ├── add_cam.py
│   ├── add_user.py
│   └── install.py
│
├── logs/                               # Логи приложения
├── media/                              # Медиафайлы
│   ├── recordings/                         # Записи видео
│   ├── screenshots/                        # Скриншоты
│   
├── screenshots/      
│   └── current/                        # Текущие скриншоты
│
├── surveillance/                       # Основной проект
│   ├── __init__.py
│   ├── camera_manager.py
│   └── main.py
│   │ 
│   ├── schemas/                            # Схемы и модели БД
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── repository.py
│   │ 
│   ├── static/                             # Статические файлы
│   │   ├── image/                          # Изображения интерфейса
│   │   └── style/                          # Стили CSS
│   │   
│   └── templates/                          # HTML шаблоны
│       ├── menu/                           # Шаблоны меню
│       │   ├── menu_auth.html
│       │   └── menu_top.html
│       ├── camera_view.html
│       ├── control.html
│       ├── head.html
│       ├── index.html
│       └── login.html
│
├── .dockerignore                       # Docker игнорирование
├── .env                                # Переменные окружения
├── .gitignore                          # Git игнорирование
├── bot_app.spec                        # Спецификация для сборки бота
├── celery.pid                          # PID файл Celery
├── db_camera.db                        # База данных SQLite
├── Dockerfile                          # Docker конфигурация
├── env_example.txt                     # Пример .env файла
├── main.spec                           # Спецификация для сборки main
├── README.md                           # Документация проекта
├── requirements.txt                    # Зависимости Python
├── start.sh                            # Скрипт запуска
└── stop.sh                             # Скрипт остановки
```

#### Видео демонстрация

[![Видео демонстрация](https://img.shields.io/badge/Посмотреть_на_youtube-FF0000?style=flat-square)](https://www.youtube.com/watch?v=_Mjlg2G7HMw)