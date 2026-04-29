"""
SME Co-Pilot — Main entry point
Multi-page app: Dashboard | Reports | Settings

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from utils.styles  import CSS
from utils.storage import load_settings
from utils.analytics import make_demo

st.set_page_config(
    page_title="SME Co-Pilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS, unsafe_allow_html=True)

# Load saved settings into session state once
if "settings_loaded" not in st.session_state:
    cfg = load_settings()
    st.session_state.business  = cfg.get("business", "My Business")
    st.session_state.industry  = cfg.get("industry", "F&B")
    st.session_state.smtp_user = cfg.get("smtp_user", "")
    st.session_state.smtp_pass = cfg.get("smtp_pass", "")
    st.session_state.wa_to     = cfg.get("whatsapp_to", "")
    st.session_state.twilio_sid   = cfg.get("twilio_sid", "")
    st.session_state.twilio_token = cfg.get("twilio_token", "")
    st.session_state.twilio_from  = cfg.get("twilio_from", "")
    st.session_state.openai_key   = cfg.get("openai_key", "")
    st.session_state.settings_loaded = True

# ── Sidebar nav ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 SME Co-Pilot")
    st.caption("AI analytics for Singapore businesses")
    st.divider()

    page = st.radio("Navigation", ["🏠 Dashboard", "📋 Reports", "⚙️ Settings"],
                    label_visibility="collapsed")
    st.divider()

    # Quick data load
    st.markdown("**Data**")
    uploaded = st.file_uploader("Upload CSV", type=["csv", "txt"],
                                label_visibility="collapsed")
    if uploaded:
        from utils.parser import parse
        try:
            st.session_state.df = parse(uploaded)
            st.success(f"✓ {len(st.session_state.df):,} transactions")
            st.rerun()
        except Exception as e:
            st.error(f"Parse error: {e}")

    if st.button("📂 Load demo data", use_container_width=True):
        st.session_state.df = make_demo()
        st.rerun()

    if "df" in st.session_state:
        if st.button("🔄 Clear data", use_container_width=True):
            del st.session_state["df"]
            st.rerun()

    st.divider()
    st.markdown("**How to get your CSV**")
    st.caption("""
**Xero:** Accounting → Reports → Profit & Loss → Export CSV

**QuickBooks:** Reports → P&L → Export → CSV

**Bank:** Download transactions as CSV
""")

# ── Route to pages ────────────────────────────────────────────────────────────
if page == "🏠 Dashboard":
    from pages import dashboard
    dashboard.show()
elif page == "📋 Reports":
    from pages import reports
    reports.show()
elif page == "⚙️ Settings":
    from pages import settings
    settings.show()
