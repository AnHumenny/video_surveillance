# Система видеонаблюдения на Python

Проект реализует видеонаблюдение с использованием `OpenCV`, `Quart`, `nmap` и других современных библиотек. Может запускаться как в Docker, так и локально.
Поддерживает детекцию движения, сканирование выбранного диапазона сети на наличие rtsp-потоков.
Использует SQLite в качестве базы данных.

## Установка

### Linux / macOS

1. Установите системные зависимости (особенно важно для OpenCV):

```bash
sudo apt update
sudo apt install -y libgl1 nmap
```
### 1. Установите системные зависимости

> Эти зависимости нужны **до установки Python-библиотек**, особенно `opencv-python`.

```bash
sudo apt update
sudo apt install -y libgl1 nmap
```

### Windows
```Установите Python 3.12+ (обязательно выберите опцию "Add Python to PATH").

Установите Nmap для Windows.

Для OpenCV может понадобиться установить Microsoft Visual C++ Redistributable.
```

```Создайте и активируйте виртуальное окружение
python3 -m venv venv
source venv/bin/activate
```

Установите Python-зависимости
pip install --upgrade pip
pip install -r requirements.txt

Структура файла .env в корне:
```
SIZE_VIDEO=1280,720 (720,480  etc...)
DATABASE="имя базы данных"
ADMIN="имя пользователя" (первичная установка)
PASSWORD="пароль" (первичная установка)
SECRET_KEY="secret_key"
HOST="host"
PORT="port"
CAM_HOST="192.168.0.1" (первичный маршрут)
SUBNET_MASK="24" (первичная маска)
```

Из корневой директории приложения
```python3 -m create.install```

Запуск
python ```main.py```