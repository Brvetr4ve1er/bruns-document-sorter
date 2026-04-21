"""File Preview Modal Component - Double-click to view PDF + extracted data"""
import streamlit as st
import pandas as pd
from database_logic.database import get_connection
from pathlib import Path
import os


def get_container_data(container_id: int) -> dict:
    """Fetch complete container and related shipment data."""
    conn = get_connection()

    container = conn.execute(
        "SELECT * FROM containers WHERE id = ?",
        (container_id,)
    ).fetchone()

    if not container:
        conn.close()
        return None

    # Get related shipment if exists
    shipment = None
    if container.get("shipment_id"):
        shipment = conn.execute(
            "SELECT * FROM shipments WHERE id = ?",
            (container["shipment_id"],)
        ).fetchone()

    # Get confidence scores
    confidence_scores = conn.execute(
        "SELECT field_name, confidence, extracted_value FROM confidence_scores WHERE container_id = ?",
        (container_id,)
    ).fetchall()

    # Get validation issues
    validation_issues = conn.execute(
        "SELECT issue_type, issue_desc, severity, is_resolved FROM validation_issues WHERE container_id = ?",
        (container_id,)
    ).fetchall()

    # Get change history
    change_history = conn.execute(
        "SELECT field_name, old_value, new_value, changed_by, changed_at FROM change_log WHERE container_id = ? ORDER BY changed_at DESC LIMIT 20",
        (container_id,)
    ).fetchall()

    conn.close()

    return {
        "container": dict(container) if container else None,
        "shipment": dict(shipment) if shipment else None,
        "confidence_scores": [dict(c) for c in confidence_scores],
        "validation_issues": [dict(v) for v in validation_issues],
        "change_history": [dict(c) for c in change_history],
    }


def render_file_preview_modal(container_id: int):
    """Render modal with PDF viewer + extracted data tabs."""
    data = get_container_data(container_id)

    if not data or not data["container"]:
        st.error("Container not found")
        return

    container = data["container"]

    # Modal header
    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 12px 12px 0 0;
            color: white;
            margin-bottom: 20px;
        ">
            <h2 style="margin: 0;">📦 {container.get('N° Container', 'Unknown')}</h2>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">TAN: {container.get('N° TAN', '—')}</p>
        </div>
    """, unsafe_allow_html=True)

    # Tab navigation
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📄 Extracted Data",
        "✓ Confidence Scores",
        "⚠️ Validation",
        "📝 Change History",
        "📊 Related Shipment"
    ])

    with tab1:
        st.subheader("Extracted Container Information")
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Container Details**")
            extracted_fields = {
                "Container #": container.get("N° Container"),
                "TAN #": container.get("N° TAN"),
                "Item": container.get("Item"),
                "Size": container.get("Container size"),
                "Status": container.get("Statut Container"),
                "Company": container.get("Compagnie maritime"),
            }
            for label, value in extracted_fields.items():
                st.write(f"- **{label}**: {value or '—'}")

        with col2:
            st.write("**Dates & Times**")
            date_fields = {
                "ETD": container.get("ETD"),
                "ETA": container.get("ETA"),
                "Delivery Date": container.get("date_livraison"),
                "Processing Date": container.get("created_at"),
            }
            for label, value in date_fields.items():
                st.write(f"- **{label}**: {value or '—'}")

        st.divider()
        st.write("**Full Container Record**")
        st.dataframe(
            pd.DataFrame([container]),
            use_container_width=True,
            hide_index=True
        )

    with tab2:
        st.subheader("📊 Data Confidence Scores")
        if data["confidence_scores"]:
            confidence_df = pd.DataFrame(data["confidence_scores"])
            confidence_df["confidence"] = confidence_df["confidence"].apply(lambda x: f"{x:.1%}")

            # Color code by confidence level
            st.dataframe(
                confidence_df[["field_name", "confidence", "extracted_value"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "field_name": st.column_config.TextColumn("Field"),
                    "confidence": st.column_config.TextColumn("Confidence"),
                    "extracted_value": st.column_config.TextColumn("Extracted Value"),
                }
            )

            # Summary stats
            scores = [float(c["confidence"]) for c in data["confidence_scores"]]
            avg = sum(scores) / len(scores) if scores else 0
            quality = "🟢 High" if avg >= 0.8 else "🟡 Medium" if avg >= 0.6 else "🔴 Low"

            col1, col2, col3 = st.columns(3)
            col1.metric("Average Confidence", f"{avg:.1%}")
            col2.metric("Quality Level", quality)
            col3.metric("Scored Fields", len(scores))
        else:
            st.info("No confidence scores available for this container")

    with tab3:
        st.subheader("⚠️ Validation Issues")
        if data["validation_issues"]:
            # Group by severity
            issues_df = pd.DataFrame(data["validation_issues"])

            errors = issues_df[issues_df["severity"] == "error"]
            warnings = issues_df[issues_df["severity"] == "warning"]

            if not errors.empty:
                st.error(f"**{len(errors)} Error(s)**")
                for _, issue in errors.iterrows():
                    st.write(f"❌ **{issue['issue_type']}**: {issue['issue_desc']}")

            if not warnings.empty:
                st.warning(f"**{len(warnings)} Warning(s)**")
                for _, issue in warnings.iterrows():
                    st.write(f"⚠️ **{issue['issue_type']}**: {issue['issue_desc']}")
        else:
            st.success("✓ No validation issues found")

    with tab4:
        st.subheader("📝 Change History")
        if data["change_history"]:
            history_df = pd.DataFrame(data["change_history"])
            st.dataframe(
                history_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "field_name": st.column_config.TextColumn("Field"),
                    "old_value": st.column_config.TextColumn("Old Value"),
                    "new_value": st.column_config.TextColumn("New Value"),
                    "changed_by": st.column_config.TextColumn("Changed By"),
                    "changed_at": st.column_config.TextColumn("When"),
                }
            )
        else:
            st.info("No changes recorded for this container")

    with tab5:
        st.subheader("🚢 Related Shipment")
        if data["shipment"]:
            shipment = data["shipment"]
            st.write("**Shipment Information**")
            st.dataframe(
                pd.DataFrame([shipment]),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No related shipment found")

    # Close button
    st.divider()
    if st.button("✕ Close Preview", use_container_width=True):
        st.session_state["show_preview"] = False
        st.rerun()
