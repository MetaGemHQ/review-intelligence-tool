"""One-step launcher for the admin UI.

Starts the Flask API in the background, waits for it to answer, then runs the
Streamlit UI, which opens in your browser. When you close the UI (Ctrl+C or
closing the window), the API is shut down too.

Run it with the project's virtual environment:

    .venv\\Scripts\\python.exe run_ui.py

or just double-click run_ui.bat.
"""

import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
API_URL = "http://127.0.0.1:5000/topics"


def api_is_up():
    try:
        urlopen(API_URL, timeout=1)
        return True
    except (URLError, OSError):
        return False


def main():
    api_proc = None
    if api_is_up():
        print("API already running on port 5000, reusing it.")
    else:
        print("Starting the API on http://127.0.0.1:5000 ...")
        api_proc = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT)
        for _ in range(40):
            if api_is_up():
                break
            time.sleep(0.5)
        else:
            print("The API did not start. Check that .env has a valid OPENAI_API_KEY.")
            if api_proc:
                api_proc.terminate()
            return 1

    print("Opening the admin UI in your browser ...")
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(ROOT / "ui" / "streamlit_app.py")],
            cwd=ROOT,
        )
    finally:
        if api_proc is not None:
            api_proc.terminate()
            try:
                api_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_proc.kill()
            print("Stopped the API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
