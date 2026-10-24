@echo off
REM Launches IdeaVault without a console window.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" call setup.bat
start "" ".venv\Scripts\pythonw.exe" main.py
