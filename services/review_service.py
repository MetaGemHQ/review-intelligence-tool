from config import get_config
from db import get_connection
from repositories import review_repo, topic_repo
from services.topic_service import ValidationError


def _row_to_dict(row):
    return {
        "id": row["id"],
        "topic_id": row["topic_id"],
        "review_text": row["review_text"],
        "source": row["source"],
        "submitted_at": row["submitted_at"],
    }


def add_review(topic_id, review_text, source=None):
    if not isinstance(topic_id, int) or isinstance(topic_id, bool) or topic_id <= 0:
        raise ValidationError("topic_id is required and must be a positive integer")

    if not isinstance(review_text, str) or not review_text.strip():
        raise ValidationError("review_text is required and must be a non-empty string")
    review_text = review_text.strip()

    config = get_config()
    max_chars = config["max_review_chars"]
    if len(review_text) > max_chars:
        raise ValidationError(
            f"review_text exceeds {max_chars} character limit"
        )

    max_reviews = config["max_reviews_per_batch"]

    conn = get_connection()
    try:
        if topic_repo.get_topic_by_id(conn, topic_id) is None:
            raise ValidationError(f"Topic {topic_id} not found")

        existing = review_repo.get_reviews_by_topic(conn, topic_id)
        if len(existing) >= max_reviews:
            raise ValidationError(
                f"Topic {topic_id} is at capacity ({max_reviews} reviews max)"
            )

        new_id = review_repo.create_review(conn, topic_id, review_text, source)
        conn.commit()
        rows = review_repo.get_reviews_by_topic(conn, topic_id)
        row = next(r for r in rows if r["id"] == new_id)
    finally:
        conn.close()
    return _row_to_dict(row)


def list_reviews(topic_id):
    if not isinstance(topic_id, int) or isinstance(topic_id, bool) or topic_id <= 0:
        raise ValidationError("topic_id is required and must be a positive integer")

    conn = get_connection()
    try:
        if topic_repo.get_topic_by_id(conn, topic_id) is None:
            raise ValidationError(f"Topic {topic_id} not found")
        rows = review_repo.get_reviews_by_topic(conn, topic_id)
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]
