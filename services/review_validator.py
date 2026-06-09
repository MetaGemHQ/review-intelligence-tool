"""AI gate that checks a review candidate before it is persisted.

A submitted "review" may not be a review at all: scraped pages can return
fabricated or irrelevant text, and a malicious batch can smuggle instructions
in (prompt injection). This asks the LLM whether the candidate is a genuine
review and whether it fits the topic, and returns a structured verdict the
service layer acts on.
"""

from pydantic import BaseModel

from services import prompts
from services.openai_client import get_client

VALIDATOR_MODEL = "gpt-4o-mini"
VALIDATOR_TEMPERATURE = 0.0


class ReviewVerdict(BaseModel):
    is_review: bool
    is_relevant: bool
    reason: str


def validate_review(review_text, topic_name, strictness=prompts.DEFAULT_RELEVANCE_LEVEL):
    client = get_client()
    prompt = prompts.build_validation_prompt(topic_name, review_text, strictness)
    response = client.responses.parse(
        model=VALIDATOR_MODEL,
        input=prompt,
        temperature=VALIDATOR_TEMPERATURE,
        text_format=ReviewVerdict,
    )
    return response.output_parsed
