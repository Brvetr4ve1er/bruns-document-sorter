"""Enhanced Filter Dashboard with Batch Operations"""
import streamlit as st
import pandas as pd
from utils.filter_manager import FilterManager
from utils.batch_processor import BatchProcessor
from database_logic.database import get_connection


def render_filter_controls() -> dict:
    """
    Render filter controls in columns.
    Returns dict with filter selections.
    """
    filter_manager = FilterManager()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        carriers = st.multiselect(
            "🚢 Shipping Companies",
            options=["CMA-CGM", "MSC", "Maersk", "Hapag-Lloyd", "ONE", "Evergreen"],
            default=[],
            key="carrier_filter"
        )

    with col2:
        sizes = st.multiselect(
            "📦 Container Sizes",
            options=["20ft", "40ft", "45ft", "53ft"],
            default=[],
            key="size_filter"
        )

    with col3:
        statuses = st.multiselect(
            "📊 Statuses",
            options=["ARRIVED", "IN_TRANSIT", "DELIVERED", "ARCHIVED", "HELD"],
            default=[],
            key="status_filter"
        )

    with col4:
        search_text = st.text_input(
            "🔍 Search (Container #, TAN, Item)",
            key="search_filter"
        )

    return {
        "carriers": carriers,
        "sizes": sizes,
        "statuses": statuses,
        "search_text": search_text,
    }


def render_preset_controls():
    """Render filter preset save/load controls."""
    filter_manager = FilterManager()

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        preset_name = st.text_input("💾 Save current filters as preset", key="preset_name_input")

    with col2:
        if st.button("Save Preset", use_container_width=True):
            if preset_name:
                filters = st.session_state.get("current_filters", {})
                if filter_manager.save_preset(preset_name, **filters):
                    st.success(f"Preset '{preset_name}' saved!")
                else:
                    st.error("Failed to save preset")

    with col3:
        presets = filter_manager.list_presets()
        if presets:
            selected_preset = st.selectbox(
                "📂 Load preset",
                options=presets,
                key="preset_selector"
            )
            if st.button("Load", use_container_width=True):
                preset = filter_manager.load_preset(selected_preset)
                if preset:
                    st.session_state.update(preset)
                    st.rerun()


def render_batch_controls(filtered_df: pd.DataFrame) -> dict:
    """
    Render batch operation controls.
    Returns dict with selected operations and items.
    """
    st.divider()
    st.subheader("⚙️ Batch Operations")

    col1, col2, col3 = st.columns(3)

    with col1:
        select_all = st.checkbox("✓ Select All", key="batch_select_all")

    with col2:
        show_batch_ops = st.checkbox("Show Batch Operations", key="show_batch_ops", value=False)

    with col3:
        batch_count = st.metric("Selected Items", len(st.session_state.get("batch_selections", {})))

    if show_batch_ops and len(st.session_state.get("batch_selections", {})) > 0:
        st.divider()
        operation = st.radio(
            "Select Operation",
            options=["Update Status", "Delete", "Archive", "Export"],
            horizontal=True,
            key="batch_operation"
        )

        col1, col2 = st.columns(2)

        with col1:
            if operation == "Update Status":
                new_status = st.selectbox(
                    "New Status",
                    options=["ARRIVED", "IN_TRANSIT", "DELIVERED", "ARCHIVED", "HELD"],
                    key="batch_status"
                )
                if st.button("Apply Status Change", use_container_width=True):
                    processor = BatchProcessor()
                    selected_ids = list(st.session_state["batch_selections"].keys())
                    count = processor.bulk_update_containers(
                        selected_ids,
                        {"statut_container": new_status}
                    )
                    st.success(f"Updated {count} containers to {new_status}")
                    st.session_state["batch_selections"] = {}
                    st.rerun()

            elif operation == "Delete":
                if st.button("🗑️ Delete Selected", use_container_width=True, type="secondary"):
                    if st.checkbox("Confirm deletion", key="confirm_delete"):
                        processor = BatchProcessor()
                        selected_ids = list(st.session_state["batch_selections"].keys())
                        count = processor.bulk_delete_containers(selected_ids)
                        st.success(f"Deleted {count} containers")
                        st.session_state["batch_selections"] = {}
                        st.rerun()

            elif operation == "Archive":
                if st.button("📦 Archive Selected", use_container_width=True):
                    processor = BatchProcessor()
                    selected_ids = list(st.session_state["batch_selections"].keys())
                    count = processor.bulk_archive_containers(selected_ids)
                    st.success(f"Archived {count} containers")
                    st.session_state["batch_selections"] = {}
                    st.rerun()

        with col2:
            if operation == "Export":
                if st.button("📥 Export Selected", use_container_width=True):
                    selected_ids = list(st.session_state["batch_selections"].keys())
                    if selected_ids:
                        export_data = filtered_df[filtered_df["id"].isin(selected_ids)]
                        st.download_button(
                            label="Download CSV",
                            data=export_data.to_csv(index=False),
                            file_name="batch_export.csv",
                            mime="text/csv",
                        )

    return {
        "operation": st.session_state.get("batch_operation"),
        "selected_items": list(st.session_state.get("batch_selections", {}).keys()),
        "select_all": select_all,
    }


def render_filtered_table(df: pd.DataFrame):
    """
    Render filtered results with batch selection checkboxes.
    """
    if df.empty:
        st.info("No results match your filters")
        return

    # Add checkbox column for batch selection
    st.subheader(f"📋 Results ({len(df)} items)")

    # Create columns for display
    cols = st.columns([0.5, 1, 1, 1.5, 1, 1, 0.8])

    with cols[0]:
        st.write("**☑️**")
    with cols[1]:
        st.write("**Container #**")
    with cols[2]:
        st.write("**TAN**")
    with cols[3]:
        st.write("**Shipping Company**")
    with cols[4]:
        st.write("**Status**")
    with cols[5]:
        st.write("**Size**")
    with cols[6]:
        st.write("**⋯**")

    for idx, row in df.iterrows():
        cols = st.columns([0.5, 1, 1, 1.5, 1, 1, 0.8])

        with cols[0]:
            selected = st.checkbox(
                label="select",
                value=st.session_state.get(f"batch_{row['id']}", False),
                key=f"batch_checkbox_{row['id']}",
                label_visibility="collapsed"
            )
            if selected:
                st.session_state.get("batch_selections", {})[row['id']] = True
            else:
                st.session_state.get("batch_selections", {}).pop(row['id'], None)

        with cols[1]:
            st.text(row.get("N° Container", "—"))

        with cols[2]:
            st.text(row.get("N° TAN", "—"))

        with cols[3]:
            st.text(row.get("Compagnie maritime", "—"))

        with cols[4]:
            status_color = {
                "ARRIVED": "🟢",
                "IN_TRANSIT": "🔵",
                "DELIVERED": "⚪",
                "ARCHIVED": "⚫",
                "HELD": "🟠"
            }
            status = row.get("Statut Container", "—")
            st.text(f"{status_color.get(status, '◯')} {status}")

        with cols[5]:
            st.text(row.get("Container size", "—"))

        with cols[6]:
            if st.button("👁️", key=f"preview_{row['id']}", help="Double-click to preview"):
                st.session_state["selected_container"] = row['id']
                st.session_state["show_preview"] = True
