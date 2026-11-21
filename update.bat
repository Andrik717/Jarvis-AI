@echo off
setlocal
cd /d "%~dp0"

if not exist "jarvis\brain.py" (
    echo Не найдена папка jarvis. Положите этот файл в папку Jarvis-AI-main.
    pause
    exit /b 1
)

echo Обновляю мозг и голос Джарвиса...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference='Stop'; $base='https://raw.githubusercontent.com/Andrik717/Jarvis-AI/main/jarvis'; foreach($name in @('brain.py','tts.py')) { $target=Join-Path 'jarvis' $name; $temp=$target+'.new'; Invoke-WebRequest -UseBasicParsing -Uri ($base+'/'+$name) -OutFile $temp; if(Test-Path $target){Copy-Item $target ($target+'.bak') -Force}; Move-Item $temp $target -Force }; Write-Host 'Готово! Файлы обновлены.' -ForegroundColor Green"
if errorlevel 1 (
    echo Не удалось скачать обновление. Проверьте подключение к интернету.
    pause
    exit /b 1
)

echo.
echo Теперь запустите run.bat
pause
endlocal
