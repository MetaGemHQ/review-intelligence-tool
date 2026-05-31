import json
import time
from typing import Literal

from pydantic import BaseModel

from config import get_config
from db import get_connection
from repositories import evaluation_repo, review_repo, topic_repo
from services import prompts
from services.openai_client import get_client as get_openai_client
from services.gemini_client import get_client as get_gemini_client
from services.anthropic_client import get_client as get_anthropic_client
from services.topic_service import ValidationError

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TECHNIQUE = "zero-shot"
TEMPERATURE = 1.0
PROMPT_VERSION = "sentiment_v1"

# Which provider serves each model. Drives client dispatch in _call_model.
MODEL_PROVIDER = {
    "gpt-4o-mini": "openai",
    "gpt-4o": "openai",
    "gemini-2.5-flash": "gemini",
    "gemini-2.5-flash-lite": "gemini",
    "gemini-2.0-flash": "gemini",
    "gemini-2.5-pro": "gemini",
    "claude-haiku-4-5-20251001": "anthropic",
    "claude-sonnet-4-6": "anthropic",
}

# USD per 1M tokens. OpenAI mini figures are confirmed; the rest are list
# prices as of 2026-05 and should be re-checked against the vendor pages
# before the cost column is quoted anywhere external. Note: the Gemini models
# in the active lineup run on the free tier, so no charge is actually incurred;
# these figures are notional list prices only.
PRICE_PER_MTOK = {
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4o": {"input": 2.500, "output": 10.000},
    "gemini-2.5-flash": {"input": 0.300, "output": 2.500},
    "gemini-2.5-flash-lite": {"input": 0.100, "output": 0.400},
    "gemini-2.0-flash": {"input": 0.100, "output": 0.400},
    "gemini-2.5-pro": {"input": 1.250, "output": 10.000},
    "claude-haiku-4-5-20251001": {"input": 1.000, "output": 5.000},
    "claude-sonnet-4-6": {"input": 3.000, "output": 15.000},
}


class ReviewEvaluation(BaseModel):
    overall_sentiment: Literal["positive", "negative", "mixed", "neutral"]
    rating: int
    short_summary: str
    long_summary: str
    key_themes: list[str]


def _compute_cost(model, input_tokens, output_tokens):
    price = PRICE_PER_MTOK.get(model)
    if price is None:
        return None
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000


def _call_openai(model, prompt, temperature):
    client = get_openai_client()
    response = client.responses.parse(
        model=model,
        input=prompt,
        temperature=temperature,
        text_format=ReviewEvaluation,
    )
    evaluation = response.output_parsed
    usage = response.usage
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    return evaluation.model_dump(), input_tokens, output_tokens


def _call_gemini(model, prompt, temperature):
    from google.genai import types

    client = get_gemini_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=ReviewEvaluation,
        ),
    )
    parsed = response.parsed
    if isinstance(parsed, ReviewEvaluation):
        evaluation = parsed
    else:
        evaluation = ReviewEvaluation.model_validate(json.loads(response.text))
    usage = response.usage_metadata
    input_tokens = getattr(usage, "prompt_token_count", None)
    output_tokens = getattr(usage, "candidates_token_count", None)
    return evaluation.model_dump(), input_tokens, output_tokens


def _call_anthropic(model, prompt, temperature):
    client = get_anthropic_client()
    tool = {
        "name": "record_evaluation",
        "description": "Record the structured evaluation of the reviews.",
        "input_schema": ReviewEvaluation.model_json_schema(),
    }
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=temperature,
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_evaluation"},
        messages=[{"role": "user", "content": prompt}],
    )
    tool_block = next(b for b in response.content if b.type == "tool_use")
    evaluation = ReviewEvaluation.model_validate(tool_block.input)
    usage = response.usage
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    return evaluation.model_dump(), input_tokens, output_tokens


def _call_model(model, prompt, temperature):
    provider = MODEL_PROVIDER.get(model)
    if provider == "openai":
        return _call_openai(model, prompt, temperature)
    if provider == "gemini":
        return _call_gemini(model, prompt, temperature)
    if provider == "anthropic":
        return _call_anthropic(model, prompt, temperature)
    raise ValidationError(f"Unknown model: {model}")


def run_evaluation(
    topic_id,
    model=DEFAULT_MODEL,
    technique=DEFAULT_TECHNIQUE,
    temperature=TEMPERATURE,
):
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
        prompt = prompts.build_prompt(technique, topic_name, numbered)

        run_id = evaluation_repo.create_run(
            conn,
            topic_id=topic_id,
            review_ids_json=json.dumps(review_ids),
            model_used=model,
            prompt_version=PROMPT_VERSION,
            prompt_technique=technique,
            temperature=temperature,
        )
        conn.commit()

        start = time.monotonic()
        try:
            evaluation_dict, input_tokens, output_tokens = _call_model(
                model, prompt, temperature
            )
        except Exception as e:
            evaluation_repo.fail_run(conn, run_id, error_message=str(e))
            conn.commit()
            raise
        latency_ms = int((time.monotonic() - start) * 1000)

        total_cost = _compute_cost(model, input_tokens or 0, output_tokens or 0)

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
        "model": model,
        "temperature": temperature,
        "prompt_version": PROMPT_VERSION,
        "prompt_technique": technique,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "total_cost": total_cost,
        "evaluation": evaluation_dict,
    }


def evaluate_topic(topic_id):
    return run_evaluation(topic_id)
