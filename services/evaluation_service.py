from typing import Literal

from pydantic import BaseModel

from config import get_config
from db import get_connection
from repositories import review_repo, topic_repo
from services.openai_client import get_client
from services.topic_service import ValidationError

MODEL = "gpt-4o-mini"


class ReviewEvaluation(BaseModel):
    overall_sentiment: Literal["positive", "negative", "mixed", "neutral"]
    rating: int
    short_summary: str
    long_summary: str
    key_themes: list[str]


def evaluate_topic(topic_id):
    conn = get_connection()
    try:
        topic = topic_repo.get_topic_by_id(conn, topic_id)
        if topic is None:
            raise ValidationError(f"Topic {topic_id} not found")

        reviews = review_repo.get_reviews_by_topic(conn, topic_id)
        if not reviews:
            raise ValidationError(
                f"Topic {topic_id} has no reviews to evaluate"
            )

        max_reviews = get_config()["max_reviews_per_batch"]
        capped_reviews = reviews[:max_reviews]

        topic_name = topic["name"]
        numbered = "\n".join(
            f"{i}. {r['review_text']}" for i, r in enumerate(capped_reviews, start=1)
        )
        prompt = (
            f'You are analyzing customer reviews about "{topic_name}". '
            "Produce a structured evaluation with the following:\n"
            "- overall_sentiment: one of positive, negative, mixed, or neutral\n"
            "- rating: an integer from 1 to 5 representing the average customer sentiment\n"
            "- short_summary: a single sentence executive summary\n"
            "- long_summary: a paragraph with more detail\n"
            "- key_themes: a list of 3 to 7 recurring themes across the reviews\n\n"
            "Reviews:\n"
            f"{numbered}"
        )

        client = get_client()
        response = client.responses.parse(
            model=MODEL,
            input=prompt,
            text_format=ReviewEvaluation,
        )
        evaluation = response.output_parsed
    finally:
        conn.close()

    return {
        "topic_id": topic_id,
        "topic_name": topic_name,
        "review_count": len(capped_reviews),
        "model": MODEL,
        "evaluation": evaluation.model_dump(),
    }
