"""Per-review breakdown for the dashboard charts.

The aggregate evaluation returns one verdict for the whole topic. The dashboard
also wants a sentiment donut, a rating distribution, and ranked theme bars,
which need per-review data. This asks the model to score each review and tally
the themes in a single structured call, then shapes it into the counts the UI
charts consume. Read-only: it does not persist anything.
"""

from collections import Counter
from typing import Literal

from pydantic import BaseModel

from config import get_config
from db import get_connection
from repositories import review_repo, topic_repo
from services import prompts
from services.openai_client import get_client
from services.topic_service import ValidationError

BREAKDOWN_MODEL = "gpt-4o-mini"
TEMPERATURE = 0.0
SENTIMENTS = ["positive", "negative", "mixed", "neutral"]


class ReviewScore(BaseModel):
    rating: int
    sentiment: Literal["positive", "negative", "mixed", "neutral"]


class ThemeCount(BaseModel):
    theme: str
    polarity: Literal["positive", "negative"]
    count: int


class TopicBreakdown(BaseModel):
    per_review: list[ReviewScore]
    themes: list[ThemeCount]


def run_breakdown(topic_id):
    conn = get_connection()
    try:
        topic = topic_repo.get_topic_by_id(conn, topic_id)
        if topic is None:
            raise ValidationError(f"Topic {topic_id} not found")
        reviews = review_repo.get_reviews_by_topic(conn, topic_id)
        if not reviews:
            raise ValidationError(f"Topic {topic_id} has no reviews to evaluate")
        capped = reviews[: get_config()["max_reviews_per_batch"]]
        topic_name = topic["name"]
    finally:
        conn.close()

    numbered = "\n".join(f"{i}. {r['review_text']}" for i, r in enumerate(capped, start=1))
    prompt = prompts.build_breakdown_prompt(topic_name, numbered)

    client = get_client()
    response = client.responses.parse(
        model=BREAKDOWN_MODEL,
        input=prompt,
        temperature=TEMPERATURE,
        text_format=TopicBreakdown,
    )
    result = response.output_parsed

    # The model occasionally returns more/fewer scores than reviews sent; align
    # to the actual count so the charts stay consistent with "reviews stored".
    scores = result.per_review[: len(capped)]
    sentiment_counts = {s: 0 for s in SENTIMENTS}
    rating_counts = {str(n): 0 for n in range(1, 6)}
    for r in scores:
        if r.sentiment in sentiment_counts:
            sentiment_counts[r.sentiment] += 1
        rating = max(1, min(5, int(r.rating)))
        rating_counts[str(rating)] += 1

    pain_points = sorted(
        [{"theme": t.theme, "count": t.count} for t in result.themes if t.polarity == "negative"],
        key=lambda x: x["count"],
        reverse=True,
    )
    positive_drivers = sorted(
        [{"theme": t.theme, "count": t.count} for t in result.themes if t.polarity == "positive"],
        key=lambda x: x["count"],
        reverse=True,
    )

    return {
        "topic_id": topic_id,
        "topic_name": topic_name,
        "review_count": len(scores),
        "sentiment_counts": sentiment_counts,
        "rating_counts": rating_counts,
        "pain_points": pain_points,
        "positive_drivers": positive_drivers,
    }
