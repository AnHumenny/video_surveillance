#!/bin/bash
set +e

echo "[INFO] Shutting down Celery workers..."
echo "[INFO] Purging Celery tasks..."
celery -A celery_app.celery purge -f || echo "[WARNING] Failed to purge Celery tasks."
sleep 2

echo "[INFO] Shutting down Celery workers..."
celery -A celery_app.celery control shutdown || echo "[WARNING] Celery shutdown failed, workers may already be stopped."
sleep 10
if pgrep -f "celery -A celery_app.celery worker" > /dev/null 2>&1; then
    echo "[INFO] Celery processes still running, sending SIGTERM..."
    pkill -f "celery -A celery_app.celery worker" || true
    sleep 5
    if pgrep -f "celery -A celery_app.celery worker" > /dev/null 2>&1; then
        echo "[INFO] Celery processes still running, forcing SIGKILL..."
        pkill -9 -f "celery -A celery_app.celery worker" || true
    fi
fi
echo "[INFO] Checking Celery status..."
celery -A celery_app.celery inspect active || echo "[INFO] No active Celery workers."

echo "[INFO] Stopping main.py..."
pkill -f "python3 -X faulthandler main.py" || true
if pgrep -f "python3 -X faulthandler main.py" > /dev/null; then
    echo "[INFO] main.py still running, forcing SIGKILL..."
    pkill -9 -f "python3 -X faulthandler main.py" || true
fi

echo "[INFO] Terminating existing FFmpeg processes..."
pkill -f "ffmpeg" || true
sleep 2
if pgrep -f "ffmpeg" > /dev/null 2>&1; then
    echo "[INFO] FFmpeg processes still running, attempting SIGKILL..."
    pkill -9 -f "ffmpeg" || true
fi

echo "[INFO] Stopping bot.app..."
pkill -f "bot.app" || true
if pgrep -f "bot.app" > /dev/null; then
    echo "[INFO] bot.app still running, forcing SIGKILL..."
    pkill -9 -f "bot.app" || true
fi

echo "[INFO] All processes stopped."
ps aux | grep python3 | grep -v grep || true
ps aux | grep celery | grep -v grep || true

exit 0