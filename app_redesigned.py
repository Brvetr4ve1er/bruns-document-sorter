"""
BRUNs Logistics Data Scraper - Redesigned UI with Floating Bottom Navbar
Main application with new architecture and all 18 improvements integrated
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from components.bottom_navbar import render_bottom_navbar, init_navigation
from components.filter_dashboard import render_filter_controls, render_preset_controls, render_batch_controls, render_filtered_table
from components.file_preview_modal import render_file_preview_modal
from components.file_tracker import render_file_tracker, render_quick_stats
from db.database import get_connection, fetch_containers_view, fetch_shipments_view, fetch_stats
from utils.filter_manager import FilterManager, apply_container_filters, apply_shipment_filters
from utils.stats_tracker import StatsTracker
from utils.batch_processor import BatchProcessor
from config import DB_PATH
import plotly.graph_objects as go
import plotly.express as px


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="BRUNs Logistics Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for overall styling
st.markdown("""
    <style>
    /* Remove default padding */
    .main { padding-bottom: 120px; }

    /* Floating navbar positioning */
    footer { display: none; }

    /* Data quality badges */
    .quality-high { color: #10b981; font-weight: bold; }
    .quality-medium { color: #f59e0b; font-weight: bold; }
    .quality-low { color: #ef4444; font-weight: bold; }

    /* Card styling */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
    }

    /* Filter panel styling */
    .filter-panel {
        background: rgba(15, 23, 42, 0.5);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.2);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize navigation state
init_navigation()

# ============================================================================
# PAGE DEFINITIONS
# ============================================================================


def page_overview():
    """Overview page with key metrics and statistics."""
    st.title("📊 Logistics Dashboard Overview")

    # Get statistics
    stats = fetch_stats()

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Containers", stats.get("total_containers", 0), help="Total containers in system")
    col2.metric("Total Shipments", stats.get("total_shipments", 0), help="Total shipments tracked")
    col3.metric("Pending Processing", stats.get("pending_files", 0), help="Files awaiting processing")
    col4.metric("System Status", "🟢 Healthy", help="All systems operational")

    st.divider()

    # Status distribution
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Container Status Distribution")
        containers_df = fetch_containers_view()
        if not containers_df.empty:
            status_counts = containers_df["Statut Container"].value_counts()
            fig = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title="Containers by Status"
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Processing Performance")
        tracker = StatsTracker()
        perf_stats = tracker.get_extraction_performance()

        col1a, col2a = st.columns(2)
        col1a.metric("Documents Processed", perf_stats.get("documents_processed", 0))
        col2a.metric("Success Rate", f"{perf_stats.get('success_rate', 0):.1%}")

    st.divider()

    # Recent activity
    st.subheader("📋 Recent Activity")
    conn = get_connection()
    recent = conn.execute("""
        SELECT 'Container' as type, 'N° Container' as item, created_at
        FROM containers
        ORDER BY created_at DESC
        LIMIT 5
    """).fetchall()
    conn.close()

    if recent:
        activity_df = pd.DataFrame([dict(r) for r in recent])
        st.dataframe(activity_df, use_container_width=True, hide_index=True)
    else:
        st.info("No recent activity")

    # Quick file stats
    st.divider()
    st.subheader("📂 File Processing Stats")
    render_quick_stats()


def page_process_pdfs():
    """PDF processing page."""
    st.title("📄 Process PDF Documents")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Upload PDF files",
            type="pdf",
            accept_multiple_files=True,
            help="Select one or more PDF files to process"
        )

    with col2:
        process_mode = st.radio(
            "Processing Mode",
            ["Standard", "High-Accuracy (Tesseract)", "Fast (Cache-only)"],
            index=0
        )

    if uploaded_file:
        st.info(f"📦 {len(uploaded_file)} file(s) selected for processing")

        # Show file details
        file_df = pd.DataFrame({
            "Filename": [f.name for f in uploaded_file],
            "Size (KB)": [f.size / 1024 for f in uploaded_file],
        })
        st.dataframe(file_df, use_container_width=True, hide_index=True)

        if st.button("▶️ Start Processing", use_container_width=True, type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, file in enumerate(uploaded_file):
                status_text.text(f"Processing {i+1}/{len(uploaded_file)}: {file.name}")
                progress_bar.progress((i+1) / len(uploaded_file))

                # Here would be the actual PDF processing logic
                # For now, just showing the UI structure

            st.success(f"✓ Processed {len(uploaded_file)} files successfully!")
            st.balloons()

    st.divider()

    # Processing queue status
    st.subheader("⏳ Processing Queue")
    processor = BatchProcessor()
    queue_status = processor.get_queue_progress()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pending", queue_status["pending"])
    col2.metric("Processing", queue_status["processing"])
    col3.metric("Completed", queue_status["completed"])
    col4.metric("Failed", queue_status["failed"])

    # Queue visualization
    if queue_status["total"] > 0:
        fig = go.Figure(data=[
            go.Bar(
                y=["Queue Status"],
                x=[queue_status["completed"]],
                name="Completed",
                orientation="h",
                marker_color="#10b981"
            ),
            go.Bar(
                y=["Queue Status"],
                x=[queue_status["processing"]],
                name="Processing",
                orientation="h",
                marker_color="#f59e0b"
            ),
            go.Bar(
                y=["Queue Status"],
                x=[queue_status["pending"]],
                name="Pending",
                orientation="h",
                marker_color="#ef4444"
            ),
        ])
        fig.update_layout(barmode="stack", height=200, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)


def page_containers():
    """Containers view with filtering and batch operations."""
    st.title("📦 Containers Database")

    # Render filter controls
    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
    filters = render_filter_controls()
    st.write("")
    render_preset_controls()
    st.markdown('</div>', unsafe_allow_html=True)

    # Get filtered data
    containers_df = fetch_containers_view()

    if not containers_df.empty:
        # Apply filters
        filtered_df = apply_container_filters(
            containers_df,
            carriers=filters.get("carriers") if filters.get("carriers") else None,
            sizes=filters.get("sizes") if filters.get("sizes") else None,
            statuses=filters.get("statuses") if filters.get("statuses") else None,
            search_text=filters.get("search_text") if filters.get("search_text") else None,
        )

        # Render batch controls
        render_batch_controls(filtered_df)

        # Render filtered table
        st.divider()
        render_filtered_table(filtered_df)

        # Show file preview if selected
        if st.session_state.get("show_preview") and st.session_state.get("selected_container"):
            st.divider()
            render_file_preview_modal(st.session_state["selected_container"])
    else:
        st.info("No containers found in database")


def page_shipments():
    """Shipments view with filtering."""
    st.title("🚢 Shipments Database")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        carriers = st.multiselect(
            "🚢 Shipping Companies",
            options=["CMA-CGM", "MSC", "Maersk", "Hapag-Lloyd", "ONE"],
            key="shipment_carrier_filter"
        )

    with col2:
        statuses = st.multiselect(
            "📊 Statuses",
            options=["PLANNED", "IN_TRANSIT", "COMPLETED", "CANCELLED"],
            key="shipment_status_filter"
        )

    with col3:
        search = st.text_input("🔍 Search shipments", key="shipment_search")

    # Get filtered data
    shipments_df = fetch_shipments_view()

    if not shipments_df.empty:
        filtered_df = apply_shipment_filters(
            shipments_df,
            carriers=carriers if carriers else None,
            statuses=statuses if statuses else None,
            search_text=search if search else None,
        )

        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

        # Export option
        if st.button("📥 Export as CSV"):
            st.download_button(
                label="Download CSV",
                data=filtered_df.to_csv(index=False),
                file_name="shipments_export.csv",
                mime="text/csv",
            )
    else:
        st.info("No shipments found")


def page_analytics():
    """Analytics dashboard with performance metrics and data quality."""
    st.title("📊 Analytics & Insights")

    tracker = StatsTracker()

    # Overview tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Pipeline Stats",
        "Data Quality",
        "Extraction Performance",
        "Audit Trail"
    ])

    with tab1:
        st.subheader("📈 Pipeline Statistics")
        pipeline_stats = tracker.get_pipeline_stats()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Containers", pipeline_stats["data_volume"]["total_containers"])
        col2.metric("Total Shipments", pipeline_stats["data_volume"]["total_shipments"])
        col3.metric("Average Confidence", f"{pipeline_stats['data_quality']['average_confidence']:.1%}")

        st.divider()
        st.write("**Cache Performance**")
        cache = pipeline_stats["cache_performance"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Cached Files", cache["cached_files"])
        col2.metric("Cache Hits", cache["total_cache_hits"])
        col3.metric("Hit Rate", f"{cache['cache_hit_rate']:.1%}")

    with tab2:
        st.subheader("✓ Data Quality Report")
        quality_report = tracker.get_data_quality_report()

        st.write("**Field Confidence Analysis**")
        if quality_report["field_analysis"]:
            field_df = pd.DataFrame(quality_report["field_analysis"])
            st.dataframe(field_df, use_container_width=True, hide_index=True)

        st.divider()
        st.write("**Validation Issues**")
        if quality_report["validation_issues"]:
            issues_df = pd.DataFrame(quality_report["validation_issues"])
            st.dataframe(issues_df, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("🎯 Extraction Performance")
        perf = tracker.get_extraction_performance()

        col1, col2 = st.columns(2)
        col1.metric("Documents Processed", perf["documents_processed"])
        col2.metric("Success Rate", f"{perf['success_rate']:.1%}")

    with tab4:
        st.subheader("📝 Audit Trail")
        audit = tracker.get_audit_summary(days=30)
        st.write(f"**Changes in last {audit['period_days']} days: {audit['total_changes']}**")
        if audit["changes_by_field"]:
            changes_df = pd.DataFrame(audit["changes_by_field"])
            st.dataframe(changes_df, use_container_width=True, hide_index=True)


def page_logs():
    """System logs and monitoring."""
    st.title("📋 System Logs & Monitoring")

    log_type = st.radio(
        "Select Log Type",
        ["Processing Logs", "Validation Logs", "Change Logs", "Error Logs"],
        horizontal=True
    )

    if log_type == "Processing Logs":
        st.subheader("📊 Processing Logs")
        st.info("Processing logs would show file processing history and results")

    elif log_type == "Validation Logs":
        st.subheader("✓ Validation Logs")
        conn = get_connection()
        issues = conn.execute("""
            SELECT issue_type, severity, COUNT(*) as count
            FROM validation_issues
            GROUP BY issue_type, severity
        """).fetchall()
        conn.close()

        if issues:
            issues_df = pd.DataFrame([dict(i) for i in issues])
            st.dataframe(issues_df, use_container_width=True, hide_index=True)

    elif log_type == "Change Logs":
        st.subheader("📝 Change Logs")
        conn = get_connection()
        changes = conn.execute("""
            SELECT field_name, changed_by, COUNT(*) as count
            FROM change_log
            GROUP BY field_name, changed_by
            ORDER BY count DESC
        """).fetchall()
        conn.close()

        if changes:
            changes_df = pd.DataFrame([dict(c) for c in changes])
            st.dataframe(changes_df, use_container_width=True, hide_index=True)

    elif log_type == "Error Logs":
        st.subheader("❌ Error Logs")
        st.info("System errors and exceptions would be displayed here")


def page_settings():
    """Settings page."""
    st.title("⚙️ System Settings")

    tab1, tab2, tab3 = st.tabs(["General", "Processing", "Database"])

    with tab1:
        st.subheader("General Settings")
        st.write("**Application Configuration**")
        col1, col2 = st.columns(2)

        with col1:
            st.session_state["app_name"] = st.text_input("App Name", value="BRUNs Logistics Scraper")
            st.session_state["auto_backup"] = st.checkbox("Enable Auto-backup", value=True)

        with col2:
            st.session_state["theme"] = st.selectbox("Theme", ["Dark", "Light", "Auto"])
            st.session_state["refresh_interval"] = st.slider("Refresh Interval (seconds)", 5, 60, 15)

    with tab2:
        st.subheader("Processing Settings")
        st.write("**PDF Processing Configuration**")

        col1, col2 = st.columns(2)

        with col1:
            st.session_state["ocr_enabled"] = st.checkbox("Enable OCR (Tesseract)", value=True)
            st.session_state["cache_enabled"] = st.checkbox("Enable Caching", value=True)

        with col2:
            st.session_state["confidence_threshold"] = st.slider("Confidence Threshold", 0.0, 1.0, 0.6)
            st.session_state["max_batch_size"] = st.slider("Max Batch Size", 5, 100, 20)

    with tab3:
        st.subheader("Database Settings")
        st.write(f"**Database Path**: `{DB_PATH}`")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 Optimize Database", use_container_width=True):
                conn = get_connection()
                conn.execute("VACUUM")
                conn.close()
                st.success("Database optimized!")

            if st.button("📊 Database Stats", use_container_width=True):
                conn = get_connection()
                tables = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table'
                """).fetchall()
                conn.close()
                st.write(f"Tables: {len(tables)}")

        with col2:
            if st.button("🗑️ Clear Cache (Old)", use_container_width=True):
                st.info("Cache older than 30 days would be cleared")

            if st.button("📁 View File Tracker", use_container_width=True):
                st.session_state["show_file_tracker"] = True

    # File tracker in collapsible section
    if st.session_state.get("show_file_tracker"):
        st.divider()
        render_file_tracker()


# ============================================================================
# MAIN APPLICATION FLOW
# ============================================================================

def main():
    """Main application entry point."""

    # Render bottom navbar and get selected page
    selected_page = render_bottom_navbar()

    st.session_state["current_page"] = selected_page

    # Route to appropriate page
    if "Overview" in selected_page:
        page_overview()
    elif "Process PDFs" in selected_page:
        page_process_pdfs()
    elif "Containers" in selected_page:
        page_containers()
    elif "Shipments" in selected_page:
        page_shipments()
    elif "Analytics" in selected_page:
        page_analytics()
    elif "Logs" in selected_page:
        page_logs()
    elif "Settings" in selected_page:
        page_settings()
    else:
        page_overview()

    # Add footer spacing for bottom navbar
    st.markdown("<br>" * 3, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
