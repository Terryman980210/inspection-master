@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\inspection-master.exe" (
  echo Run setup_windows.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\inspection-master.exe %*

