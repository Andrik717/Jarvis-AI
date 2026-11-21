@echo off
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=py -3.12"
%PY% -m jarvis
if errorlevel 1 (
  echo.
  echo Jarvis завершился с ошибкой. Проверьте сообщения выше.
  pause
)
endlocal
