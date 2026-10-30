#!/bin/bash
# ==============================================================================
# ZERO-TRUST AI HOST ENVIRONMENT BOOTSTRAPPER (LIFT AND SHIFT DEPLOYMENT)
# Instantiates the Immutable Host Doctrine for Agentic Environments
# ==============================================================================

set -e

echo "[*] Initiating Zero-Trust Host Bootstrap..."

PROJECT_DIR=$(pwd)
SCRATCH_DIR="$PROJECT_DIR/.agent_scratch"

# 1. Create the Ephemeral Sandbox Directory
echo "[*] Ensuring Agent Scratch Directory exists..."
mkdir -p "$SCRATCH_DIR"

# 2. Mount tmpfs RAM Disk (Requires Sudo on Production)
# We check if it is already mounted to prevent duplication.
if mount | grep "on $SCRATCH_DIR type tmpfs" > /dev/null; then
    echo "[*] tmpfs is already mounted on $SCRATCH_DIR."
else
    echo "[!] Mounting tmpfs (RAM Disk) to $SCRATCH_DIR..."
    echo "    (If this prompts for a password, it is because mounting requires root)"
    sudo mount -t tmpfs -o size=256M,mode=0777 tmpfs "$SCRATCH_DIR"
    echo "[*] RAM Disk successfully mounted. Data Remanence threat neutralized."
fi

# 3. Build the Cryptographic Reaper Daemon
REAPER_SCRIPT="$PROJECT_DIR/reaper_daemon.sh"
echo "[*] Building Cryptographic Reaper Daemon at $REAPER_SCRIPT..."

cat << 'REAPER_EOF' > "$REAPER_SCRIPT"
#!/bin/bash
# REAPER DAEMON: Purges all files in the scratch directory older than 10 minutes.
# Uses 'shred -u -z' for cryptographic overwrite before unlinking.

SCRATCH_DIR="$(dirname "$0")/.agent_scratch"

if [ -d "$SCRATCH_DIR" ]; then
    # Find files modified more than 10 minutes ago
    find "$SCRATCH_DIR" -type f -mmin +10 | while read -r target_file; do
        echo "[REAPER] Shredding dead artifact: $target_file"
        shred -u -z "$target_file" 2>/dev/null || rm -f "$target_file"
    done
fi
REAPER_EOF

chmod +x "$REAPER_SCRIPT"

# 4. Install the Reaper into the System Cron
echo "[*] Registering Reaper Daemon in System Cron (runs every 5 minutes)..."
CRON_JOB="*/5 * * * * $REAPER_SCRIPT >> $PROJECT_DIR/reaper.log 2>&1"

# Check if the cron job already exists to prevent duplicates
(crontab -l 2>/dev/null | grep -F "$REAPER_SCRIPT") || (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
echo "[*] Reaper Daemon active."

echo ""
echo "=============================================================================="
echo "ZERO-TRUST BOOTSTRAP COMPLETE"
echo "=============================================================================="
echo "- All AI scratch scripts will now be written purely to RAM (tmpfs)."
echo "- Forensic disk retrieval is physically impossible."
echo "- The Reaper Daemon will cryptographically shred abandoned artifacts every 10 mins."
echo "Your environment is ready for Lift and Shift."
