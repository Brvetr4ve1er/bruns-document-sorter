"""Floating Bottom Navigation Bar Component"""
import streamlit as st
from streamlit_option_menu import option_menu


def render_bottom_navbar() -> str:
    """
    Render a floating bottom navigation bar.
    Returns the selected page name.
    """
    st.markdown("""
        <style>
        /* Floating Bottom Navigation */
        .bottom-nav {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 999;
            background: rgba(20, 30, 48, 0.95);
            border-radius: 50px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            padding: 12px 24px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* Navigation Menu Styling */
        .bottom-nav [role="menuitemradio"] {
            color: #cbd5e0 !important;
            font-weight: 500;
            padding: 8px 16px !important;
            border-radius: 8px !important;
            transition: all 0.3s ease !important;
        }

        .bottom-nav [role="menuitemradio"]:hover {
            background-color: rgba(59, 130, 246, 0.2) !important;
            color: #60a5fa !important;
        }

        .bottom-nav [role="menuitemradio"][aria-selected="true"] {
            background-color: linear-gradient(135deg, #3b82f6, #2563eb) !important;
            color: white !important;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .bottom-nav {
                width: 90%;
                padding: 8px 16px;
            }
            .bottom-nav [role="menuitemradio"] {
                font-size: 0.85rem !important;
                padding: 6px 12px !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    selected = option_menu(
        menu_title=None,
        options=[
            "📊 Overview",
            "📄 Process PDFs",
            "📦 Containers",
            "🚢 Shipments",
            "✏️ Edit",
            "📊 Analytics",
            "📋 Logs",
            "⚙️ Settings"
        ],
        icons=[
            "graph-up",
            "file-earmark-pdf",
            "box-seam",
            "ship",
            "pencil-square",
            "bar-chart",
            "list-check",
            "gear"
        ],
        menu_icon="chevron-up",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"max-width": "1200px", "padding": "0px", "margin": "0 auto"},
            "nav-link": {
                "text-align": "center",
                "margin": "0px 5px",
                "padding": "8px 15px",
            },
        }
    )

    # Map option names to page names
    page_mapping = {
        "📊 Overview": "Overview",
        "📄 Process PDFs": "Process PDFs",
        "📦 Containers": "Containers",
        "🚢 Shipments": "Shipments",
        "✏️ Edit": "Edit Container",
        "📊 Analytics": "Analytics",
        "📋 Logs": "Logs",
        "⚙️ Settings": "Settings"
    }

    return page_mapping.get(selected, "Overview")


def init_navigation():
    """Initialize navigation state in session."""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Overview"
    if "selected_container" not in st.session_state:
        st.session_state.selected_container = None
    if "batch_selections" not in st.session_state:
        st.session_state.batch_selections = {}
