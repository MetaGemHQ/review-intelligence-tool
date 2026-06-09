"""Launcher for the admin UI.

  python run_ui.py          start the API + UI and open the browser
  python run_ui.py stop     stop the API + UI started earlier

Start brings up the Flask API in the background, waits for it, then runs the
Streamlit UI, which opens in your browser. It records both process ids so that
`stop` (or closing the launcher window) shuts everything down cleanly. Clicking
the launch link again while it is already running just reopens the browser tab.
"""

import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
API_URL = "http://127.0.0.1:5000/topics"
UI_URL = "http://127.0.0.1:8501/"
RUNFILE = ROOT / "data" / "ui_pids.json"


def _is_up(url):
    try:
        urlopen(url, timeout=1)
        return True
    except (URLError, OSError):
        return False


def _kill(pid):
    # /T also ends child processes (e.g. the Streamlit server under its parent).
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, text=True)


def stop():
    if not RUNFILE.exists():
        print("Nothing recorded as running.")
        return 0
    pids = json.loads(RUNFILE.read_text())
    for key in ("ui", "api"):
        pid = pids.get(key)
        if pid:
            _kill(pid)
            print(f"Stopped {key} (pid {pid}).")
    RUNFILE.unlink(missing_ok=True)
    return 0


def start():
    if _is_up(UI_URL):
        print("Admin UI already running, opening it in the browser.")
        webbrowser.open(UI_URL)
        return 0

    print("Starting the API on http://127.0.0.1:5000 ...")
    # Force the reloader off so the API is a single process we can stop cleanly
    # (a debug reloader spawns a child that owns the socket and escapes the kill).
    # load_dotenv does not override an already-set env var, so this wins.
    api_env = {**os.environ, "FLASK_DEBUG": "0"}
    api_proc = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT, env=api_env)
    for _ in range(40):
        if _is_up(API_URL):
            break
        time.sleep(0.5)
    else:
        print("The API did not start. Check that .env has a valid OPENAI_API_KEY.")
        api_proc.terminate()
        return 1

    print("Opening the admin UI in your browser ...")
    ui_proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "ui" / "streamlit_app.py")],
        cwd=ROOT,
    )
    RUNFILE.parent.mkdir(exist_ok=True)
    RUNFILE.write_text(json.dumps({"api": api_proc.pid, "ui": ui_proc.pid}))
    try:
        ui_proc.wait()
    finally:
        api_proc.terminate()
        try:
            api_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_proc.kill()
        RUNFILE.unlink(missing_ok=True)
        print("Stopped the API.")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower().startswith("stop"):
        return stop()
    return start()


if __name__ == "__main__":
    raise SystemExit(main())
