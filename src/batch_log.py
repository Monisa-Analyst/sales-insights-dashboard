"""
batch_log.py
Tracks every data submission that comes through the upload page.
Stores batch metadata, health scores, and validation issues so we
can show a history log and flag batches that need analyst review.
"""

import os
import json
import sqlite3
from datetime import datetime


def _get_db_path():
    """figure out where the database lives — /tmp on cloud, local otherwise"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.exists("/mount/src/sales-insights-dashboard"):
        return "/tmp/sales.db"
    return os.path.join(root, "data", "sales.db")


def _ensure_log_table():
    """create the ingestion_log table if it doesn't exist yet"""
    conn = sqlite3.connect(_get_db_path())
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_log (
            batch_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            submitted_at   TEXT NOT NULL,
            filename       TEXT,
            row_count      INTEGER,
            status         TEXT DEFAULT 'Pending',
            health_score   REAL,
            issues_json    TEXT,
            accepted_rows  INTEGER DEFAULT 0,
            rejected_rows  INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def log_batch(filename, row_count, status, health_score, issues, accepted_rows, rejected_rows):
    """
    Record a completed ingestion attempt in the log.
    Returns the new batch_id.
    """
    _ensure_log_table()
    conn = sqlite3.connect(_get_db_path())
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ingestion_log
            (submitted_at, filename, row_count, status, health_score,
             issues_json, accepted_rows, rejected_rows)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        filename,
        row_count,
        status,
        round(health_score, 1),
        json.dumps(issues),
        accepted_rows,
        rejected_rows,
    ))
    batch_id = cur.lastrowid
    conn.commit()
    conn.close()
    return batch_id


def get_batch_history(limit=50):
    """pull the most recent batch submissions for the history table"""
    _ensure_log_table()
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM ingestion_log ORDER BY batch_id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_alerts():
    """return batches that are flagged as needing analyst review"""
    _ensure_log_table()
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM ingestion_log WHERE status = 'Needs Review' ORDER BY batch_id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
