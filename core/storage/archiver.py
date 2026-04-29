"""
core/storage/archiver.py

Archival job to prevent unbounded database growth.

Problem: Over time, documents, jobs, and audit logs accumulate in the
SQLite file. A 5GB SQLite file is slow to query and expensive to back up.

Solution: Any records older than `retention_days` are:
  1. Exported to a compressed .CSV.GZ file in an `archive/` directory
  2. Deleted from the live database
  3. A vacuum is run to reclaim freed disk space

This keeps the live DB lean and fast while preserving all historical data.
"""

import os
import gzip
import csv
import sqlite3
import shutil
from datetime import datetime, timezone, timedelta
from core.storage.db import get_connection


ARCHIVABLE_TABLES = [
    # (table_name, timestamp_column, id_column)
    ("jobs",        "created_at",    "id"),
    ("audit_log",   "timestamp",     "id"),
    ("documents",   "created_at",    "id"),
]


def run_archival(db_path: str, retention_days: int = 365) -> dict:
    """
    Archive rows older than `retention_days` from archivable tables.
    Returns a summary dict of how many rows were archived per table.
    """
    archive_dir = os.path.join(os.path.dirname(db_path), "archive")
    os.makedirs(archive_dir, exist_ok=True)

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    ts_label   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    summary = {}
    conn = get_connection(db_path)

    try:
        for table, ts_col, id_col in ARCHIVABLE_TABLES:
            # Fetch rows to archive
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {ts_col} < ?", (cutoff_str,)
            ).fetchall()

            if not rows:
                summary[table] = 0
                continue

            # Write to .csv.gz
            archive_file = os.path.join(
                archive_dir, f"{table}_{ts_label}.csv.gz"
            )
            col_names = [desc[0] for desc in conn.execute(
                f"SELECT * FROM {table} LIMIT 0"
            ).description]

            with gzip.open(archive_file, "wt", newline="", encoding="utf-8") as gz:
                writer = csv.writer(gz)
                writer.writerow(col_names)
                writer.writerows([tuple(r) for r in rows])

            # Delete archived rows from live DB
            ids = tuple(r[id_col] for r in rows)
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"DELETE FROM {table} WHERE {id_col} IN ({placeholders})", ids
            )
            conn.commit()
            summary[table] = len(rows)

        # Reclaim freed disk space
        conn.execute("VACUUM")
        conn.commit()

    finally:
        conn.close()

    return summary
