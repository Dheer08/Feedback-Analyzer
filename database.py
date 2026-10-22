"""SQLite storage for analysed reviews.

Kept separate from the dashboard so the UI code stays short and the storage
layer can be tested on its own.
"""

import os
import sqlite3
from contextlib import closing

DB_FILE = os.getenv("FEEDBACK_DB", "feedback.db")


def _connect(db_file: str | None = None) -> sqlite3.Connection:
    return sqlite3.connect(db_file or DB_FILE)


def init_db(db_file: str | None = None) -> None:
    """Create the feedback table if it does not exist yet."""
    with closing(_connect(db_file)) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY,
                review TEXT,
                label TEXT,
                score INTEGER,
                theme TEXT
            )
        """)


def save_results(results: list[dict], db_file: str | None = None) -> int:
    """Store successfully analysed reviews and return how many were saved.

    Rows that failed analysis (label == "error") are skipped so they never
    distort the saved history.
    """
    rows = [
        (r["review"], r["label"], r["score"], r["theme"])
        for r in results
        if r["label"] != "error"
    ]
    with closing(_connect(db_file)) as conn, conn:
        conn.executemany(
            "INSERT INTO feedback (review, label, score, theme) VALUES (?, ?, ?, ?)", rows
        )
    return len(rows)


def load_history(db_file: str | None = None) -> list[dict]:
    """Return every saved review, oldest first."""
    with closing(_connect(db_file)) as conn:
        rows = conn.execute(
            "SELECT review, label, score, theme FROM feedback ORDER BY id"
        ).fetchall()
    return [{"review": r[0], "label": r[1], "score": r[2], "theme": r[3]} for r in rows]
