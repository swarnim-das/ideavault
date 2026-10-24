@echo off
REM Builds a single-file dist\IdeaVault.exe that runs on any Windows 10/11 PC (no Python needed).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call setup.bat
call .venv\Scripts\activate.bat
pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean --onefile --windowed --name IdeaVault ^
  --icon assets\ideavault.ico --add-data "assets\ideavault.ico;assets" ^
  --version-file version_info.txt --collect-data customtkinter main.py
echo.
echo Built: dist\IdeaVault.exe
pause
