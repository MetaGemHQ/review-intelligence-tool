@echo off
REM Makes the Review Intelligence Tool start hidden at every login, serving
REM http://localhost:8501, and starts it now. Then just bookmark that URL.
REM No admin needed. To undo, run uninstall_autostart.bat (or delete the file
REM this creates in your Startup folder).
setlocal
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%STARTUP%\ReviewIntelligenceTool.vbs"

> "%VBS%" echo Set sh = CreateObject("WScript.Shell")
>> "%VBS%" echo sh.Run """%ROOT%\.venv\Scripts\pythonw.exe"" ""%ROOT%\run_ui.py"" serve", 0, False

echo Autostart installed:
echo   %VBS%
echo It will run hidden at every login and serve http://localhost:8501
echo.
echo Starting it now...
wscript "%VBS%"
echo.
echo Done. Open http://localhost:8501 in your browser and bookmark it.
echo (Give it a few seconds the first time.)
pause
