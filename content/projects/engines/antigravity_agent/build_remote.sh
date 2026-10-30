#!/bin/bash
TARGET="robert@172.20.10.3"

echo "======================================================"
echo "    Antigravity Remote Build Pipeline (Nuitka)"
echo "    Target: $TARGET"
echo "======================================================"
echo ""

# --- AUTO SSH KEY SETUP ---
# 1. Generate the key silently if it doesn't exist
if [ ! -f ~/.ssh/id_rsa.pub ]; then
    echo "[Setup] Generating secure SSH Key..."
    ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa > /dev/null 2>&1
fi

# 2. Check if passwordless auth is already working
ssh -q -o BatchMode=yes -o ConnectTimeout=5 $TARGET "echo auth_ok" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "======================================================"
    echo "  First-Time Setup: Installing 'Passwordless' Key."
    echo "  Please type Robert's password ONE LAST TIME."
    echo "======================================================"
    # 3. Push the key to the remote Windows machine securely
    # Fix: type con does not read from SSH stdin on Windows. We use powershell to append stdin.
    cat ~/.ssh/id_rsa.pub | ssh $TARGET 'powershell -NoProfile -Command "if (!(Test-Path .ssh)) { New-Item -ItemType Directory -Path .ssh }; $input | Out-File -Append -Encoding ascii .ssh\authorized_keys; icacls .ssh\authorized_keys /inheritance:r /grant ${env:USERNAME}:F"'
    echo ""
    echo "✅ Key installed! You will never have to type the password again."
    echo ""
    sleep 2
fi
# ---------------------------

echo "[1/4] Packaging codebase..."
tar -cf /tmp/devcore_build.tar --exclude='venv' --exclude='.git' --exclude='__pycache__' --exclude='*.exe' -C /mnt/c/Users/michael/Documents/DevCore .

echo ""
echo "[2/4] Transferring to Build Server..."
scp -q /tmp/devcore_build.tar $TARGET:~/devcore_build.tar

echo ""
echo "[3/4] Extracting & Verifying Windows Dependencies..."
# Use powershell for reliable sequential execution regardless of directory existence
# Use powershell for reliable sequential execution regardless of directory existence
ssh -q $TARGET 'powershell -NoProfile -Command "Set-Location \"$env:USERPROFILE\"; if (!(Test-Path DevCore_Build)) { New-Item -ItemType Directory -Path DevCore_Build | Out-Null }; tar -xf devcore_build.tar -C DevCore_Build; Remove-Item devcore_build.tar -Force; Set-Location DevCore_Build; pip install nuitka quart websockets pywebview; pip install --force-reinstall --no-cache-dir google-antigravity"'

echo ""
echo "[4/4] Compiling Native Windows Executable (This will take 5-10 minutes)..."
ssh -q -o ServerAliveInterval=60 -o ServerAliveCountMax=30 $TARGET 'cmd.exe /c "cd /d %USERPROFILE%\DevCore_Build && python remote_compiler.py"'

echo ""
echo "[5/5] Retrieving Compiled Binary..."
scp -q $TARGET:~/DevCore_Build/Siraugga.exe /mnt/c/Users/michael/Documents/DevCore/

echo "======================================================"
echo "✅ Build Complete! Siraugga.exe is ready."
echo "======================================================"
