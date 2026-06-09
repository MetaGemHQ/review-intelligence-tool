def save_message(conn, thread_id, role, content):
    cursor = conn.execute(
        "INSERT INTO chat_messages (thread_id, role, content) VALUES (?, ?, ?)",
        (thread_id, role, content),
    )
    return cursor.lastrowid


def get_messages_by_thread(conn, thread_id):
    return conn.execute(
        "SELECT id, thread_id, role, content, created_at "
        "FROM chat_messages WHERE thread_id = ? ORDER BY id",
        (thread_id,),
    ).fetchall()


def get_thread(conn, thread_id):
    return conn.execute(
        "SELECT thread_id, verified_topic_id, verified_topic_name, verified_at "
        "FROM chat_threads WHERE thread_id = ?",
        (thread_id,),
    ).fetchone()


def set_verified_topic(conn, thread_id, topic_id, topic_name):
    conn.execute(
        "INSERT INTO chat_threads "
        "(thread_id, verified_topic_id, verified_topic_name, verified_at) "
        "VALUES (?, ?, ?, datetime('now')) "
        "ON CONFLICT(thread_id) DO UPDATE SET "
        "verified_topic_id = excluded.verified_topic_id, "
        "verified_topic_name = excluded.verified_topic_name, "
        "verified_at = excluded.verified_at",
        (thread_id, topic_id, topic_name),
    )
