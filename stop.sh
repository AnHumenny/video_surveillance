#!/bin/bash
set +e

cd "$(dirname "$0")" || { echo "Error: Cannot enter script directory" >&2; exit 1; }

PYTHONPATH="$(pwd):$PYTHONPATH"
export PYTHONPATH

echo "[INFO] Shutting down Celery workers..."
echo "[INFO] Purging Celery tasks..."
celery -A celery_task purge -f || echo "[WARNING] Failed to purge Celery tasks."
sleep 2

echo "[INFO] Stopping Celery Beat..."
pkill -f "celery -A celery_task beat" || true
sleep 1
pkill -9 -f "celery -A celery_task beat" 2>/dev/null || true

echo "[INFO] Shutting down Celery workers..."
celery -A celery_task control shutdown || echo "[WARNING] Celery shutdown failed, workers may already be stopped."
sleep 5

if pgrep -f "celery -A celery_task worker" > /dev/null 2>&1; then
    echo "[INFO] Celery processes still running, sending SIGTERM..."
    pkill -f "celery -A celery_task worker" || true
    sleep 5
    if pgrep -f "celery -A celery_task worker" > /dev/null 2>&1; then
        echo "[INFO] Celery processes still running, forcing SIGKILL..."
        pkill -9 -f "celery -A celery_task worker" || true
    fi
fi

echo "[INFO] Checking Celery status..."
celery -A celery_task inspect active || echo "[INFO] No active Celery workers."

echo "[INFO] Stopping surveillance/main.py..."
pkill -f "python3 -m surveillance.main" || true
if pgrep -f "python3 -m surveillance.main" > /dev/null 2>&1; then
    echo "[INFO] surveillance/main.py still running, forcing SIGKILL..."
    pkill -9 -f "python3 -m surveillance.main" || true
fi

echo "[INFO] Terminating existing FFmpeg processes..."
pkill -f "ffmpeg" || true
sleep 2
if pgrep -f "ffmpeg" > /dev/null 2>&1; then
    echo "[INFO] FFmpeg processes still running, attempting SIGKILL..."
    pkill -9 -f "ffmpeg" || true
fi

echo "[INFO] Stopping bot.app..."
pkill -f "python3 -m bot.app" || true
if pgrep -f "python3 -m bot.app" > /dev/null 2>&1; then
    echo "[INFO] bot.app still running, forcing SIGKILL..."
    pkill -9 -f "python3 -m bot.app" || true
fi

echo "[INFO] All processes stopped."

echo "[INFO] Active python3 processes:"
pgrep -af python3 || echo "[INFO] No python3 processes."

echo "[INFO] Active celery processes:"
pgrep -af celery || echo "[INFO] No celery processes."

echo "[INFO] Active bot.app processes:"
pgrep -af "python3 -m bot.app" || echo "[INFO] No bot.app processes."

rm -f main.pid bot.pid celery_task.pid celery_beat.pid celery_beat-schedule* || true

exit 0