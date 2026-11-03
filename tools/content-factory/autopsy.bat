@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install Python 3.11+ first.
  pause
  exit /b 1
)

python autopsy.py %*
echo.
pause
