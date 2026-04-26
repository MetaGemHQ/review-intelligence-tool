def create_topic(conn, name, category, created_by):
    cursor = conn.execute(
        "INSERT INTO topics (name, category, created_by) VALUES (?, ?, ?)",
        (name, category, created_by),
    )
    return cursor.lastrowid


def get_all_topics(conn):
    return conn.execute(
        "SELECT id, name, category, created_by, created_at "
        "FROM topics ORDER BY created_at DESC"
    ).fetchall()


def get_topic_by_id(conn, topic_id):
    return conn.execute(
        "SELECT id, name, category, created_by, created_at "
        "FROM topics WHERE id = ?",
        (topic_id,),
    ).fetchone()
