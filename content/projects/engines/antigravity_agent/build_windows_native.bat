@echo off
echo ======================================================
echo    Starting Windows Native Build (Nuitka)
echo ======================================================

echo [1/3] Ensuring dependencies are installed...
pip install nuitka quart websockets pywebview google-antigravity

echo.
echo [2/3] Launching Python build script...
python remote_compiler.py

echo.
echo ======================================================
echo    Build Process Completed
echo ======================================================
pause
