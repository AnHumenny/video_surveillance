#!/bin/bash
set -e

source "$(dirname "$0")/.venv/bin/activate"

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
            timeout=15
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

        echo "[INFO] All processes stopped."
        exit 0
    fi
}

trap cleanup SIGINT SIGTERM

echo "[INFO] Terminating existing Celery workers..."
pkill -f "celery -A celery_app.celery worker" || true
sleep 2

echo "[INFO] Terminating existing bot..."
pkill -f "bot.app" || true
sleep 2

echo "[INFO] Terminating existing main.py..."
pkill -f "python3 main.py" || true
sleep 2

echo "[INFO] Starting main.py..."
python3 main.py &
MAIN_PID=$!

echo "[INFO] Starting bot.app..."
python3 -m bot.app &
BOT_PID=$!

CELERY_NAME="worker_$(date +%s)_${RANDOM}_$$"
echo "[INFO] Starting Celery worker..."
celery -A celery_app.celery worker \
    --loglevel=info \
    -n ${CELERY_NAME}@%h \
    --concurrency=1 \
    --logfile=celery.log \
    --time-limit=300 \
    --soft-time-limit=280 &
CELERY_PID=$!

wait $MAIN_PID $BOT_PID $CELERY_PID