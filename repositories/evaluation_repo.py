def create_run(
    conn,
    topic_id,
    review_ids_json,
    model_used,
    prompt_version,
    prompt_technique,
    temperature,
):
    cursor = conn.execute(
        "INSERT INTO evaluation_runs "
        "(topic_id, review_ids, model_used, prompt_version, prompt_technique, temperature) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            topic_id,
            review_ids_json,
            model_used,
            prompt_version,
            prompt_technique,
            temperature,
        ),
    )
    return cursor.lastrowid


def complete_run(
    conn,
    run_id,
    input_tokens,
    output_tokens,
    latency_ms,
    total_cost,
    result_json,
):
    conn.execute(
        "UPDATE evaluation_runs SET "
        "status = 'complete', "
        "completed_at = datetime('now'), "
        "input_tokens = ?, "
        "output_tokens = ?, "
        "latency_ms = ?, "
        "total_cost = ?, "
        "result_json = ? "
        "WHERE id = ?",
        (input_tokens, output_tokens, latency_ms, total_cost, result_json, run_id),
    )


def fail_run(conn, run_id, error_message):
    conn.execute(
        "UPDATE evaluation_runs SET "
        "status = 'failed', "
        "completed_at = datetime('now'), "
        "error_message = ? "
        "WHERE id = ?",
        (error_message, run_id),
    )


def get_run_by_id(conn, run_id):
    return conn.execute(
        "SELECT id, topic_id, review_ids, model_used, prompt_version, prompt_technique, "
        "temperature, status, started_at, completed_at, input_tokens, output_tokens, "
        "latency_ms, total_cost, result_json, error_message "
        "FROM evaluation_runs WHERE id = ?",
        (run_id,),
    ).fetchone()


def list_runs_by_topic(conn, topic_id):
    return conn.execute(
        "SELECT id, topic_id, review_ids, model_used, prompt_version, prompt_technique, "
        "temperature, status, started_at, completed_at, input_tokens, output_tokens, "
        "latency_ms, total_cost, result_json, error_message "
        "FROM evaluation_runs WHERE topic_id = ? ORDER BY started_at DESC",
        (topic_id,),
    ).fetchall()
