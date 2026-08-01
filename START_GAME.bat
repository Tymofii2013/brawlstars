@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 mini_brawl.py
  goto :check
)
python mini_brawl.py

:check
if not errorlevel 1 exit /b 0
echo.
echo Python was not found or the game crashed.
echo Install Python 3 from https://python.org and enable "Add Python to PATH".
pause
