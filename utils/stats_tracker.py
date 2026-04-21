"""IMPROVEMENT 14: Processing Stats Dashboard + IMPROVEMENT 8: Performance Metrics"""
from database_logic.database import get_connection, increment_processing_stat, get_processing_stats
from datetime import datetime, timedelta
import json


class StatsTracker:
    """Track and analyze processing statistics and performance metrics."""

    def __init__(self):
        self.start_time = datetime.now()

    def record_extraction(self, doc_type: str, success: bool, extraction_time_ms: int):
        """Record extraction performance metric."""
        increment_processing_stat(doc_type, success, extraction_time_ms)

    def get_pipeline_stats(self) -> dict:
        """Get comprehensive pipeline statistics."""
        conn = get_connection()

        # Get processing stats
        stats = get_processing_stats()

        # Calculate additional metrics
        total_containers = conn.execute("SELECT COUNT(*) FROM containers").fetchone()[0]
        total_shipments = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]

        # Get average confidence
        avg_confidence = conn.execute(
            "SELECT AVG(confidence) FROM confidence_scores"
        ).fetchone()[0] or 0.0

        # Get validation issues count
        open_issues = conn.execute(
            "SELECT COUNT(*) FROM validation_issues WHERE is_resolved = 0"
        ).fetchone()[0]

        # Get cache hit rate
        cache_stats = conn.execute("""
            SELECT
                COUNT(*) as cached_files,
                COALESCE(SUM(hit_count), 0) as total_hits
            FROM extraction_cache
        """).fetchone()

        conn.close()

        return {
            "pipeline_status": stats,
            "data_quality": {
                "average_confidence": round(avg_confidence, 3),
                "validation_issues_open": open_issues,
            },
            "cache_performance": {
                "cached_files": cache_stats["cached_files"],
                "total_cache_hits": cache_stats["total_hits"],
                "cache_hit_rate": (cache_stats["total_hits"] / total_containers * 100) if total_containers > 0 else 0,
            },
            "data_volume": {
                "total_containers": total_containers,
                "total_shipments": total_shipments,
            },
        }

    def get_extraction_performance(self) -> dict:
        """Get extraction performance metrics by document type."""
        stats = get_processing_stats()
        return {
            "documents_processed": stats.get("total_documents", 0),
            "success_rate": stats.get("success_rate", 0),
            "avg_extraction_time": stats.get("avg_extraction_time_ms", 0),
            "by_document_type": stats.get("by_document_type", {}),
        }

    def get_data_quality_report(self) -> dict:
        """Generate data quality report."""
        conn = get_connection()

        # Field-level confidence analysis
        field_stats = conn.execute("""
            SELECT
                field_name,
                COUNT(*) as total_scores,
                AVG(confidence) as avg_confidence,
                MIN(confidence) as min_confidence,
                MAX(confidence) as max_confidence
            FROM confidence_scores
            GROUP BY field_name
            ORDER BY avg_confidence DESC
        """).fetchall()

        # Validation issues by type
        issue_stats = conn.execute("""
            SELECT
                issue_type,
                severity,
                COUNT(*) as count
            FROM validation_issues
            WHERE is_resolved = 0
            GROUP BY issue_type, severity
            ORDER BY count DESC
        """).fetchall()

        # High-confidence vs low-confidence containers
        high_confidence = conn.execute(
            """SELECT COUNT(DISTINCT container_id) FROM confidence_scores
               WHERE confidence >= 0.8"""
        ).fetchone()[0]

        low_confidence = conn.execute(
            """SELECT COUNT(DISTINCT container_id) FROM confidence_scores
               WHERE confidence < 0.6"""
        ).fetchone()[0]

        conn.close()

        return {
            "field_analysis": [
                {
                    "field": f["field_name"],
                    "total_extractions": f["total_scores"],
                    "average_confidence": round(f["avg_confidence"], 3),
                    "range": [round(f["min_confidence"], 3), round(f["max_confidence"], 3)],
                }
                for f in field_stats
            ],
            "validation_issues": [
                {
                    "type": i["issue_type"],
                    "severity": i["severity"],
                    "count": i["count"],
                }
                for i in issue_stats
            ],
            "confidence_distribution": {
                "high_confidence_containers": high_confidence,
                "low_confidence_containers": low_confidence,
            },
        }

    def get_filter_preset_usage(self) -> dict:
        """Get usage statistics for filter presets."""
        conn = get_connection()
        presets = conn.execute("""
            SELECT
                preset_name,
                last_used_at,
                created_at
            FROM filter_presets
            ORDER BY last_used_at DESC
        """).fetchall()
        conn.close()

        return {
            "total_presets": len(presets),
            "presets": [
                {
                    "name": p["preset_name"],
                    "created": p["created_at"],
                    "last_used": p["last_used_at"],
                }
                for p in presets
            ],
        }

    def get_audit_summary(self, days: int = 30) -> dict:
        """Get change audit summary for past N days."""
        conn = get_connection()
        since = datetime.now() - timedelta(days=days)

        changes = conn.execute("""
            SELECT
                field_name,
                COUNT(*) as change_count,
                changed_by
            FROM change_log
            WHERE changed_at >= ?
            GROUP BY field_name, changed_by
            ORDER BY change_count DESC
        """, (since.isoformat(),)).fetchall()

        conn.close()

        return {
            "period_days": days,
            "total_changes": sum(c["change_count"] for c in changes),
            "changes_by_field": [
                {
                    "field": c["field_name"],
                    "count": c["change_count"],
                    "last_modified_by": c["changed_by"],
                }
                for c in changes
            ],
        }

    def export_metrics_json(self) -> str:
        """Export all metrics as JSON string."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "pipeline": self.get_pipeline_stats(),
            "quality": self.get_data_quality_report(),
            "extraction": self.get_extraction_performance(),
            "filters": self.get_filter_preset_usage(),
            "audit": self.get_audit_summary(),
        }
        return json.dumps(metrics, indent=2, default=str)
