# Scenarios

Copy-pasteable curl commands for testing the Review Intelligence Tool API. Assumes the Flask dev server is running on http://127.0.0.1:5000.

On Windows PowerShell, `curl` is an alias for `Invoke-WebRequest`. To run the real curl, use `curl.exe` (shown below) or run these from `cmd.exe`.

## POST /topics — Create a topic

Creates a new topic. `category` is optional but, if set, must be one of `company`, `product`, `service`. `created_by` is a free-form string and may be omitted.

```bash
curl.exe -X POST http://127.0.0.1:5000/topics ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"Acme Corp\", \"category\": \"company\", \"created_by\": \"vlad\"}"
```

Expected: `201 Created` with the new topic row.

Error cases:

```bash
curl.exe -X POST http://127.0.0.1:5000/topics -H "Content-Type: application/json" -d "{\"name\": \"\"}"
```

Expected: `400 Bad Request`, `name is required and must be a non-empty string`.

```bash
curl.exe -X POST http://127.0.0.1:5000/topics -H "Content-Type: application/json" -d "{\"name\": \"X\", \"category\": \"bogus\"}"
```

Expected: `400 Bad Request`, message lists the allowed categories.

## GET /topics — List all topics

Returns every topic in the DB as a JSON array.

```bash
curl.exe http://127.0.0.1:5000/topics
```

Expected: `200 OK` with a JSON array (possibly empty).

## POST /reviews — Add a review to a topic

Adds one review to an existing topic. Cap is 20 reviews per topic and 1000 characters per review (configured in `config.py`).

```bash
curl.exe -X POST http://127.0.0.1:5000/reviews ^
  -H "Content-Type: application/json" ^
  -d "{\"topic_id\": 1, \"review_text\": \"Great product, would buy again.\", \"source\": \"manual\"}"
```

Expected: `201 Created` with the new review row.

Error cases:

```bash
curl.exe -X POST http://127.0.0.1:5000/reviews -H "Content-Type: application/json" -d "{\"topic_id\": 99999, \"review_text\": \"hi\"}"
```

Expected: `400 Bad Request`, `Topic 99999 not found`. (Note: this endpoint returns 400 for missing topics, not 404.)

```bash
curl.exe -X POST http://127.0.0.1:5000/reviews -H "Content-Type: application/json" -d "{\"topic_id\": 1, \"review_text\": \"\"}"
```

Expected: `400 Bad Request`, `review_text is required and must be a non-empty string`.

Once a topic has 20 reviews, further adds return `400 Bad Request` with `Topic <id> is at capacity (20 reviews max)`.

## GET /topics/<topic_id>/reviews — List reviews for a topic

Returns every review attached to the given topic.

```bash
curl.exe http://127.0.0.1:5000/topics/1/reviews
```

Expected: `200 OK` with a JSON array (possibly empty if the topic has no reviews yet).

Error case:

```bash
curl.exe http://127.0.0.1:5000/topics/99999/reviews
```

Expected: `404 Not Found`, `Topic 99999 not found`.

## POST /topics/<topic_id>/evaluate — Run AI evaluation

Sends the topic's reviews (capped at 20) to the OpenAI Responses API and returns a summary of the main themes. Uses `gpt-4o-mini`.

```bash
curl.exe -X POST http://127.0.0.1:5000/topics/1/evaluate
```

Expected: `200 OK` with `{topic_id, topic_name, review_count, model, summary}`.

Error cases:

```bash
curl.exe -X POST http://127.0.0.1:5000/topics/99999/evaluate
```

Expected: `404 Not Found`, `Topic 99999 not found`.

```bash
curl.exe -X POST http://127.0.0.1:5000/topics/3/evaluate
```

Expected: `400 Bad Request`, `Topic 3 has no reviews to evaluate` (when the topic exists but has zero reviews).
