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

### 2. Настройка Python окружения

#### Создайте и активируйте виртуальное окружение
```bash
 python3 -m venv .venv
``` 

### Linux
```bash
 source .venv/bin/activate
```

### Установите Python-зависимости
```bash
 pip install --upgrade pip
```
```bash
 pip install -r requirements.txt
```

### 3. Настройка переменных окружения

#### Создайте и копируйте .env
```bash
 cp env_example.txt .env
```

### 4. Инициализация приложения
Из корневой директории приложения выполните:

``` bash 
 python3 -m surveillance.utils.install.install
```

Запуск
#### 1. Подготовка скрипта запуска
```bash
chmod +x start.sh
```

#### 2. Запуск системы
``` bash
 ./start.sh
```

Скрипт запускает:

- Основной сервер (main.py)

- Telegram-бота (bot/app.py)

- Celery worker (celery_app.celery)

### Структура проекта
```
video_surveillance/
├── .venv/ # Виртуальное окружение Python
├── bot/ # Telegram-бот
│ ├── init.py
│ ├── app.py
│ └── utils/
│ ├── jwt_utils.py # JWT токены и авторизация
│ └── lists.py
│
├── celery_task/ # Celery задачи
│ ├── init.py
│ ├── celery_app.py
│ └── tasks.py
│
├── config/ # Конфигурация
│ ├── init.py
│ └── config.py
│
├── logs/
│ ├── YYYY-MM-DD/ # Логи приложения
│ └── logging_config.py
│
├── media/ # Медиафайлы
│ ├── recordings/ # Записи видео
│ │ └── YYYY-MM-DD/
│ │ ├── cam_1/
│ │ ├── cam_2/
│ │ └── cam_3/
│ └── current/
│ ├── movie/
│ └── screenshots/
│
├── surveillance/ # Основной проект
│ ├── init.py
│ ├── camera_manager.py
│ ├── main.py
│ │
│ ├── schemas/ # Схемы и модели БД
│ │ ├── init.py
│ │ ├── database.py
│ │ └── repository.py
│ │
│ ├── static/ # Статические файлы
│ │ ├── image/ # Изображения интерфейса
│ │ └── style/ # Стили CSS
│ │
│ ├── templates/ # HTML шаблоны
│ │ ├── menu/ # Шаблоны меню
│ │ │ ├── menu_auth.html
│ │ │ └── menu_top.html
│ │ ├── camera_view.html
│ │ ├── control.html
│ │ ├── head.html
│ │ ├── index.html
│ │ └── login.html
│ │
│ └── utils/
│ ├── common.py # Общие утилиты и хелперы
│ ├── hash_utils.py # Хеширование паролей
│ └── jwt_utils.py # JWT токены и авторизация
│
├── .dockerignore # Docker игнорирование
├── .env # Переменные окружения
├── .gitignore # Git игнорирование
├── db_camera.db # База данных SQLite
├── Dockerfile # Docker конфигурация
├── env_example.txt # Пример .env файла
├── README.md # Документация проекта
├── requirements.txt # Зависимости Python
├── start.sh # Скрипт запуска
└── stop.sh # Скрипт остановки


# Структура базы данных

Документация по структуре таблиц базы данных проекта.

## Общая схема

База данных состоит из трех основных таблиц, отвечающих за управление камерами, их поиск в локальной сети и пользователей системы.

---

### Таблица `_camera`

Хранит информацию о каждой подключенной или настроенной камере.

| Поле | Тип | Описание |
| :--- | :--- | :--- |
| `id` | `INTEGER NOT NULL` | Уникальный идентификатор камеры (первичный ключ). |
| `path_to_cam` | `VARCHAR(200)` | Путь или адрес (URL/RTSP) до видеопотока камеры. |
| `status_cam` | `BOOLEAN NOT NULL` | Статус камеры (активна/неактивна, онлайн/оффлайн). |
| `visible_cam` | `BOOLEAN` | Флаг видимости камеры в интерфейсе. |
| `screen_cam` | `BOOLEAN NOT NULL` | Создание скриншотов. |
| `send_email` | `BOOLEAN NOT NULL` | Разрешение на отправку уведомлений (видео, скриншот) по email. |
| `coordinate_x1` | `VARCHAR(12)` | Координата X1 для зоны детекции (левая граница). |
| `coordinate_x2` | `VARCHAR(12)` | Координата X2 для зоны детекции (правая граница). |
| `coordinate_y1` | `VARCHAR(12)` | Координата Y1 для зоны детекции (верхняя граница). |
| `coordinate_y2` | `VARCHAR(12)` | Координата Y2 для зоны детекции (нижняя граница). |
| `send_tg` | `BOOLEAN NOT NULL` | Разрешение на отправку уведомлений (скриншот) в Telegram. |
| `send_video_tg` | `INTEGER DEFAULT 0` | Флаг или таймаут для отправки видео в Telegram (например: 0 - не отправлять, 1 - отправлять). |

---

### Таблица `_find_camera`

Используется для служебных целей — поиска камер в локальной сети.

| Поле | Тип | Описание |
| :--- | :--- | :--- |
| `id` | `INTEGER NOT NULL` | Уникальный идентификатор записи (первичный ключ). |
| `cam_host` | `VARCHAR(200)` | IP-адрес или хост найденной камеры. |
| `subnet_mask` | `VARCHAR(10)` | Маска подсети, в которой производится поиск. |

---

### Таблица `_user`

Содержит данные пользователей для авторизации в системе и интеграции с мессенджерами.

| Поле | Тип | Описание |
| :--- | :--- | :--- |
| `id` | `INTEGER NOT NULL` | Уникальный идентификатор пользователя (первичный ключ). |
| `user` | `VARCHAR(50)` | Имя пользователя (логин). |
| `password` | `VARCHAR(100)` | Хэш пароля. |
| `status` | `VARCHAR(10)` | Статус пользователя (например: `admin`, `user`). |
| `tg_id` | `BIGINT` | Уникальный идентификатор пользователя в Telegram (Chat ID). |
| `active` | `INTEGER` | Флаг активности аккаунта (1 - активен, 0 - заблокирован). |

---

```

#### Видео демонстрация

[![Видео демонстрация](https://img.shields.io/badge/Посмотреть_на_youtube-FF0000?style=flat-square)](https://www.youtube.com/watch?v=_Mjlg2G7HMw)