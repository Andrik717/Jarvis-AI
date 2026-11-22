@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist "%~dp0update.ps1" (
    echo Не найден update.ps1. Сначала скачайте оба файла обновления.
    pause
    exit /b 1
)

echo Запускаю безопасное обновление Jarvis...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1"
if errorlevel 1 (
    echo.
    echo Обновление не завершено. Проверьте сообщение об ошибке выше.
    pause
    exit /b 1
)

echo.
echo Обновление завершено. Теперь можно запустить run.bat
pause
endlocal