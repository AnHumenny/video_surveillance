#!/bin/bash
set -e

trap 'rm -f main.pid bot.pid celery_worker.pid celery_beat.pid; echo "[INFO] Cleanup PID files on exit"' EXIT

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

echo "[INFO] Checking existing processes..."
pgrep aux | grep -E 'python3|celery|bot.app|ffmpeg' | grep -v grep || true

echo "[INFO] Checking port..."
lsof -i :"$PORT" || true
fuser -k -TERM "$PORT"/tcp || true

echo "[INFO] Checking active Celery tasks..."
celery -A celery_task inspect active || true

echo "[INFO] Killing old processes if they exist..."
pkill -f "celery -A celery_task worker" || true
pkill -f "celery -A celery_task beat" || true
pkill -f "python3 -m bot.app" || true
pkill -f "python3 -m surveillance.main" || true
pkill -f "ffmpeg" || true
sleep 2

LOG_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CELERY_WORKER_LOGFILE="logs/celery_worker_${LOG_TIMESTAMP}.log"
CELERY_BEAT_LOGFILE="logs/celery_beat_${LOG_TIMESTAMP}.log"

echo "[INFO] Starting surveillance/main.py..."
python3 -m surveillance.main &
echo "$!" > main.pid

echo "[INFO] Starting bot.app..."
python3 -m bot.app &
echo "$!" > bot.pid

LOG_DATE=$(date +"%Y-%m-%d")
LOG_DIR="logs/$LOG_DATE"
mkdir -p "$LOG_DIR"

CELERY_WORKER_LOGFILE="$LOG_DIR/celery_worker.log"
CELERY_BEAT_LOGFILE="$LOG_DIR/celery_beat.log"

CELERY_WORKER_NAME="worker_$(date +%s)_${RANDOM}_$$"

echo "[INFO] Starting Celery worker with log file: $CELERY_WORKER_LOGFILE"
celery -A celery_task worker \
    --loglevel=info \
    -n "${CELERY_WORKER_NAME}@%h" \
    --concurrency=1 \
    --logfile="$CELERY_WORKER_LOGFILE" \
    --time-limit=300 \
    --soft-time-limit=280 &
echo "$!" > "$LOG_DIR/celery_worker.pid"
sleep 2

echo "[INFO] Starting Celery beat with log file: $CELERY_BEAT_LOGFILE"
celery -A celery_task beat \
    --loglevel=info \
    --logfile="$CELERY_BEAT_LOGFILE" \
    --pidfile="$LOG_DIR/celery_beat.pid" \
    --schedule="$LOG_DIR/celery_beat-schedule.db" &
echo "$!" > "$LOG_DIR/celery_beat.pid"

echo "[INFO] All processes started. Check logs/start.log and celery logs for details."
echo "[INFO] Processes:"
echo "  Main: $(cat main.pid)"
echo "  Bot: $(cat bot.pid)"
echo "  Celery Worker: $(cat "$LOG_DIR/celery_worker.pid")"
echo "  Celery Beat: $(cat "$LOG_DIR/celery_beat.pid")"
