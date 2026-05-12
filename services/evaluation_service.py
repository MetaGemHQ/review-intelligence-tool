from config import get_config
from db import get_connection
from repositories import review_repo, topic_repo
from services.openai_client import get_client
from services.topic_service import ValidationError

MODEL = "gpt-4o-mini"


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
            f'Here are customer reviews about "{topic_name}". '
            "Summarize the main themes in a few sentences.\n\n"
            "Reviews:\n"
            f"{numbered}"
        )

        client = get_client()
        response = client.responses.create(
            model=MODEL,
            input=prompt,
        )
        summary = response.output_text
    finally:
        conn.close()

    return {
        "topic_id": topic_id,
        "topic_name": topic_name,
        "review_count": len(capped_reviews),
        "model": MODEL,
        "summary": summary,
    }
