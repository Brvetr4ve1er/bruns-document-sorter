"""IMPROVEMENT 2: Batch Queue & Background Processing + IMPROVEMENT 11: Bulk Operations"""
from database_logic.database import (
    get_connection, record_processing_queue, update_queue_status,
    get_queue_status, log_change
)
from datetime import datetime
from enum import Enum
import json
import uuid


class OperationType(Enum):
    """Types of batch operations."""
    PROCESS_FILES = "process_files"
    UPDATE_CONTAINERS = "update_containers"
    DELETE_CONTAINERS = "delete_containers"
    ARCHIVE_CONTAINERS = "archive_containers"
    EXPORT_DATA = "export_data"
    VALIDATE_CONTAINERS = "validate_containers"


class QueueStatus(Enum):
    """Processing queue status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchProcessor:
    def __init__(self):
        self.batch_id = str(uuid.uuid4())

    def create_batch_operation(self, operation_type: OperationType, items: list, metadata: dict = None) -> str:
        """Create a new batch operation. Returns batch_id."""
        conn = get_connection()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO batch_operations (batch_id, operation_type, status, metadata)
                       VALUES (?, ?, ?, ?)""",
                    (
                        self.batch_id,
                        operation_type.value,
                        QueueStatus.PENDING.value,
                        json.dumps({"items": items, **(metadata or {})})
                    )
                )
            conn.close()
            return self.batch_id
        except Exception as e:
            print(f"Batch creation error: {e}")
            conn.close()
            return None

    def add_to_queue(self, file_path: str, priority: int = 5, retry_count: int = 0) -> bool:
        """Add file to processing queue. Priority: 1-10 (higher = more urgent)."""
        return record_processing_queue(file_path, priority, retry_count)

    def get_queue_progress(self) -> dict:
        """Get overall queue progress statistics."""
        conn = get_connection()
        total = conn.execute("SELECT COUNT(*) FROM processing_queue").fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM processing_queue WHERE status = ?",
            (QueueStatus.PENDING.value,)
        ).fetchone()[0]
        processing = conn.execute(
            "SELECT COUNT(*) FROM processing_queue WHERE status = ?",
            (QueueStatus.PROCESSING.value,)
        ).fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM processing_queue WHERE status = ?",
            (QueueStatus.COMPLETED.value,)
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM processing_queue WHERE status = ?",
            (QueueStatus.FAILED.value,)
        ).fetchone()[0]
        conn.close()

        return {
            "total": total,
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "completion_rate": (completed / total * 100) if total > 0 else 0,
        }

    def bulk_update_containers(self, container_ids: list, updates: dict, changed_by: str = "system") -> int:
        """Bulk update multiple containers. Returns count updated."""
        conn = get_connection()
        count = 0

        try:
            with conn:
                for container_id in container_ids:
                    # Get old values for audit
                    old_record = conn.execute(
                        "SELECT * FROM containers WHERE id = ?",
                        (container_id,)
                    ).fetchone()

                    if not old_record:
                        continue

                    # Update container
                    cols = ", ".join(f"{k} = ?" for k in updates.keys())
                    values = list(updates.values()) + [container_id]
                    conn.execute(f"UPDATE containers SET {cols} WHERE id = ?", values)

                    # Log changes
                    for field_name, new_value in updates.items():
                        old_value = old_record[field_name] if field_name in dict(old_record).keys() else None
                        if old_value != new_value:
                            log_change(container_id, field_name, old_value, new_value, changed_by)

                    count += 1

            conn.close()
            return count
        except Exception as e:
            print(f"Bulk update error: {e}")
            conn.close()
            return count

    def bulk_delete_containers(self, container_ids: list) -> int:
        """Bulk delete containers. Returns count deleted."""
        conn = get_connection()
        count = 0

        try:
            with conn:
                for container_id in container_ids:
                    conn.execute("DELETE FROM containers WHERE id = ?", (container_id,))
                    count += 1
            conn.close()
            return count
        except Exception as e:
            print(f"Bulk delete error: {e}")
            conn.close()
            return count

    def bulk_archive_containers(self, container_ids: list, archive_status: str = "ARCHIVED") -> int:
        """Bulk archive containers by updating status. Returns count archived."""
        return self.bulk_update_containers(
            container_ids,
            {"statut_container": archive_status},
            changed_by="system_archive"
        )

    def get_batch_status(self, batch_id: str) -> dict:
        """Get status of a batch operation."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM batch_operations WHERE batch_id = ?",
            (batch_id,)
        ).fetchone()
        conn.close()

        if not row:
            return None

        return {
            "batch_id": row["batch_id"],
            "operation_type": row["operation_type"],
            "status": row["status"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        }

    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch operation."""
        conn = get_connection()
        try:
            with conn:
                conn.execute(
                    "UPDATE batch_operations SET status = ? WHERE batch_id = ?",
                    (QueueStatus.CANCELLED.value, batch_id)
                )
            conn.close()
            return True
        except Exception as e:
            print(f"Cancel batch error: {e}")
            conn.close()
            return False


def process_next_in_queue(batch_processor: BatchProcessor = None) -> tuple[str, bool]:
    """Process next item in queue. Returns (file_path, success)."""
    conn = get_connection()

    # Get highest priority pending item
    row = conn.execute(
        """SELECT file_path FROM processing_queue
           WHERE status = ?
           ORDER BY priority DESC, created_at ASC
           LIMIT 1""",
        (QueueStatus.PENDING.value,)
    ).fetchone()

    if not row:
        conn.close()
        return None, False

    file_path = row["file_path"]

    # Mark as processing
    update_queue_status(file_path, QueueStatus.PROCESSING.value)
    conn.close()

    return file_path, True
