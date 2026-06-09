@echo off
REM Registers two clickable browser links on this user account (no admin needed):
REM   reviewtool:open      starts the API + UI and opens it in the browser
REM   reviewtoolstop:open  stops them
REM Uses this folder's own path, so it works wherever the repo lives.
setlocal
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PYW=%ROOT%\.venv\Scripts\pythonw.exe"
set "SCRIPT=%ROOT%\run_ui.py"

reg add "HKCU\Software\Classes\reviewtool" /ve /d "URL:Review Intelligence Tool" /f
reg add "HKCU\Software\Classes\reviewtool" /v "URL Protocol" /d "" /f
reg add "HKCU\Software\Classes\reviewtool\shell\open\command" /ve /d "\"%PYW%\" \"%SCRIPT%\"" /f

reg add "HKCU\Software\Classes\reviewtoolstop" /ve /d "URL:Stop Review Intelligence Tool" /f
reg add "HKCU\Software\Classes\reviewtoolstop" /v "URL Protocol" /d "" /f
reg add "HKCU\Software\Classes\reviewtoolstop\shell\open\command" /ve /d "\"%PYW%\" \"%SCRIPT%\" stop" /f

echo.
echo Registered the reviewtool: and reviewtoolstop: links.
echo Open links.html and bookmark the two links, or add bookmarks pointing to
echo   reviewtool:open   and   reviewtoolstop:open
pause
