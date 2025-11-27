#!/bin/bash
set -e

trap 'rm -f main.pid bot.pid celery_task.pid; echo "[INFO] Cleanup PID files on exit"' EXIT

cd "$(dirname "$0")"

if [ -f ".env" ]; then
    source ".env"
fi

if [ -z "$PORT" ]; then
    echo "[ERROR] PORT is not set. Please define it in .env or environment."
    exit 1
fi

source ".venv/bin/activate"

PYTHONPATH="$(pwd):$PYTHONPATH"
export PYTHONPATH

mkdir -p logs
exec > >(tee -a logs/start.log) 2>&1

echo "[INFO] Checking existing processes..."
ps aux | grep -E 'python3|celery|bot.app|ffmpeg' | grep -v grep || true

echo "[INFO] Checking port..."
lsof -i :"$PORT" || true
fuser -k -TERM "$PORT"/tcp || true

echo "[INFO] Checking active Celery tasks..."
celery -A celery_task inspect active || true

echo "[INFO] Killing old processes if they exist..."
pkill -f "celery -A celery_task worker" || true
pkill -f "python3 -m bot.app" || true
pkill -f "python3 -m surveillance.main" || true
pkill -f "ffmpeg" || true
sleep 2

LOG_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CELERY_LOGFILE="logs/celery_${LOG_TIMESTAMP}.log"

echo "[INFO] Starting surveillance/main.py..."
python3 -m surveillance.main &
echo "$!" > main.pid


echo "[INFO] Starting bot.app..."
python3 -m bot.app &
echo "$!" > bot.pid

CELERY_NAME="worker_$(date +%s)_${RANDOM}_$$"
echo "[INFO] Starting Celery worker with log file: $CELERY_LOGFILE"
celery -A celery_task worker \
    --loglevel=info \
    -n "${CELERY_NAME}@%h" \
    --concurrency=1 \
    --logfile="$CELERY_LOGFILE" \
    --time-limit=300 \
    --soft-time-limit=280 &
echo "$!" > celery_task.pid

echo "[INFO] All processes started. Check logs/start.log and celery logs for details."