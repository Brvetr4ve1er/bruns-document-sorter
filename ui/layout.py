"""
Main layout architecture for bottom-nav dashboard design.
Replaces sidebar with floating bottom navigation.
Includes AOS animation framework and double-click detection.
"""
import streamlit as st
from ui.styles import COLORS

def inject_layout_css():
    """Inject CSS for bottom navbar and main content layout."""
    # First, inject AOS CDN
    st.markdown("""
    <link rel="stylesheet" href="https://unpkg.com/aos@next/dist/aos.css" />
    <script src="https://unpkg.com/aos@next/dist/aos.js"></script>
    <script>
        // Initialize AOS on page load
        window.addEventListener('load', function() {
            AOS.init({
                duration: 600,
                once: true,
                offset: 80,
                easing: 'ease-out-cubic'
            });
        });
        // Refresh AOS when Streamlit reruns
        if (window.location.hash !== '#streamlit-rerun') {
            window.addEventListener('hashchange', function() {
                setTimeout(() => AOS.refreshHard(), 300);
            });
        }
    </script>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <style>
    /* ─── Hide default Streamlit sidebar ───────────────────────────────── */
    [data-testid="stSidebar"] {{ display: none; }}

    /* ─── Main container — add bottom padding for navbar ──────────────────── */
    .block-container {{
        padding-bottom: 120px !important;
    }}

    /* ─── Bottom Navigation Bar ────────────────────────────────────────────── */
    .bottom-navbar {{
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(11, 16, 32, 0.92);
        backdrop-filter: blur(12px);
        border: 1px solid {COLORS["border"]};
        border-radius: 50px;
        padding: 12px 24px;
        z-index: 999;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        display: flex;
        gap: 12px;
        align-items: center;
        width: fit-content;
    }}

    .nav-button {{
        padding: 10px 18px;
        border-radius: 30px;
        border: 1px solid transparent;
        background: rgba(99, 102, 241, 0.1);
        color: {COLORS["text"]};
        cursor: pointer;
        font-weight: 500;
        font-size: 0.9rem;
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        white-space: nowrap;
    }}

    .nav-button:hover {{
        background: rgba(99, 102, 241, 0.2);
        border-color: {COLORS["primary"]};
        transform: translateY(-2px);
    }}

    .nav-button.active {{
        background: linear-gradient(135deg, {COLORS["primary"]} 0%, {COLORS["primary_2"]} 100%);
        border-color: {COLORS["primary"]};
        color: white;
        box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4);
    }}

    .nav-divider {{
        width: 1px;
        height: 24px;
        background: {COLORS["border"]};
    }}

    /* ─── Status Indicator in Navbar ───────────────────────────────────────── */
    .nav-status {{
        display: flex;
        align-items: center;
        gap: 6px;
        margin-left: 12px;
        padding-left: 12px;
        border-left: 1px solid {COLORS["border"]};
        font-size: 0.8rem;
        color: {COLORS["text_muted"]};
    }}

    .status-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: {COLORS["success"]};
        animation: pulse 2s infinite;
    }}

    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.5; }}
    }}

    /* ─── Filter Bar Container ──────────────────────────────────────────────── */
    .filter-container {{
        background: linear-gradient(135deg, {COLORS["bg_2"]} 0%, {COLORS["bg_3"]} 100%);
        border: 1px solid {COLORS["border"]};
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 24px;
        backdrop-filter: blur(8px);
    }}

    .filter-title {{
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: {COLORS["text_muted"]};
        margin-bottom: 12px;
    }}

    /* ─── Document Grid ───────────────────────────────────────────────────────── */
    .doc-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 16px;
        margin-top: 24px;
    }}

    .doc-card {{
        background: linear-gradient(135deg, {COLORS["bg_2"]} 0%, {COLORS["bg_3"]} 100%);
        border: 1px solid {COLORS["border"]};
        border-radius: 12px;
        padding: 16px;
        transition: all 0.3s ease;
        cursor: pointer;
        position: relative;
        overflow: hidden;
    }}

    .doc-card::before {{
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, {COLORS["primary"]}, {COLORS["primary_2"]});
        opacity: 0;
        transition: opacity 0.3s ease;
        z-index: -1;
    }}

    .doc-card:hover {{
        transform: translateY(-4px);
        border-color: {COLORS["primary"]};
        box-shadow: 0 12px 32px rgba(99, 102, 241, 0.25);
    }}

    .doc-card:hover::before {{
        opacity: 0.1;
    }}

    /* ─── Viewer Modal ──────────────────────────────────────────────────────── */
    .viewer-modal {{
        background: linear-gradient(135deg, {COLORS["bg_2"]} 0%, {COLORS["bg_3"]} 100%);
        border: 1px solid {COLORS["border"]};
        border-radius: 16px;
        padding: 24px;
        margin-top: 24px;
        animation: slideUp 0.3s ease;
    }}

    @keyframes slideUp {{
        from {{
            opacity: 0;
            transform: translateY(20px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    /* ─── Animations ───────────────────────────────────────────────────────── */
    @keyframes fadeInDown {{
        from {{
            opacity: 0;
            transform: translateY(-10px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    </style>
    """, unsafe_allow_html=True)


def initialize_layout_state():
    """Initialize session state for page navigation and UI state."""
    if "current_page" not in st.session_state:
        st.session_state.current_page = "dashboard"
    if "selected_doc" not in st.session_state:
        st.session_state.selected_doc = None
    if "show_viewer" not in st.session_state:
        st.session_state.show_viewer = False
    if "active_filters" not in st.session_state:
        st.session_state.active_filters = {
            "tan": [],
            "carrier": [],
            "status": [],
            "search": "",
        }


def render_bottom_navbar():
    """Render floating bottom navigation bar with active state styling."""
    # Inject JavaScript to mark active nav button
    st.markdown(f"""
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        const currentPage = '{st.session_state.current_page}';
        const navButtons = document.querySelectorAll('button[key^="nav_"]');
        navButtons.forEach(btn => {{
            if (btn.getAttribute('key') === `nav_${{currentPage}}`) {{
                btn.classList.add('nav-button-active');
                btn.style.background = 'linear-gradient(135deg, #6366F1, #8B5CF6)';
                btn.style.color = 'white';
            }} else {{
                btn.classList.remove('nav-button-active');
            }}
        }});
    }});
    </script>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4, spacer = st.columns([1.2, 1.2, 1.2, 1.2, 3])

    with col1:
        if st.button(
            "📊 Dashboard",
            key="nav_dashboard",
            use_container_width=True,
            help="View all documents and containers"
        ):
            st.session_state.current_page = "dashboard"
            st.session_state.show_viewer = False
            st.rerun()

    with col2:
        if st.button(
            "⚙️ Processing",
            key="nav_processing",
            use_container_width=True,
            help="Monitor batch processing"
        ):
            st.session_state.current_page = "processing"
            st.session_state.show_viewer = False
            st.rerun()

    with col3:
        if st.button(
            "📤 Export",
            key="nav_export",
            use_container_width=True,
            help="Export filtered documents"
        ):
            st.session_state.current_page = "export"
            st.session_state.show_viewer = False
            st.rerun()

    with col4:
        if st.button(
            "🛠️ Settings",
            key="nav_settings",
            use_container_width=True,
            help="Configuration and tools"
        ):
            st.session_state.current_page = "settings"
            st.session_state.show_viewer = False
            st.rerun()


def render_page_header(title: str, description: str = None, icon: str = ""):
    """Render page header with title and optional description."""
    st.markdown(f"""
    <div style="margin-bottom: 24px;">
        <h1 style="margin: 0; display: flex; align-items: center; gap: 12px;">
            {icon} {title}
        </h1>
        {f'<p style="margin: 8px 0 0 0; color: #8C95B3; font-size: 0.95rem;">{description}</p>' if description else ''}
    </div>
    """, unsafe_allow_html=True)
