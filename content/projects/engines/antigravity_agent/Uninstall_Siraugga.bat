@echo off
color 0c
echo ======================================================
echo    Siraugga Uninstaller
echo ======================================================
echo.
echo WARNING: This will completely delete the Siraugga application,
echo including your local Access Keys, chat histories, logs,
echo WebView caches, and any Over-The-Air updates.
echo.
echo This action CANNOT be undone.
echo.
set /p confirm="Are you absolutely sure you want to uninstall Siraugga? (Y/N): "
if /I "%confirm%" NEQ "Y" (
    echo Uninstallation cancelled.
    pause
    exit /b
)

echo.
echo [1/4] Terminating any active Siraugga processes...
taskkill /F /IM Siraugga.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/4] Wiping WebView2 caches and temporary app data...
if exist "%LOCALAPPDATA%\Siraugga" rmdir /S /Q "%LOCALAPPDATA%\Siraugga" >nul 2>&1
if exist "%LOCALAPPDATA%\EBWebView" rmdir /S /Q "%LOCALAPPDATA%\EBWebView" >nul 2>&1
if exist "EBWebView" rmdir /S /Q "EBWebView" >nul 2>&1

echo [3/4] Purging Access Keys, Session Databases, and Security Logs...
del /Q sessions.json >nul 2>&1
del /Q keys.json >nul 2>&1
del /Q .devcore_master.key >nul 2>&1
del /Q crash_log*.txt >nul 2>&1
del /Q std*.log >nul 2>&1

echo [4/4] Removing the Siraugga Executable and Live Override architectures...
del /Q Siraugga.exe >nul 2>&1
rmdir /S /Q core >nul 2>&1
rmdir /S /Q security >nul 2>&1
rmdir /S /Q sandbox >nul 2>&1
rmdir /S /Q plugins >nul 2>&1

echo.
color 0a
echo ======================================================
echo    Uninstallation Complete
echo ======================================================
echo Siraugga has been successfully purged from your system.
echo You may now safely delete this empty folder.
pause
(goto) 2>nul & del "%~f0"
