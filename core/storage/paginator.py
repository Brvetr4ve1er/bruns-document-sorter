"""
core/storage/paginator.py

Paginated query helper to prevent full-table scans.

Problem: `SELECT * FROM containers` on 50,000 rows bloats memory
and makes the UI unresponsive. 

Solution: All table reads go through this helper which enforces
LIMIT / OFFSET pagination and returns metadata for the UI widget.
"""

import sqlite3
from typing import Any


def paginated_query(
    conn: sqlite3.Connection,
    table: str,
    page: int = 1,
    page_size: int = 50,
    where: str = "",
    order_by: str = "id DESC",
    params: tuple = ()
) -> dict[str, Any]:
    """
    Returns:
      {
        "rows":       list[sqlite3.Row],
        "page":       int,
        "page_size":  int,
        "total":      int,       # total matching rows
        "total_pages": int,
        "has_next":   bool,
        "has_prev":   bool,
      }
    """
    where_clause = f"WHERE {where}" if where else ""

    # Count total matching rows (cheap — no data transfer)
    count_sql = f"SELECT COUNT(*) FROM {table} {where_clause}"
    total = conn.execute(count_sql, params).fetchone()[0]

    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))  # clamp to valid range

    offset = (page - 1) * page_size
    data_sql = (
        f"SELECT * FROM {table} {where_clause} "
        f"ORDER BY {order_by} LIMIT ? OFFSET ?"
    )
    rows = conn.execute(data_sql, params + (page_size, offset)).fetchall()

    return {
        "rows":        rows,
        "page":        page,
        "page_size":   page_size,
        "total":       total,
        "total_pages": total_pages,
        "has_next":    page < total_pages,
        "has_prev":    page > 1,
    }
