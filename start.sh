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

LOG_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CELERY_LOGFILE="logs/celery_${LOG_TIMESTAMP}.log"

CLEANUP_DONE=0
cleanup() {
    if [ "$CLEANUP_DONE" -eq 0 ]; then
        CLEANUP_DONE=1
        echo "[INFO] Stopping all processes..."

        for pid in $MAIN_PID $BOT_PID $CELERY_PID; do
            if ps -p $pid > /dev/null 2>&1; then
                pgid=$(ps -o pgid= -p $pid | tr -d ' ')
                echo "[INFO] Sending SIGTERM to process group $pgid (pid $pid)..."
                kill -TERM -$pgid 2>/dev/null || true
            fi
        done

        for pid in $MAIN_PID $BOT_PID $CELERY_PID; do
            timeout=60
            while kill -0 $pid 2>/dev/null && [ $timeout -gt 0 ]; do
                sleep 1
                timeout=$((timeout-1))
            done
        done

        for pid in $MAIN_PID $BOT_PID $CELERY_PID; do
            if ps -p $pid > /dev/null 2>&1; then
                pgid=$(ps -o pgid= -p $pid | tr -d ' ')
                echo "[INFO] Force killing process group $pgid (pid $pid)..."
                kill -KILL -$pgid 2>/dev/null || true
            fi
        done

        echo "[INFO] Freeing port..."
        fuser -k -TERM $PORT/tcp || true
        sleep 2
        if lsof -i :$PORT > /dev/null 2>&1; then
            echo "[INFO] Port still in use, attempting SIGKILL..."
            fuser -k -KILL $PORT/tcp || true
        fi

        echo "[INFO] Checking for remaining processes..."
        ps aux | grep -E 'python3|celery|bot.app|ffmpeg' | grep -v grep || true
        echo "[INFO] Checking port..."
        lsof -i :$PORT || true
        echo "[INFO] Checking active Celery tasks..."
        celery -A celery_app.celery inspect active || true
        echo "[INFO] Checking SQLite database file..."
        ls -l "$(dirname "$0")/../${DATABASE}.db" || true

        echo "[INFO] All processes stopped."
        exit 0
    fi
}

trap cleanup SIGINT SIGTERM

exec > >(tee -a logs/start.log) 2>&1

echo "[INFO] Checking existing processes..."
ps aux | grep -E 'python3|celery|bot.app|ffmpeg' | grep -v grep || true
echo "[INFO] Checking port..."
lsof -i :$PORT || true
echo "[INFO] Checking active Celery tasks..."
celery -A celery_app.celery inspect active || true

echo "[INFO] Terminating existing Celery workers..."
pkill -f "celery -A celery_app.celery worker" || true
sleep 2

echo "[INFO] Terminating existing bot..."
pkill -f "bot.app" || true
sleep 2

echo "[INFO] Terminating existing main.py..."
pkill -f "python3 main.py" || true
sleep 2

echo "[INFO] Terminating existing FFmpeg processes..."
pkill -f "ffmpeg" || true
sleep 2

echo "[INFO] Freeing port..."
fuser -k -TERM $PORT/tcp || true
sleep 2

echo "[INFO] Starting main.py..."
python3 -X faulthandler main.py &
MAIN_PID=$!
echo $MAIN_PID > main.pid

echo "[INFO] Starting bot.app..."
python3 -m bot.app &
BOT_PID=$!
echo $BOT_PID > bot.pid

CELERY_NAME="worker_$(date +%s)_${RANDOM}_$$"
echo "[INFO] Starting Celery worker with log file: $CELERY_LOGFILE"
celery -A celery_app.celery worker \
    --loglevel=info \
    -n ${CELERY_NAME}@%h \
    --concurrency=1 \
    --logfile="$CELERY_LOGFILE" \
    --time-limit=300 \
    --soft-time-limit=280 &
CELERY_PID=$!
echo $CELERY_PID > celery.pid
