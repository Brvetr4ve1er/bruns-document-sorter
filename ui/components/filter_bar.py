"""
Filter bar component for document filtering by keys.
Phase 3: Enhanced with date ranges, port filter, quick presets, clear all.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from ui.styles import COLORS


# ─── Quick filter presets ──────────────────────────────────────────────────────
QUICK_PRESETS = {
    "🚢 En transit":     {"status": ["En transit"]},
    "📦 Livrés":         {"status": ["Livré"]},
    "📌 Réservés":       {"status": ["Réservé"]},
    "⚓ Arrivés":        {"status": ["Arrivé"]},
    "✅ Restitués":      {"status": ["Restitué"]},
    "📭 Dépotés":        {"status": ["Dépoté"]},
}


def render_filter_bar(df: pd.DataFrame) -> dict:
    """
    Render document filter controls.
    Returns dict with active filters.
    """
    st.markdown(
        f"""<div class="filter-container" data-aos="fade-down" data-aos-duration="600">
        <div class="filter-title">🔍 Filter Documents</div>
        </div>""",
        unsafe_allow_html=True
    )

    # ── Quick preset chips ────────────────────────────────────────────────────
    st.markdown("**Quick Filters:**")
    preset_cols = st.columns(len(QUICK_PRESETS) + 1)
    for i, (label, preset) in enumerate(QUICK_PRESETS.items()):
        with preset_cols[i]:
            if st.button(label, key=f"preset_{i}", use_container_width=True):
                # Apply preset
                st.session_state.active_filters["status"] = preset.get("status", [])
                st.session_state.active_filters["tan"] = []
                st.session_state.active_filters["carrier"] = []
                st.session_state.active_filters["search"] = ""
                st.session_state.active_filters["port"] = []
                st.session_state.active_filters["date_from"] = None
                st.session_state.active_filters["date_to"] = None
                st.rerun()

    with preset_cols[-1]:
        if st.button("🗑️ Clear All", key="clear_filters", use_container_width=True):
            st.session_state.active_filters = _empty_filters()
            st.rerun()

    st.markdown("---")

    # ── Main filter row ───────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        tan_options = sorted([x for x in df["N° TAN"].unique() if pd.notna(x) and str(x).strip()])
        selected_tan = st.multiselect(
            "🔖 Filter by TAN",
            options=tan_options,
            default=[x for x in st.session_state.active_filters.get("tan", []) if x in tan_options],
            key="filter_tan",
            help="Select one or more Transaction Reference Numbers"
        )
        st.session_state.active_filters["tan"] = selected_tan

    with col2:
        carrier_options = sorted([x for x in df["Compagnie maritime"].unique() if pd.notna(x) and str(x).strip()])
        selected_carriers = st.multiselect(
            "🚢 Filter by Carrier",
            options=carrier_options,
            default=[x for x in st.session_state.active_filters.get("carrier", []) if x in carrier_options],
            key="filter_carrier",
            help="Select one or more maritime companies"
        )
        st.session_state.active_filters["carrier"] = selected_carriers

    with col3:
        status_options = sorted([x for x in df["Statut Container"].unique() if pd.notna(x) and str(x).strip()])
        selected_status = st.multiselect(
            "📊 Filter by Status",
            options=status_options,
            default=[x for x in st.session_state.active_filters.get("status", []) if x in status_options],
            key="filter_status",
            help="Select one or more container statuses"
        )
        st.session_state.active_filters["status"] = selected_status

    with col4:
        port_options = sorted([x for x in df["Port"].unique() if pd.notna(x) and str(x).strip()])
        selected_ports = st.multiselect(
            "⚓ Filter by Port",
            options=port_options,
            default=[x for x in st.session_state.active_filters.get("port", []) if x in port_options],
            key="filter_port",
            help="Select one or more ports"
        )
        st.session_state.active_filters["port"] = selected_ports

    # ── Second row: text search + date ranges ─────────────────────────────────
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

    with col1:
        search_term = st.text_input(
            "🔎 Text Search",
            value=st.session_state.active_filters.get("search", ""),
            key="filter_search",
            placeholder="Container, Item, TAN, Carrier, Port, Transitaire...",
            help="Search across all key fields"
        )
        st.session_state.active_filters["search"] = search_term

    with col2:
        # ETD from
        sort_col = st.selectbox(
            "Sort by",
            options=["Date accostage", "Date shipment", "Date livraison", "N° Container", "N° TAN"],
            index=0,
            key="filter_sort_col"
        )
        st.session_state.active_filters["sort_col"] = sort_col

    with col3:
        sort_order = st.radio(
            "Order",
            options=["↓ Newest", "↑ Oldest"],
            index=0,
            key="filter_sort_order",
            horizontal=True
        )
        st.session_state.active_filters["sort_asc"] = (sort_order == "↑ Oldest")

    with col4:
        # Date window filter
        date_window = st.selectbox(
            "📅 Date Window",
            options=["All time", "Last 7 days", "Last 30 days", "Last 90 days", "Last 6 months"],
            index=0,
            key="filter_date_window"
        )
        st.session_state.active_filters["date_window"] = date_window

    return st.session_state.active_filters


def _empty_filters() -> dict:
    return {
        "tan": [], "carrier": [], "status": [], "port": [],
        "search": "", "sort_col": "Date accostage", "sort_asc": False,
        "date_window": "All time",
    }


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply active filters and sorting to the dataframe."""
    filtered = df.copy()

    # Multiselect filters
    if filters.get("tan"):
        filtered = filtered[filtered["N° TAN"].isin(filters["tan"])]
    if filters.get("carrier"):
        filtered = filtered[filtered["Compagnie maritime"].isin(filters["carrier"])]
    if filters.get("status"):
        filtered = filtered[filtered["Statut Container"].isin(filters["status"])]
    if filters.get("port"):
        filtered = filtered[filtered["Port"].isin(filters["port"])]

    # Full-text search across all key columns
    if filters.get("search"):
        term = filters["search"].lower().strip()
        search_cols = ["N° Container", "Item", "Port", "N° TAN", "Transitaire",
                       "Compagnie maritime", "Site livraison", "Chauffeur livraison"]
        mask = pd.Series([False] * len(filtered), index=filtered.index)
        for col in search_cols:
            if col in filtered.columns:
                mask |= filtered[col].astype(str).str.lower().str.contains(term, na=False)
        filtered = filtered[mask]

    # Date window filter — applied to the sort column (which is likely a date field)
    date_window = filters.get("date_window", "All time")
    sort_col = filters.get("sort_col", "Date accostage")
    if date_window != "All time" and sort_col in filtered.columns:
        window_map = {
            "Last 7 days": 7, "Last 30 days": 30,
            "Last 90 days": 90, "Last 6 months": 182,
        }
        days = window_map.get(date_window, 0)
        if days:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            date_col = pd.to_datetime(filtered[sort_col], errors="coerce")
            cutoff_dt = pd.to_datetime(cutoff)
            filtered = filtered[date_col >= cutoff_dt]

    # Sort
    if sort_col in filtered.columns:
        try:
            sort_series = pd.to_datetime(filtered[sort_col], errors="coerce")
            filtered = filtered.assign(_sort_key=sort_series).sort_values(
                "_sort_key", ascending=filters.get("sort_asc", False), na_position="last"
            ).drop(columns=["_sort_key"])
        except Exception:
            filtered = filtered.sort_values(sort_col, ascending=filters.get("sort_asc", False), na_position="last")

    return filtered.reset_index(drop=True)


def render_filter_summary(filters: dict, total: int, filtered: int):
    """Render summary of active filters and result count."""
    active_parts = []
    if filters.get("tan"):
        active_parts.append(f"**TAN:** {', '.join(filters['tan'][:2])}{'...' if len(filters['tan']) > 2 else ''}")
    if filters.get("carrier"):
        active_parts.append(f"**Carrier:** {len(filters['carrier'])}")
    if filters.get("status"):
        active_parts.append(f"**Status:** {', '.join(filters['status'])}")
    if filters.get("port"):
        active_parts.append(f"**Port:** {', '.join(filters['port'])}")
    if filters.get("search"):
        active_parts.append(f'**Search:** "{filters["search"]}"')
    if filters.get("date_window") and filters["date_window"] != "All time":
        active_parts.append(f"**Period:** {filters['date_window']}")

    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        if active_parts:
            st.caption("🔽 Active filters: " + " · ".join(active_parts))
        else:
            st.caption("Showing all documents — use filters above to narrow results")
    with col2:
        delta = filtered - total
        st.metric("Showing", f"{filtered:,}", delta=f"{delta:,}" if delta != 0 else None, delta_color="off")
    with col3:
        st.metric("Total", f"{total:,}")
