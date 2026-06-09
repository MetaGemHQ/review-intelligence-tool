@echo off
REM Removes the login autostart and stops the tool if it is running.
setlocal
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ReviewIntelligenceTool.vbs"

if exist "%VBS%" del "%VBS%"
"%ROOT%\.venv\Scripts\python.exe" "%ROOT%\run_ui.py" stop

echo Autostart removed and the tool stopped.
pause
