import json
import time
from typing import Literal

from pydantic import BaseModel

from config import get_config
from db import get_connection
from repositories import evaluation_repo, review_repo, topic_repo
from services.openai_client import get_client
from services.topic_service import ValidationError

MODEL = "gpt-4o-mini"
TEMPERATURE = 1.0
PROMPT_VERSION = "sentiment_v1"
PROMPT_TECHNIQUE = "zero-shot"

# USD per 1M tokens. Update when adding models or when pricing changes.
PRICE_PER_MTOK = {
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
}


class ReviewEvaluation(BaseModel):
    overall_sentiment: Literal["positive", "negative", "mixed", "neutral"]
    rating: int
    short_summary: str
    long_summary: str
    key_themes: list[str]


def _build_prompt(topic_name, numbered_reviews):
    return (
        f'You are analyzing customer reviews about "{topic_name}". '
        "Produce a structured evaluation with the following:\n"
        "- overall_sentiment: one of positive, negative, mixed, or neutral\n"
        "- rating: an integer from 1 to 5 representing the average customer sentiment\n"
        "- short_summary: a single sentence executive summary\n"
        "- long_summary: a paragraph with more detail\n"
        "- key_themes: a list of 3 to 7 recurring themes across the reviews\n\n"
        "Reviews:\n"
        f"{numbered_reviews}"
    )


def _compute_cost(model, input_tokens, output_tokens):
    price = PRICE_PER_MTOK.get(model)
    if price is None:
        return None
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000


def evaluate_topic(topic_id):
    conn = get_connection()
    try:
        topic = topic_repo.get_topic_by_id(conn, topic_id)
        if topic is None:
            raise ValidationError(f"Topic {topic_id} not found")

        reviews = review_repo.get_reviews_by_topic(conn, topic_id)
        if not reviews:
            raise ValidationError(f"Topic {topic_id} has no reviews to evaluate")

        max_reviews = get_config()["max_reviews_per_batch"]
        capped_reviews = reviews[:max_reviews]

        topic_name = topic["name"]
        review_ids = [r["id"] for r in capped_reviews]
        numbered = "\n".join(
            f"{i}. {r['review_text']}"
            for i, r in enumerate(capped_reviews, start=1)
        )
        prompt = _build_prompt(topic_name, numbered)

        run_id = evaluation_repo.create_run(
            conn,
            topic_id=topic_id,
            review_ids_json=json.dumps(review_ids),
            model_used=MODEL,
            prompt_version=PROMPT_VERSION,
            prompt_technique=PROMPT_TECHNIQUE,
            temperature=TEMPERATURE,
        )
        conn.commit()

        client = get_client()
        start = time.monotonic()
        try:
            response = client.responses.parse(
                model=MODEL,
                input=prompt,
                temperature=TEMPERATURE,
                text_format=ReviewEvaluation,
            )
        except Exception as e:
            evaluation_repo.fail_run(conn, run_id, error_message=str(e))
            conn.commit()
            raise
        latency_ms = int((time.monotonic() - start) * 1000)

        evaluation = response.output_parsed
        evaluation_dict = evaluation.model_dump()
        usage = response.usage
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        total_cost = _compute_cost(MODEL, input_tokens or 0, output_tokens or 0)

        evaluation_repo.complete_run(
            conn,
            run_id=run_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            total_cost=total_cost,
            result_json=json.dumps(evaluation_dict),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "run_id": run_id,
        "topic_id": topic_id,
        "topic_name": topic_name,
        "review_count": len(capped_reviews),
        "model": MODEL,
        "temperature": TEMPERATURE,
        "prompt_version": PROMPT_VERSION,
        "prompt_technique": PROMPT_TECHNIQUE,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "total_cost": total_cost,
        "evaluation": evaluation_dict,
    }
