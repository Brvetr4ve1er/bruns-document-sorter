"""
Settings Page — Phase 3
Ollama configuration, model selection, database tools, app preferences.
"""
import os
import sqlite3
import json
from pathlib import Path

import streamlit as st

from ui.styles import COLORS


def render_settings_page():
    """Full settings page with config, Ollama test, and DB tools."""

    st.markdown("""
    <div data-aos="fade-up" style="margin-bottom: 8px;">
        <p style="color:#8C95B3; margin:0; font-size:0.95rem;">
        Configure the AI model, database paths, and application preferences.
        Changes are saved automatically.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["🤖 AI / Ollama", "🗄️ Database", "🎨 Appearance"])

    # ─────────────────────────────── TAB 1: OLLAMA ────────────────────────────
    with tab1:
        st.markdown("#### Ollama Configuration")
        st.markdown("""
        <div style="background:rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.2);
                    border-radius:12px; padding:16px; margin-bottom:20px; font-size:0.875rem; color:#8C95B3;">
        ℹ️ <b style="color:#E6E9F2;">Ollama</b> is the local AI engine that reads your PDF documents.
        It must be running on this machine before you process files.
        Download it from <a href="https://ollama.ai" style="color:#6366F1;">ollama.ai</a>
        </div>
        """, unsafe_allow_html=True)

        settings = _load_settings()

        col1, col2 = st.columns(2)

        with col1:
            ollama_url = st.text_input(
                "Ollama URL",
                value=settings.get("ollama_url", "http://localhost:11434"),
                key="set_ollama_url",
                help="URL where Ollama is running (default: http://localhost:11434)"
            )

        with col2:
            # Suggest common models
            model_options = [
                "llama3", "llama3.1", "llama3.2", "mistral",
                "mixtral", "qwen2", "gemma2", "phi3", "deepseek-r1"
            ]
            current_model = settings.get("ollama_model", "llama3")
            if current_model not in model_options:
                model_options.insert(0, current_model)

            ollama_model = st.selectbox(
                "Model",
                options=model_options,
                index=model_options.index(current_model),
                key="set_ollama_model",
                help="Ollama model to use for document parsing"
            )

        ollama_timeout = st.slider(
            "Request timeout (seconds)",
            min_value=30, max_value=600,
            value=settings.get("ollama_timeout", 180),
            step=30,
            key="set_ollama_timeout",
            help="How long to wait for Ollama to respond per document"
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🔌 Test Connection", key="test_ollama", use_container_width=True):
                _test_ollama_connection(ollama_url, ollama_model)

        with col2:
            if st.button("💾 Save AI Settings", key="save_ai", use_container_width=True, type="primary"):
                settings["ollama_url"] = ollama_url
                settings["ollama_model"] = ollama_model
                settings["ollama_timeout"] = ollama_timeout
                _save_settings(settings)
                _apply_to_config(settings)
                st.success("✅ AI settings saved!")

        st.markdown("---")
        st.markdown("#### 📦 Pull a Model")
        st.markdown("If you don't have a model yet, run this in your terminal:")
        st.code(f"ollama pull {ollama_model}", language="bash")
        st.markdown("Or pull a specific model:")
        pull_model = st.text_input("Model name to pull", placeholder="e.g. llama3.1", key="pull_model_input")
        if pull_model:
            st.code(f"ollama pull {pull_model}", language="bash")

    # ─────────────────────────────── TAB 2: DATABASE ─────────────────────────
    with tab2:
        st.markdown("#### Database Configuration")

        settings = _load_settings()

        try:
            import config
            db_path = config.DB_PATH
            input_dir = config.INPUT_DIR
        except Exception:
            db_path = "data/logistics.db"
            input_dir = "data/input"

        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Database path", value=db_path, disabled=True, key="db_path_display")
        with col2:
            st.text_input("Input directory", value=input_dir, disabled=True, key="input_dir_display")

        st.markdown("---")
        st.markdown("#### 🗄️ Database Stats")

        try:
            conn = sqlite3.connect(db_path)
            total_shipments = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
            total_containers = conn.execute("SELECT COUNT(*) FROM containers").fetchone()[0]
            db_size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
            conn.close()

            c1, c2, c3 = st.columns(3)
            c1.metric("Shipments", f"{total_shipments:,}")
            c2.metric("Containers", f"{total_containers:,}")
            c3.metric("DB Size", f"{db_size_bytes/1024:.1f} KB")

        except Exception as e:
            st.warning(f"Could not read database: {e}")

        st.markdown("---")
        st.markdown("#### ⚠️ Danger Zone")
        st.markdown("""
        <div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.25);
                    border-radius:12px; padding:16px; margin-bottom:16px; color:#8C95B3; font-size:0.875rem;">
        These actions are <b style="color:#EF4444;">irreversible</b>. Make sure you have exported your data first.
        </div>
        """, unsafe_allow_html=True)

        if st.button("🗑️ Clear ALL data from database", key="clear_db_btn"):
            st.session_state["confirm_clear_db"] = True

        if st.session_state.get("confirm_clear_db"):
            st.error("⚠️ This will delete ALL shipments and containers. Are you sure?")
            ccol1, ccol2 = st.columns(2)
            with ccol1:
                if st.button("✅ Yes, delete everything", key="confirm_clear_yes", type="primary"):
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.execute("DELETE FROM containers")
                        conn.execute("DELETE FROM shipments")
                        conn.commit()
                        conn.close()
                        st.session_state["confirm_clear_db"] = False
                        st.success("✅ Database cleared.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            with ccol2:
                if st.button("❌ Cancel", key="confirm_clear_no"):
                    st.session_state["confirm_clear_db"] = False
                    st.rerun()

    # ─────────────────────────────── TAB 3: APPEARANCE ───────────────────────
    with tab3:
        st.markdown("#### 🎨 Appearance Settings")
        settings = _load_settings()

        col1, col2 = st.columns(2)

        with col1:
            grid_cols = st.select_slider(
                "Dashboard grid columns",
                options=[1, 2, 3, 4],
                value=settings.get("grid_columns", 3),
                key="set_grid_cols",
                help="Number of document card columns on the dashboard"
            )

        with col2:
            animation_speed = st.select_slider(
                "Animation speed",
                options=["Slow (900ms)", "Normal (600ms)", "Fast (350ms)", "Off"],
                value=settings.get("animation_speed", "Normal (600ms)"),
                key="set_anim_speed"
            )

        cards_per_page = st.slider(
            "Max cards shown on dashboard",
            min_value=10, max_value=200,
            value=settings.get("cards_per_page", 50),
            step=10,
            key="set_cards_per_page",
            help="Limit dashboard to show this many cards (improves performance with large datasets)"
        )

        if st.button("💾 Save Appearance", key="save_appearance", type="primary"):
            settings["grid_columns"] = grid_cols
            settings["animation_speed"] = animation_speed
            settings["cards_per_page"] = cards_per_page
            _save_settings(settings)
            st.success("✅ Appearance settings saved! Refresh the dashboard to apply.")

        st.markdown("---")
        st.markdown("#### ℹ️ About")
        st.markdown("""
        <div style="color:#8C95B3; font-size:0.875rem; line-height:1.8;">
        <b style="color:#E6E9F2;">BRUNs Logistics Dashboard</b><br>
        Version 3.0 — Phase 3 Complete<br><br>
        • Local AI processing with Ollama<br>
        • Liquid glass UI with AOS animations<br>
        • PDF → SQLite → Dashboard pipeline<br>
        • No external API calls — fully private<br><br>
        <span style="color:#6366F1;">Built for logistics document management</span>
        </div>
        """, unsafe_allow_html=True)


# ─── Settings persistence helpers ─────────────────────────────────────────────

def _settings_path() -> str:
    base = Path(__file__).parent.parent.parent
    return str(base / "data" / "ui_settings.json")


def _load_settings() -> dict:
    path = _settings_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_settings(settings: dict):
    path = _settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)


def _apply_to_config(settings: dict):
    """Apply settings to the running config module."""
    try:
        import config
        if settings.get("ollama_url"):
            config.OLLAMA_URL = settings["ollama_url"].rstrip("/") + "/api/generate"
        if settings.get("ollama_model"):
            config.OLLAMA_MODEL = settings["ollama_model"]
        if settings.get("ollama_timeout"):
            config.OLLAMA_TIMEOUT = settings["ollama_timeout"]
    except Exception:
        pass


def _test_ollama_connection(url: str, model: str):
    """Test the Ollama connection and show result inline."""
    import requests
    base_url = url.rstrip("/")
    try:
        resp = requests.get(base_url, timeout=5)
        if resp.status_code == 200:
            # Check if model is available
            models_resp = requests.get(f"{base_url}/api/tags", timeout=5)
            if models_resp.ok:
                available = [m["name"].split(":")[0] for m in models_resp.json().get("models", [])]
                if model in available or any(model in m for m in available):
                    st.success(f"✅ Ollama is running! Model **{model}** is available.")
                else:
                    models_str = ", ".join(available[:5]) or "none"
                    st.warning(
                        f"⚠️ Ollama is running but model **{model}** was not found. "
                        f"Available: {models_str}. Run: `ollama pull {model}`"
                    )
            else:
                st.success("✅ Ollama is running!")
        else:
            st.error(f"❌ Ollama returned status {resp.status_code}")
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Cannot connect to Ollama at {url}. Is it running?")
    except Exception as e:
        st.error(f"❌ Error: {e}")
