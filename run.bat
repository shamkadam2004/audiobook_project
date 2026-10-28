@echo off
cd /d "%~dp0"
echo Installing libraries (first time only) ...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo Install failed. Check your internet connection and that Python is installed.
  pause
  exit /b 1
)
start "" http://127.0.0.1:5000
python app.py
pause
