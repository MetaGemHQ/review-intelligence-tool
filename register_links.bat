@echo off
REM Registers one clickable browser link on this user account (no admin needed):
REM   reviewtool:open   starts the API + UI and opens it in the browser
REM Stopping is done from the "Shut down app" button inside the UI.
REM Uses this folder's own path, so it works wherever the repo lives.
setlocal
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PYW=%ROOT%\.venv\Scripts\pythonw.exe"
set "SCRIPT=%ROOT%\run_ui.py"

reg add "HKCU\Software\Classes\reviewtool" /ve /d "URL:Review Intelligence Tool" /f
reg add "HKCU\Software\Classes\reviewtool" /v "URL Protocol" /d "" /f
reg add "HKCU\Software\Classes\reviewtool\shell\open\command" /ve /d "\"%PYW%\" \"%SCRIPT%\"" /f

echo.
echo Registered the reviewtool: link.
echo Open links.html and bookmark the link, or add a bookmark pointing to
echo   reviewtool:open
pause
