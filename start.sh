#!/bin/bash

source "$(dirname "$0")/.venv/bin/activate"
python3 main.py &
python3 -m bot.app &
celery -A celery_app.celery worker --loglevel=info