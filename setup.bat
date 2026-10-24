@echo off
REM One-time setup: creates a virtual environment and installs dependencies.
cd /d "%~dp0"
set "PY=python"
where py >nul 2>&1 && set "PY=py -3"
echo Using: %PY%
%PY% -m venv .venv || (echo Failed to create virtual environment. Is Python 3.9+ installed? & pause & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || (echo Dependency install failed. & pause & exit /b 1)
echo.
echo Setup complete. Start the app with run.bat
pause
