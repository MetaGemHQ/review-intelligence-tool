def create_review(conn, topic_id, review_text, source):
    cursor = conn.execute(
        "INSERT INTO reviews (topic_id, review_text, source) VALUES (?, ?, ?)",
        (topic_id, review_text, source),
    )
    return cursor.lastrowid


def get_reviews_by_topic(conn, topic_id):
    return conn.execute(
        "SELECT id, topic_id, review_text, source, submitted_at "
        "FROM reviews WHERE topic_id = ? ORDER BY submitted_at DESC",
        (topic_id,),
    ).fetchall()
