#!/bin/bash
set -e

celery -A celery_app.celery control shutdown
sleep 5
ps aux | grep 'celery -A celery_app.celery worker'
pkill -f "celery -A celery_app.celery worker"
sleep 2
if pgrep -f "celery -A celery_app.celery worker" > /dev/null 2>&1; then
    echo "[INFO] Celery processes still running, attempting SIGKILL..."
    pkill -9 -f "celery -A celery_app.celery worker"
fi

pkill -f "python3 -X faulthandler main.py"
sleep 2
ps aux | grep 'python3 -X faulthandler main.py'
if pgrep -f "python3 -X faulthandler main.py" > /dev/null 2>&1; then
    echo "[INFO] main.py processes still running, attempting SIGKILL..."
    pkill -9 -f "python3 -X faulthandler main.py"
fi

pkill -f "python3 bot.app.py"
sleep 2
ps aux | grep 'bot.app.py'
if pgrep -f "python3 bot.app.py" > /dev/null 2>&1; then
    echo "[INFO] main.py processes still running, attempting SIGKILL..."
    pkill -9 -f "python3 bot.app.py"
fi