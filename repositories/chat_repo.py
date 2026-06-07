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
