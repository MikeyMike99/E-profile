@echo off
echo ======================================================
echo    Starting Antigravity Remote Build (Windows to WSL)
echo ======================================================
echo Bridging to WSL to execute the rsync pipeline...
wsl ./build_remote.sh
pause
