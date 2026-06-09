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

## Run it

From the project root, with the virtual environment active:

```bash
# 1. install the UI dependencies (once)
pip install -r ui/requirements.txt

# 2. start the API (terminal 1)
flask --app app run

# 3. start the UI (terminal 2)
streamlit run ui/streamlit_app.py
```

The UI defaults to `http://127.0.0.1:5000`. Point it elsewhere with the
`API_BASE_URL` environment variable or the field in the sidebar.
