@echo off
setlocal
cd /d "%~dp0"
py -m venv .venv
if errorlevel 1 goto :error
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :error
pip install -e .
if errorlevel 1 goto :error
echo.
echo Setup completed. Run run_windows.bat next.
pause
exit /b 0

:error
echo.
echo Setup failed. Confirm that Python 3.11 or 3.12 is installed.
pause
exit /b 1

