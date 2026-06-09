from db import get_connection
from repositories import topic_repo
from services.prompts import DEFAULT_RELEVANCE_LEVEL, RELEVANCE_LEVELS

ALLOWED_CATEGORIES = {"company", "product", "service"}
ALLOWED_STRICTNESS = set(RELEVANCE_LEVELS)


class ValidationError(Exception):
    pass


def _row_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "created_by": row["created_by"],
        "relevance_strictness": row["relevance_strictness"],
        "created_at": row["created_at"],
    }


def create_topic(name, category, created_by, relevance_strictness=None):
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name is required and must be a non-empty string")
    name = name.strip()

    if category is not None and category not in ALLOWED_CATEGORIES:
        raise ValidationError(
            f"category must be one of {sorted(ALLOWED_CATEGORIES)} or null"
        )

    if relevance_strictness is None:
        relevance_strictness = DEFAULT_RELEVANCE_LEVEL
    elif relevance_strictness not in ALLOWED_STRICTNESS:
        raise ValidationError(
            f"relevance_strictness must be one of {sorted(ALLOWED_STRICTNESS)}"
        )

    conn = get_connection()
    try:
        new_id = topic_repo.create_topic(
            conn, name, category, created_by, relevance_strictness
        )
        conn.commit()
        row = topic_repo.get_topic_by_id(conn, new_id)
    finally:
        conn.close()
    return _row_to_dict(row)


def list_topics():
    conn = get_connection()
    try:
        rows = topic_repo.get_all_topics(conn)
    finally:
        conn.close()
    return [_row_to_dict(r) for r in rows]
