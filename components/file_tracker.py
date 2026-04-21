"""File Tracker Component - Display processed files and extraction results"""
import streamlit as st
import pandas as pd
from database_logic.database import get_connection
from pathlib import Path
import os


def get_processed_files() -> pd.DataFrame:
    """Get list of all processed files from database."""
    conn = get_connection()

    files = conn.execute("""
        SELECT
            fh.filename,
            fh.file_hash,
            fh.processed_at,
            COUNT(c.id) as container_count,
            AVG(cs.confidence) as avg_confidence
        FROM file_hashes fh
        LEFT JOIN containers c ON c.id IN (
            SELECT container_id FROM confidence_scores
            WHERE extracted_value LIKE '%' || fh.filename || '%'
        )
        LEFT JOIN confidence_scores cs ON c.id = cs.container_id
        GROUP BY fh.filename
        ORDER BY fh.processed_at DESC
    """).fetchall()

    conn.close()

    return pd.DataFrame([dict(f) for f in files]) if files else pd.DataFrame()


def get_extraction_by_filename(filename: str) -> list:
    """Get all containers extracted from a specific file."""
    conn = get_connection()

    containers = conn.execute("""
        SELECT
            c.id,
            c.'N° Container',
            c.'N° TAN',
            c.'Item',
            c.'Compagnie maritime',
            c.'Statut Container',
            c.'created_at',
            COALESCE(
                (SELECT AVG(confidence) FROM confidence_scores WHERE container_id = c.id),
                0
            ) as avg_confidence
        FROM containers c
        WHERE c.created_at IN (
            SELECT MAX(created_at) FROM containers
            WHERE created_at LIKE
            (SELECT DATE(processed_at) FROM file_hashes WHERE filename = ?)
        )
        LIMIT 10
    """, (filename,)).fetchall()

    conn.close()

    return [dict(c) for c in containers]


def render_file_tracker():
    """Render the file tracker dashboard."""
    st.subheader("📂 Processed Files Tracker")

    files_df = get_processed_files()

    if files_df.empty:
        st.info("No processed files found")
        return

    # Filter controls
    col1, col2 = st.columns([2, 1])

    with col1:
        search_term = st.text_input("🔍 Search files", key="file_search")

    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Recent", "Containers", "Confidence"],
            key="file_sort"
        )

    # Apply search filter
    if search_term:
        files_df = files_df[
            files_df["filename"].str.contains(search_term, case=False, na=False)
        ]

    # Apply sorting
    if sort_by == "Recent":
        files_df = files_df.sort_values("processed_at", ascending=False)
    elif sort_by == "Containers":
        files_df = files_df.sort_values("container_count", ascending=False)
    elif sort_by == "Confidence":
        files_df = files_df.sort_values("avg_confidence", ascending=False)

    # Display statistics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Files Processed", len(files_df))
    col2.metric("Total Containers", files_df["container_count"].sum())
    col3.metric("Avg Confidence", f"{files_df['avg_confidence'].mean():.1%}")
    col4.metric("Success Rate", f"{(files_df['container_count'] > 0).sum() / len(files_df) * 100:.0f}%")

    st.divider()

    # File list with expandable details
    for idx, file in files_df.iterrows():
        with st.expander(
            f"📄 {file['filename']} · {file['container_count']} containers · {file['avg_confidence']:.0%} confidence",
            expanded=False
        ):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.write("**File Hash**")
                st.code(file["file_hash"][:16] + "...")

            with col2:
                st.write("**Processed**")
                st.write(file["processed_at"])

            with col3:
                st.write("**Quality**")
                conf = file["avg_confidence"] or 0
                if conf >= 0.8:
                    st.success("🟢 High")
                elif conf >= 0.6:
                    st.warning("🟡 Medium")
                else:
                    st.error("🔴 Low")

            st.divider()

            # Show extracted containers
            containers = get_extraction_by_filename(file["filename"])
            if containers:
                st.write(f"**Extracted {len(containers)} Containers:**")

                container_df = pd.DataFrame(containers)
                st.dataframe(
                    container_df[[
                        "N° Container",
                        "N° TAN",
                        "Item",
                        "Compagnie maritime",
                        "Statut Container",
                        "avg_confidence"
                    ]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "avg_confidence": st.column_config.ProgressColumn(
                            "Confidence",
                            min_value=0,
                            max_value=1,
                        ),
                    }
                )

                # Action buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("👁️ View Details", key=f"view_{file['filename']}", use_container_width=True):
                        st.session_state["selected_file"] = file["filename"]

                with col2:
                    if st.button("🔄 Reprocess", key=f"reprocess_{file['filename']}", use_container_width=True):
                        st.info(f"Reprocessing {file['filename']}...")

                with col3:
                    if st.button("📥 Export", key=f"export_{file['filename']}", use_container_width=True):
                        csv_data = container_df.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv_data,
                            file_name=f"{file['filename']}_extracted.csv",
                            mime="text/csv",
                            key=f"dl_{file['filename']}"
                        )
            else:
                st.info("No containers extracted from this file")


def render_quick_stats():
    """Render quick statistics about file processing."""
    conn = get_connection()

    stats = {
        "total_files": conn.execute("SELECT COUNT(*) FROM file_hashes").fetchone()[0],
        "total_containers": conn.execute("SELECT COUNT(*) FROM containers").fetchone()[0],
        "cached_extractions": conn.execute("SELECT COUNT(*) FROM extraction_cache").fetchone()[0],
        "cache_hits": conn.execute("SELECT SUM(hit_count) FROM extraction_cache").fetchone()[0] or 0,
    }

    conn.close()

    # Display in columns
    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Files Processed",
        stats["total_files"],
        help="Total unique files processed"
    )
    col2.metric(
        "Containers Extracted",
        stats["total_containers"],
        help="Total containers successfully extracted"
    )
    col3.metric(
        "Cached Results",
        stats["cached_extractions"],
        help="Number of extraction results in cache"
    )
    col4.metric(
        "Cache Hits",
        stats["cache_hits"],
        help="Total times cache was used instead of reprocessing"
    )
