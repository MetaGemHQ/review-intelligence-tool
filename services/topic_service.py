from db import get_connection
from repositories import topic_repo

ALLOWED_CATEGORIES = {"company", "product", "service"}


class ValidationError(Exception):
    pass


def _row_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


def create_topic(name, category, created_by):
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name is required and must be a non-empty string")
    name = name.strip()

    if category is not None and category not in ALLOWED_CATEGORIES:
        raise ValidationError(
            f"category must be one of {sorted(ALLOWED_CATEGORIES)} or null"
        )

    conn = get_connection()
    try:
        new_id = topic_repo.create_topic(conn, name, category, created_by)
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
