# Admin UI

A small Streamlit console for the Review Intelligence Tool. It is a separate
client: it talks to the Flask API over HTTP and does not import or change the
core project, so the API remains the only place behaviour lives.

## What it covers

- **Topics**: list topics and create one, including the per-topic relevance
  strictness level (strict / standard / loose).
- **Reviews**: submit a review and see the AI validation gate accept it or
  reject it with a reason, and list a topic's stored reviews.
- **Evaluate**: run the AI evaluation on a topic and read the structured result.
- **Agent chat**: talk to the threaded Evaluation Agent, including its
  verified-topic memory across turns.

## Run it (one step)

The simplest way starts the API and the UI together and opens the UI in your
browser. From the project root:

- **Double-click `run_ui.bat`**, or
- run `.venv\Scripts\python.exe run_ui.py`

Press `Ctrl+C` in that window (or close it) to stop both.

First time only, install the UI dependencies: `pip install -r ui/requirements.txt`.

## Run it (two terminals)

If you prefer to run the two processes yourself, with the virtual environment active:

```bash
# terminal 1: the API
flask --app app run

# terminal 2: the UI
streamlit run ui/streamlit_app.py
```

The UI defaults to `http://127.0.0.1:5000`. Point it elsewhere with the
`API_BASE_URL` environment variable or the field in the sidebar.
