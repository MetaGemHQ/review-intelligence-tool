# Review Intelligence Tool

Batch-processes customer reviews via an LLM API to produce structured intelligence reports: sentiment breakdown, recurring themes, ranked pain points, and positive drivers with supporting quotes. Built for marketing managers and brand owners who currently read reviews one by one.

MSIT AI Engineering course project.

## Architecture

Three-layer onion, per the architectural guidance of project mentor **Stavros**. Calls flow strictly inward — outer layers may call inner layers, never the reverse, and **controllers must never call repositories directly**.

- **Controllers** (`app.py`) — HTTP routes only. No business logic, no DB access.
- **Services** (`services/`) — business logic, validation, orchestration.
- **Repositories** (`repositories/`) — pure SQL only. No logic, no validation; trust the caller.

Batching parameters (`max_reviews_per_batch`, `max_review_chars`) are config-driven (`config.json`), not hardcoded — tuning later is a one-line change.

## Setup

Requires Python 3.13+ and a virtual environment.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# then edit .env and set OPENAI_API_KEY
```

## Run

```powershell
python app.py
```

Then open <http://localhost:5000>.

## Admin UI (optional)

A separate Streamlit console under `ui/` drives the API over HTTP without
touching the core project. It covers topic creation (with the per-topic
relevance strictness level), review submission against the validation gate,
evaluations, and the threaded Evaluation Agent.

For a permanent one-click setup, double-click `install_autostart.bat` once: the
tool then starts hidden at every login and serves `http://localhost:8501`, which
you bookmark. To launch it manually instead, double-click `run_ui.bat`. See
`ui/README.md` for details and the two-terminal alternative.
