"""Centralised style injection — gives Streamlit a modern, animated look."""
import streamlit as st

# ───────────────────────────────────────────────────────────────────────────────
# Design tokens
# ───────────────────────────────────────────────────────────────────────────────
COLORS = {
    "bg":          "#0B1020",
    "bg_2":        "#141A2E",
    "bg_3":        "#1B2341",
    "border":      "#2A3454",
    "text":        "#E6E9F2",
    "text_muted":  "#8C95B3",
    "primary":     "#6366F1",   # indigo
    "primary_2":   "#8B5CF6",   # violet
    "accent":      "#06B6D4",   # cyan
    "success":     "#10B981",
    "warning":     "#F59E0B",
    "danger":      "#EF4444",
    "pink":        "#EC4899",
}

STATUS_STYLE = {
    # shipment-level (EN)
    "BOOKED":       ("#065F46", "#10B981", "🟢"),
    "IN_TRANSIT":   ("#1E40AF", "#3B82F6", "🚢"),
    "UNKNOWN":      ("#374151", "#9CA3AF", "⚪"),
    # container-level (FR) — matches the xlsx values
    "Réservé":      ("#065F46", "#10B981", "📌"),
    "En transit":   ("#1E3A8A", "#60A5FA", "🚢"),
    "Arrivé":       ("#4C1D95", "#A78BFA", "⚓"),
    "Livré":        ("#065F46", "#34D399", "📦"),
    "Dépoté":       ("#7C2D12", "#FB923C", "📭"),
    "Restitué":     ("#334155", "#94A3B8", "✅"),
}


def inject_global_css():
    """Inject app-wide CSS. Call once at the top of app.py after page config."""
    st.markdown(f"""
    <style>
    /* ─── Root / Typography ───────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');
    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, system-ui, sans-serif !important;
    }}
    code, pre, .stCodeBlock {{ font-family: 'JetBrains Mono', monospace !important; }}

    /* ─── Global background — soft radial glow ─────────────────────────── */
    .stApp {{
        background:
            radial-gradient(1200px 600px at 10% -10%, rgba(99,102,241,0.18), transparent 50%),
            radial-gradient(1000px 500px at 90% 100%, rgba(139,92,246,0.12), transparent 50%),
            {COLORS["bg"]};
    }}

    /* ─── Hide default Streamlit chrome ────────────────────────────────── */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header[data-testid="stHeader"] {{ background: transparent; }}
    .block-container {{ padding-top: 1.5rem !important; padding-bottom: 3rem !important; max-width: 1400px; }}

    /* ─── Sidebar ──────────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {COLORS["bg_2"]} 0%, {COLORS["bg"]} 100%);
        border-right: 1px solid {COLORS["border"]};
    }}
    [data-testid="stSidebar"] .stRadio > label > div:first-child {{ display: none; }}
    [data-testid="stSidebar"] [role="radiogroup"] > label {{
        padding: 10px 12px;
        border-radius: 10px;
        margin-bottom: 4px;
        transition: all .18s ease;
        cursor: pointer;
    }}
    [data-testid="stSidebar"] [role="radiogroup"] > label:hover {{
        background: rgba(99,102,241,0.10);
        transform: translateX(2px);
    }}
    [data-testid="stSidebar"] [role="radiogroup"] > label[data-checked="true"],
    [data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {{
        background: linear-gradient(90deg, rgba(99,102,241,.22), rgba(139,92,246,.10));
        box-shadow: inset 3px 0 0 {COLORS["primary"]};
    }}

    /* ─── Headings ─────────────────────────────────────────────────────── */
    h1, h2, h3 {{ letter-spacing: -0.02em; font-weight: 700; }}
    h1 {{
        background: linear-gradient(135deg, #fff 0%, #A5B4FC 50%, #C4B5FD 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: fadeInDown .5s ease-out;
    }}

    /* ─── Metrics — sleek glowing cards ────────────────────────────────── */
    [data-testid="stMetric"] {{
        background: linear-gradient(135deg, {COLORS["bg_2"]} 0%, {COLORS["bg_3"]} 100%);
        border: 1px solid {COLORS["border"]};
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,.25);
        transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
        position: relative;
        overflow: hidden;
    }}
    [data-testid="stMetric"]::before {{
        content: '';
        position: absolute; inset: 0; border-radius: 16px;
        background: linear-gradient(90deg, {COLORS["primary"]}, {COLORS["primary_2"]}, {COLORS["accent"]});
        opacity: 0; transition: opacity .25s ease;
        -webkit-mask:
            linear-gradient(#fff 0 0) content-box,
            linear-gradient(#fff 0 0);
        -webkit-mask-composite: xor;
                mask-composite: exclude;
        padding: 1px;
    }}
    [data-testid="stMetric"]:hover {{
        transform: translateY(-3px);
        box-shadow: 0 12px 28px rgba(99,102,241,.25);
    }}
    [data-testid="stMetric"]:hover::before {{ opacity: 1; }}
    [data-testid="stMetricValue"] {{
        font-size: 2rem !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #fff, #C7D2FE);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    [data-testid="stMetricLabel"] {{ color: {COLORS["text_muted"]} !important; font-size: 0.78rem !important; text-transform: uppercase; letter-spacing: 0.05em; }}

    /* ─── Buttons ──────────────────────────────────────────────────────── */
    .stButton > button {{
        border-radius: 10px;
        font-weight: 600;
        letter-spacing: 0.01em;
        transition: all .2s ease;
        border: 1px solid {COLORS["border"]};
        background: {COLORS["bg_2"]};
        color: {COLORS["text"]};
    }}
    .stButton > button:hover {{
        transform: translateY(-1px);
        border-color: {COLORS["primary"]};
        box-shadow: 0 6px 18px rgba(99,102,241,.30);
    }}
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {COLORS["primary"]} 0%, {COLORS["primary_2"]} 100%);
        border: none;
        color: white;
        box-shadow: 0 4px 14px rgba(99,102,241,.35);
    }}
    .stButton > button[kind="primary"]:hover {{
        box-shadow: 0 8px 22px rgba(99,102,241,.55);
        transform: translateY(-2px);
    }}

    /* Download buttons */
    .stDownloadButton > button {{
        border-radius: 10px;
        background: linear-gradient(135deg, {COLORS["success"]} 0%, #059669 100%);
        border: none; color: white; font-weight: 600;
        box-shadow: 0 4px 14px rgba(16,185,129,.30);
    }}
    .stDownloadButton > button:hover {{ transform: translateY(-1px); box-shadow: 0 8px 22px rgba(16,185,129,.50); }}

    /* ─── Inputs, selects, textareas ───────────────────────────────────── */
    .stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea {{
        background: {COLORS["bg_2"]} !important;
        border: 1px solid {COLORS["border"]} !important;
        border-radius: 10px !important;
        color: {COLORS["text"]} !important;
        transition: all .2s ease;
    }}
    .stTextInput input:focus, .stNumberInput input:focus, .stDateInput input:focus, .stTextArea textarea:focus {{
        border-color: {COLORS["primary"]} !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,.18) !important;
    }}
    [data-baseweb="select"] > div {{
        background: {COLORS["bg_2"]} !important;
        border-radius: 10px !important;
        border-color: {COLORS["border"]} !important;
    }}

    /* ─── Tabs ─────────────────────────────────────────────────────────── */
    .stTabs [role="tablist"] {{
        gap: 6px;
        background: {COLORS["bg_2"]};
        padding: 6px;
        border-radius: 12px;
        border: 1px solid {COLORS["border"]};
    }}
    .stTabs [role="tab"] {{
        border-radius: 8px;
        padding: 8px 16px;
        color: {COLORS["text_muted"]};
        transition: all .2s ease;
    }}
    .stTabs [role="tab"]:hover {{ color: {COLORS["text"]}; }}
    .stTabs [role="tab"][aria-selected="true"] {{
        background: linear-gradient(135deg, {COLORS["primary"]}, {COLORS["primary_2"]});
        color: white !important;
        box-shadow: 0 4px 14px rgba(99,102,241,.35);
    }}

    /* ─── Expander ─────────────────────────────────────────────────────── */
    .streamlit-expanderHeader, [data-testid="stExpander"] details > summary {{
        background: {COLORS["bg_2"]} !important;
        border: 1px solid {COLORS["border"]} !important;
        border-radius: 10px !important;
        font-weight: 600;
        transition: border-color .2s;
    }}
    [data-testid="stExpander"] details[open] > summary {{ border-color: {COLORS["primary"]} !important; }}

    /* ─── Dataframe ────────────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {{
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid {COLORS["border"]};
        box-shadow: 0 4px 20px rgba(0,0,0,.20);
    }}
    [data-testid="stDataFrame"] [role="columnheader"] {{
        background: {COLORS["bg_3"]} !important;
        color: {COLORS["text"]} !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        font-size: 0.72rem;
        letter-spacing: 0.04em;
    }}

    /* ─── Alerts / toasts ──────────────────────────────────────────────── */
    [data-testid="stAlert"] {{ border-radius: 12px; border-left-width: 4px; }}

    /* ─── Progress bar ─────────────────────────────────────────────────── */
    [data-testid="stProgress"] > div > div > div {{
        background: linear-gradient(90deg, {COLORS["primary"]}, {COLORS["primary_2"]}, {COLORS["accent"]}) !important;
        background-size: 200% 100% !important;
        animation: shimmer 2s linear infinite;
    }}

    /* ─── Divider ──────────────────────────────────────────────────────── */
    hr {{ border-color: {COLORS["border"]} !important; opacity: .5; }}

    /* ─── Custom components ────────────────────────────────────────────── */
    .hero-banner {{
        background: linear-gradient(135deg, rgba(99,102,241,.15) 0%, rgba(139,92,246,.08) 50%, rgba(6,182,212,.10) 100%);
        border: 1px solid {COLORS["border"]};
        border-radius: 20px;
        padding: 28px 32px;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
        animation: fadeInUp .6s ease-out;
    }}
    .hero-banner::before {{
        content: '';
        position: absolute; top: -50%; right: -20%;
        width: 400px; height: 400px;
        background: radial-gradient(circle, rgba(99,102,241,.25) 0%, transparent 70%);
        animation: float 8s ease-in-out infinite;
    }}
    .hero-title {{
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        background: linear-gradient(135deg, #fff, #C7D2FE 50%, #DDD6FE);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin: 0 0 4px 0;
    }}
    .hero-sub {{ color: {COLORS["text_muted"]}; font-size: 1rem; margin: 0; }}
    .hero-emoji {{ font-size: 3rem; display: inline-block; animation: wave 2.5s ease-in-out infinite; transform-origin: 70% 70%; }}

    .badge {{
        display: inline-flex; align-items: center; gap: 6px;
        padding: 4px 10px; border-radius: 20px;
        font-size: 0.78rem; font-weight: 600;
        border: 1px solid transparent;
    }}

    .stat-pill {{
        display: inline-flex; align-items: center; gap: 8px;
        padding: 6px 14px; border-radius: 999px;
        background: {COLORS["bg_2"]}; border: 1px solid {COLORS["border"]};
        font-size: 0.85rem; font-weight: 500;
        transition: all .2s ease;
    }}
    .stat-pill:hover {{ border-color: {COLORS["primary"]}; transform: translateY(-1px); }}
    .stat-pill .dot {{ width: 8px; height: 8px; border-radius: 50%; background: {COLORS["primary"]}; box-shadow: 0 0 8px currentColor; }}

    .glass-card {{
        background: linear-gradient(135deg, rgba(255,255,255,.05), rgba(255,255,255,.01));
        backdrop-filter: blur(16px) saturate(180%);
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 20px;
        padding: 20px;
        transition: all .3s cubic-bezier(0.23, 1, 0.320, 1);
        position: relative;
        overflow: hidden;
    }}
    .glass-card::before {{
        content: '';
        position: absolute; inset: 0; border-radius: 20px;
        background: linear-gradient(135deg, rgba(99,102,241,.1), rgba(139,92,246,.05));
        opacity: 0; transition: opacity .3s ease;
        pointer-events: none;
    }}
    .glass-card:hover {{
        border-color: rgba(255,255,255,.2);
        transform: translateY(-4px);
        box-shadow: 0 8px 32px rgba(99,102,241,.20), inset 0 1px 0 rgba(255,255,255,.1);
    }}
    .glass-card:hover::before {{ opacity: 1; }}

    /* ─── Bottom Navigation — Liquid Glass ─────────────────────────────── */
    .bottom-navbar {{
        position: fixed; bottom: 20px; left: 50%;
        transform: translateX(-50%);
        background: linear-gradient(135deg, rgba(11,16,32,0.88), rgba(20,26,46,0.92));
        backdrop-filter: blur(20px) saturate(190%);
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 60px;
        padding: 12px 20px;
        display: flex; gap: 8px; align-items: center;
        z-index: 999;
        box-shadow: 0 8px 32px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.1);
        animation: slideUp .5s cubic-bezier(0.34, 1.56, 0.64, 1);
    }}
    .nav-button {{
        padding: 10px 18px;
        border-radius: 50px;
        border: 1px solid rgba(255,255,255,.1);
        background: rgba(255,255,255,.03);
        color: {COLORS["text_muted"]};
        font-weight: 600;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all .2s ease;
        display: inline-flex; align-items: center; gap: 6px;
    }}
    .nav-button:hover {{
        background: rgba(255,255,255,.08);
        border-color: rgba(255,255,255,.2);
        color: {COLORS["text"]};
        transform: translateY(-1px);
    }}
    .nav-button.active {{
        background: linear-gradient(135deg, {COLORS["primary"]}, {COLORS["primary_2"]});
        border-color: {COLORS["primary"]};
        color: white;
        box-shadow: 0 4px 16px rgba(99,102,241,.3);
    }}

    /* ─── Document Cards — Enhanced Glass ──────────────────────────────── */
    [data-testid="stContainer"] > .glass-card {{
        background: linear-gradient(135deg, rgba(20,26,46,0.6), rgba(27,35,65,0.4));
        backdrop-filter: blur(12px);
        border: 1px solid rgba(99,102,241,.2);
        box-shadow: 0 4px 24px rgba(0,0,0,.2), inset 0 1px 0 rgba(255,255,255,.08);
    }}
    [data-testid="stContainer"] > .glass-card:hover {{
        border-color: rgba(99,102,241,.4);
        box-shadow: 0 12px 36px rgba(99,102,241,.25), inset 0 1px 0 rgba(255,255,255,.12);
    }}

    /* ─── Filter Container ─────────────────────────────────────────────── */
    .filter-container {{
        background: linear-gradient(135deg, rgba(11,16,32,0.5), rgba(20,26,46,0.6));
        backdrop-filter: blur(12px);
        border: 1px solid rgba(99,102,241,.15);
        border-radius: 16px;
        padding: 18px 20px;
        margin-bottom: 20px;
        animation: slideDown .4s ease-out;
    }}
    .filter-title {{
        font-size: 1rem; font-weight: 700;
        color: {COLORS["text"]}; margin: 0;
        letter-spacing: 0.02em;
    }}

    /* ─── Status Badge Enhancement ──────────────────────────────────────── */
    .status-badge {{
        padding: 6px 12px; border-radius: 8px;
        font-weight: 600; font-size: 0.85rem;
        backdrop-filter: blur(8px);
        border: 1px solid;
        display: inline-flex; align-items: center; gap: 4px;
    }}

    /* ─── Modal Container ──────────────────────────────────────────────── */
    [data-testid="stContainer"] > div > [data-testid="stContainer"] {{
        background: linear-gradient(135deg, rgba(11,16,32,0.7), rgba(27,35,65,0.5));
        backdrop-filter: blur(20px);
        border: 1px solid rgba(99,102,241,.25);
        border-radius: 20px;
        padding: 28px;
        box-shadow: 0 20px 60px rgba(0,0,0,.4);
        animation: scaleIn .3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }}

    /* ─── Animations ───────────────────────────────────────────────────── */
    @keyframes fadeInUp   {{ from {{ opacity: 0; transform: translateY(12px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes fadeInDown {{ from {{ opacity: 0; transform: translateY(-12px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes slideUp    {{ from {{ opacity: 0; transform: translate(-50%, 20px); }} to {{ opacity: 1; transform: translate(-50%, 0); }} }}
    @keyframes slideDown  {{ from {{ opacity: 0; transform: translateY(-10px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes scaleIn    {{ from {{ opacity: 0; transform: scale(0.95); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes shimmer    {{ 0% {{ background-position: 200% 0; }} 100% {{ background-position: -200% 0; }} }}
    @keyframes pulse      {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .55; }} }}
    @keyframes float      {{ 0%,100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-18px); }} }}
    @keyframes wave       {{ 0%,100% {{ transform: rotate(0); }} 15% {{ transform: rotate(14deg); }} 30% {{ transform: rotate(-8deg); }} 45% {{ transform: rotate(10deg); }} 60% {{ transform: rotate(-4deg); }} 75% {{ transform: rotate(6deg); }} }}

    /* ─── AOS Animation Integration ────────────────────────────────────── */
    [data-aos] {{ opacity: 1; }}
    .aos-init [data-aos] {{ opacity: 0; }}
    .aos-animate {{ animation-duration: 0.6s; animation-fill-mode: both; }}

    /* Fade animations */
    [data-aos="fade-up"] {{ transform: translateY(26px); opacity: 0; }}
    [data-aos="fade-up"].aos-animate {{ animation: fadeInUp 0.6s ease-out forwards; }}
    [data-aos="fade-down"] {{ transform: translateY(-26px); opacity: 0; }}
    [data-aos="fade-down"].aos-animate {{ animation: fadeInDown 0.6s ease-out forwards; }}

    /* Scale animations */
    [data-aos="scale-in"] {{ transform: scale(0.95); opacity: 0; }}
    [data-aos="scale-in"].aos-animate {{ animation: scaleIn 0.6s ease-out forwards; }}

    /* Scrollbars */
    ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
    ::-webkit-scrollbar-track {{ background: {COLORS["bg"]}; }}
    ::-webkit-scrollbar-thumb {{ background: {COLORS["border"]}; border-radius: 5px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {COLORS["primary"]}; }}
    </style>
    """, unsafe_allow_html=True)


# ───────────────────────────────────────────────────────────────────────────────
# Reusable HTML components
# ───────────────────────────────────────────────────────────────────────────────

def hero(title: str, subtitle: str = "", emoji: str = "🚢"):
    st.markdown(f"""
    <div class="hero-banner">
      <div style="display:flex; align-items:center; gap:20px;">
        <div class="hero-emoji">{emoji}</div>
        <div>
          <h1 class="hero-title">{title}</h1>
          <p class="hero-sub">{subtitle}</p>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def status_badge(value: str) -> str:
    """Return inline HTML string for a colored status badge."""
    bg, fg, icon = STATUS_STYLE.get(value, ("#374151", "#9CA3AF", "•"))
    return (
        f'<span class="badge" style="background:{bg}33;color:{fg};border-color:{fg}55;">'
        f'{icon} {value}</span>'
    )


def stat_pill(label: str, value, color: str = None) -> str:
    c = color or COLORS["primary"]
    return (
        f'<span class="stat-pill"><span class="dot" style="background:{c};color:{c};"></span>'
        f'<strong>{value}</strong>&nbsp;<span style="color:{COLORS["text_muted"]};">{label}</span></span>'
    )


def quick_stats_row(stats: dict):
    """Render a sleek row of stat pills."""
    pills = []
    pills.append(stat_pill("shipments", stats["shipments"], COLORS["primary"]))
    pills.append(stat_pill("containers", stats["containers"], COLORS["accent"]))
    pills.append(stat_pill("booked", stats["booked"], COLORS["success"]))
    pills.append(stat_pill("in transit", stats["in_transit"], "#3B82F6"))
    st.markdown(
        '<div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">'
        + "".join(pills) + '</div>',
        unsafe_allow_html=True,
    )


def empty_state(icon: str, title: str, hint: str):
    st.markdown(f"""
    <div style="text-align:center; padding:60px 20px; animation: fadeInUp .5s ease-out;">
      <div style="font-size:4rem; margin-bottom:12px; animation: float 3s ease-in-out infinite;">{icon}</div>
      <h3 style="margin:0 0 6px 0; color:{COLORS["text"]};">{title}</h3>
      <p style="color:{COLORS["text_muted"]}; margin:0;">{hint}</p>
    </div>
    """, unsafe_allow_html=True)


def section_header(title: str, emoji: str = "", subtitle: str = ""):
    st.markdown(f"""
    <div style="margin: 16px 0 12px 0; animation: fadeInUp .4s ease-out;">
      <h3 style="margin:0; font-size:1.25rem;">{emoji} {title}</h3>
      {f'<p style="color:{COLORS["text_muted"]}; margin:4px 0 0 0; font-size:0.9rem;">{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)
