#!/usr/bin/env bash
LOG_FILE="/mnt/c/Users/michael/Documents/antigravity_test/upgrade.log"
exec > "$LOG_FILE" 2>&1

TARGET_PID=7949

echo "[$(date)] Upgrade daemon started. Monitoring agy PID $TARGET_PID..."
while kill -0 "$TARGET_PID" 2>/dev/null; do
    sleep 0.5
done

echo "[$(date)] agy PID $TARGET_PID completed. Waiting 2 seconds for WebSocket delivery..."
sleep 2

echo "[$(date)] Terminating old server processes..."
pkill -f "python.*server\.py" 2>/dev/null || true
sleep 1.5

echo "[$(date)] Launching modular server on port 5000..."
cd /mnt/c/Users/michael/Documents/antigravity_test
/home/michael/alp-env/bin/python3 apply_mods.py
setsid nohup /home/michael/alp-env/bin/python3 server.py > server_stdout.log 2>&1 &

sleep 2
if pgrep -f "server\.py" >/dev/null; then
    echo "[$(date)] Upgrade successful! Modular server is running with PID $(pgrep -f 'server\.py' | head -n 1)."
else
    echo "[$(date)] ERROR: Server failed to start. Check server_stdout.log."
fi
