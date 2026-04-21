"""IMPROVEMENT 17: Cache Extraction Results"""
import sqlite3
import json
from database_logic.database import get_connection


def cache_extraction(file_hash: str, extraction_result: dict) -> bool:
    """Cache extraction result by file hash."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO extraction_cache (file_hash, extraction_results)
                   VALUES (?, ?)""",
                (file_hash, json.dumps(extraction_result))
            )
        conn.close()
        return True
    except Exception as e:
        print(f"Cache error: {e}")
        conn.close()
        return False


def get_cached_extraction(file_hash: str) -> dict | None:
    """Retrieve cached extraction if exists."""
    conn = get_connection()
    row = conn.execute(
        """SELECT extraction_results FROM extraction_cache WHERE file_hash = ?""",
        (file_hash,)
    ).fetchone()

    if row:
        # Increment hit count
        with conn:
            conn.execute(
                "UPDATE extraction_cache SET hit_count = hit_count + 1 WHERE file_hash = ?",
                (file_hash,)
            )
        conn.close()
        return json.loads(row[0])

    conn.close()
    return None


def clear_cache(older_than_days: int = 30):
    """Clear cache entries older than N days."""
    conn = get_connection()
    with conn:
        conn.execute(
            """DELETE FROM extraction_cache
               WHERE cached_at < datetime('now', ? || ' days')""",
            (f"-{older_than_days}",)
        )
    conn.close()


def get_cache_stats() -> dict:
    """Get cache hit/miss statistics."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM extraction_cache").fetchone()[0]
    hit_sum = conn.execute("SELECT SUM(hit_count) FROM extraction_cache").fetchone()[0]
    conn.close()
    return {
        "cached_files": total,
        "total_hits": hit_sum or 0,
        "avg_hits_per_file": (hit_sum or 0) / total if total > 0 else 0,
    }
