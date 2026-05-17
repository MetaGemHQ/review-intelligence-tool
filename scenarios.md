# Scenarios

Copy-pasteable curl commands for testing the Review Intelligence Tool API. Assumes the Flask dev server is running on http://127.0.0.1:5000.

On Windows PowerShell, `curl` is an alias for `Invoke-WebRequest`. To run the real curl, use `curl.exe` (shown below) or run these from `cmd.exe`.

## POST /topics: Create a topic

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

## GET /topics: List all topics

Returns every topic in the DB as a JSON array.

```bash
curl.exe http://127.0.0.1:5000/topics
```

Expected: `200 OK` with a JSON array (possibly empty).

## POST /reviews: Add a review to a topic

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

## GET /topics/<topic_id>/reviews: List reviews for a topic

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

## POST /topics/<topic_id>/evaluate: Run AI evaluation

Sends the topic's reviews (capped at 20) to the OpenAI Responses API and returns a structured evaluation of the reviews. Uses `gpt-4o-mini` with Structured Outputs. Every call writes one row to `evaluation_runs` for the comparison-table audit trail (model, prompt version + technique, temperature, token usage, latency, cost, and the full structured result blob).

```bash
curl.exe -X POST http://127.0.0.1:5000/topics/1/evaluate
```

Expected: `200 OK` with the run metadata + the typed evaluation:

```json
{
  "run_id": 1,
  "topic_id": 1,
  "topic_name": "Acme Corp",
  "review_count": 5,
  "model": "gpt-4o-mini",
  "temperature": 1.0,
  "prompt_version": "sentiment_v1",
  "prompt_technique": "zero-shot",
  "input_tokens": 2724,
  "output_tokens": 171,
  "latency_ms": 8525,
  "total_cost": 0.0005112,
  "evaluation": {
    "overall_sentiment": "positive",
    "rating": 4,
    "short_summary": "Customers are largely satisfied with the product.",
    "long_summary": "Reviewers praise the build quality and value, with a few noting slow support response times.",
    "key_themes": ["build quality", "value for money", "support response time"]
  }
}
```

`overall_sentiment` is one of `positive`, `negative`, `mixed`, `neutral`. `rating` is an integer from 1 to 5. `key_themes` is a list of 3 to 7 strings. `total_cost` is in USD, computed from a price-per-million-tokens table in the service (gpt-4o-mini: $0.150 input, $0.600 output as of 2026-05). When the OpenAI call fails, the pending run row is updated to `status='failed'` with the error message before the HTTP error is raised.

Error cases:

```bash
curl.exe -X POST http://127.0.0.1:5000/topics/99999/evaluate
```

Expected: `404 Not Found`, `Topic 99999 not found`.

```bash
curl.exe -X POST http://127.0.0.1:5000/topics/3/evaluate
```

Expected: `400 Bad Request`, `Topic 3 has no reviews to evaluate` (when the topic exists but has zero reviews).
