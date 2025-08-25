#!/bin/bash
set -e

if [ -f "$(dirname "$0")/.env" ]; then
    source "$(dirname "$0")/.env"
fi

if [ -z "$PORT" ]; then
    echo "[ERROR] PORT is not set. Please define it in .env or environment."
    exit 1
fi

source "$(dirname "$0")/.venv/bin/activate"

mkdir -p logs
exec > >(tee -a logs/start.log) 2>&1

echo "[INFO] Checking existing processes..."
ps aux | grep -E 'python3|celery|bot.app|ffmpeg' | grep -v grep || true
echo "[INFO] Checking port..."
lsof -i :$PORT || true
echo "[INFO] Checking active Celery tasks..."
celery -A celery_app.celery inspect active || true

echo "[INFO] Killing old processes if they exist..."
pkill -f "celery -A celery_app.celery worker" || true
pkill -f "bot.app" || true
pkill -f "python3 main.py" || true
pkill -f "ffmpeg" || true
fuser -k -TERM $PORT/tcp || true
sleep 2

LOG_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CELERY_LOGFILE="logs/celery_${LOG_TIMESTAMP}.log"

echo "[INFO] Starting main.py..."
python3 -X faulthandler main.py &
echo $! > main.pid

echo "[INFO] Starting bot.app..."
python3 -m bot.app &
echo $! > bot.pid

CELERY_NAME="worker_$(date +%s)_${RANDOM}_$$"
echo "[INFO] Starting Celery worker with log file: $CELERY_LOGFILE"
celery -A celery_app.celery worker \
    --loglevel=info \
    -n ${CELERY_NAME}@%h \
    --concurrency=1 \
    --logfile="$CELERY_LOGFILE" \
    --time-limit=300 \
    --soft-time-limit=280 &
echo $! > celery.pid
