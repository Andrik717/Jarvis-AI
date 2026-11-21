@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist "jarvis\brain.py" (
    echo Не найдена папка jarvis. Положите этот файл в папку Jarvis-AI-main.
    pause
    exit /b 1
)

echo Обновляю мозг, память, интерфейс и мужской голос Джарвиса...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference='Stop'; $files=@(@{Path='jarvis/brain.py';Target='jarvis\brain.py'},@{Path='jarvis/app.py';Target='jarvis\app.py'}); foreach($file in $files) { $temp=$file.Target+'.new'; Invoke-WebRequest -UseBasicParsing -Uri ('https://raw.githubusercontent.com/Andrik717/Jarvis-AI/main/'+$file.Path) -OutFile $temp; if(Test-Path $file.Target){Copy-Item $file.Target ($file.Target+'.bak') -Force}; Move-Item $temp $file.Target -Force }; Write-Host 'Готово! Мозг, память, интерфейс и голос обновлены.' -ForegroundColor Green"
if errorlevel 1 (
    echo Не удалось скачать обновление. Проверьте подключение к интернету.
    pause
    exit /b 1
)

echo.
echo Теперь запустите run.bat
pause
endlocal
