import sqlite3
from pathlib import Path

DB_PATH = Path("data/dev.db")
SCHEMA_PATH = Path("schema.sql")


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _migrate(conn):
    """Apply additive schema changes to databases created before them.

    `CREATE TABLE IF NOT EXISTS` never alters an existing table, so columns
    added after a database's first init need an explicit ALTER here.
    """
    topic_cols = {row[1] for row in conn.execute("PRAGMA table_info(topics)")}
    if "relevance_strictness" not in topic_cols:
        conn.execute(
            "ALTER TABLE topics ADD COLUMN "
            "relevance_strictness TEXT NOT NULL DEFAULT 'standard'"
        )


def init_db():
    schema = SCHEMA_PATH.read_text()
    conn = get_connection()
    try:
        conn.executescript(schema)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()
