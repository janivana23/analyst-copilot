"""
app.py — SME Co-Pilot Phase 2
Full-featured: CSV upload + Xero/QuickBooks OAuth + rich analytics + email reports.

Run:  streamlit run app.py
Env:  copy .env.example to .env and fill in your keys
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import re
from io import StringIO
from datetime import datetime

from engine   import analytics as eng
from engine   import insights  as ins
from email_report import sender as mailer
import db

# ── optional connectors ───────────────────────────────────────────────────────
try:
    from connectors import xero as xero_conn
    XERO_ENABLED = bool(os.getenv("XERO_CLIENT_ID"))
except ImportError:
    XERO_ENABLED = False

try:
    from connectors import quickbooks as qb_conn
    QB_ENABLED = bool(os.getenv("QB_CLIENT_ID"))
except ImportError:
    QB_ENABLED = False

# ── load .env if present ──────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG + CSS
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="SME Co-Pilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

[data-testid="metric-container"] {
    background: #fff; border: 1px solid #e8e8e8;
    border-radius: 12px; padding: 1.1rem 1.3rem;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.7rem; font-weight: 700; color: #111827;
}

.section-title {
    font-size: 0.72rem; font-weight: 700; color: #9ca3af;
    text-transform: uppercase; letter-spacing: 0.09em;
    margin: 1.8rem 0 0.8rem; padding-bottom: 0.4rem;
    border-bottom: 1px solid #f0f0f0;
}

.insight-card {
    background: #fff; border: 1px solid #e8e8e8;
    border-radius: 12px; padding: 1.1rem 1.4rem; margin-bottom: 0.7rem;
}
.insight-card.win   { border-left: 4px solid #22c55e; }
.insight-card.alert { border-left: 4px solid #ef4444; }
.insight-card.tip   { border-left: 4px solid #3b82f6; }
.insight-label { font-size: 0.68rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.35rem; }
.insight-label.win   { color: #16a34a; }
.insight-label.alert { color: #dc2626; }
.insight-label.tip   { color: #2563eb; }
.insight-text { font-size: 0.9rem; color: #374151; line-height: 1.65; margin: 0; }

.bm-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 0; border-bottom: 1px solid #f3f4f6; font-size: 0.85rem;
}
.bm-pill {
    display: inline-block; font-size: 0.7rem; font-weight: 700;
    padding: 2px 9px; border-radius: 99px;
}
.pill-green  { background: #dcfce7; color: #166534; }
.pill-teal   { background: #e0f2fe; color: #0369a1; }
.pill-amber  { background: #fef3c7; color: #92400e; }
.pill-red    { background: #fef2f2; color: #991b1b; }

.connect-card {
    background: #f9fafb; border: 1px dashed #d1d5db;
    border-radius: 12px; padding: 1.1rem 1.3rem; margin-bottom: 0.6rem;
}
.connect-card.connected {
    border-color: #86efac; background: #f0fdf4;
}
.stButton > button {
    background: #1a1a2e; color: #fff; border: none;
    border-radius: 8px; font-weight: 500; width: 100%;
}
.stButton > button:hover { background: #16213e; }

.anomaly-box {
    background: #fef2f2; border: 1px solid #fecaca;
    border-radius: 8px; padding: 10px 14px; margin-bottom: 7px;
    font-size: 0.86rem;
}
.runway-pill {
    display: inline-block; padding: 3px 14px; border-radius: 99px;
    font-size: 0.8rem; font-weight: 700;
}
.rp-green  { background: #dcfce7; color: #166534; }
.rp-amber  { background: #fef3c7; color: #92400e; }
.rp-red    { background: #fef2f2; color: #991b1b; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  CSV PARSING  (Phase 1 logic, kept for fallback + manual upload)
# ══════════════════════════════════════════════════════════════════════════════

def parse_amount(val) -> float:
    if pd.isna(val): return 0.0
    s = str(val).strip().replace(",", "").replace("$", "").replace("S$", "")
    if s.startswith("(") and s.endswith(")"): return -float(s[1:-1])
    try: return float(s)
    except: return 0.0


def load_csv(uploaded_file) -> pd.DataFrame:
    content = uploaded_file.read().decode("utf-8", errors="ignore")
    lines   = content.splitlines()
    start   = next((i for i, l in enumerate(lines)
                    if re.search(r"date|Date|DATE", l)), 0)
    df = pd.read_csv(StringIO("\n".join(lines[start:])), dtype=str)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    cols = df.columns.tolist()
    date_col   = next((c for c in cols if "date"   in c), cols[0])
    desc_col   = next((c for c in cols if any(x in c for x in ("desc","name","memo","narr"))), None)
    cat_col    = next((c for c in cols if any(x in c for x in ("account","cat","type"))), None)
    amount_col = next((c for c in cols if any(x in c for x in ("amount","value","debit","net"))), None)

    out = pd.DataFrame()
    out["date"]        = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
    out["description"] = df[desc_col].fillna("") if desc_col else ""
    out["category"]    = df[cat_col].fillna("Uncategorised") if cat_col else "Uncategorised"
    out["amount"]      = df[amount_col].apply(parse_amount) if amount_col else 0.0
    out["type"]        = np.where(out["amount"] >= 0, "income", "expense")
    out["amount_abs"]  = out["amount"].abs()
    out = out.dropna(subset=["date"])
    out = out[out["amount_abs"] > 0]
    out["month"] = out["date"].dt.to_period("M")
    return out.sort_values("date")


def make_demo_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    today = datetime.today()
    rows  = []
    for m in range(6, -1, -1):
        ms   = (today.replace(day=1) - pd.DateOffset(months=m))
        base = 45000 + m * -800 + rng.normal(0, 2000)
        for _ in range(rng.integers(15, 22)):
            rows.append({"date": ms + pd.DateOffset(days=int(rng.integers(0, 28))),
                         "description": "Sales", "category": "Revenue",
                         "amount": round(float(rng.uniform(800, 3200)), 2)})
        rows.append({"date": ms, "description": "Rent",
                     "category": "Rent", "amount": -8500.0})
        rows.append({"date": ms + pd.DateOffset(days=28), "description": "Salaries",
                     "category": "Staff costs",
                     "amount": round(-float(rng.uniform(18000, 22000)), 2)})
        ing_base = 9000 if m > 0 else 13800   # anomaly in latest month
        rows.append({"date": ms + pd.DateOffset(days=5), "description": "Ingredients",
                     "category": "Ingredients & supplies",
                     "amount": round(-float(rng.uniform(ing_base * 0.9, ing_base * 1.1)), 2)})
        rows.append({"date": ms + pd.DateOffset(days=14), "description": "PUB",
                     "category": "Utilities",
                     "amount": round(-float(rng.uniform(1200, 1800)), 2)})
        if rng.random() > 0.4:
            rows.append({"date": ms + pd.DateOffset(days=int(rng.integers(1, 20))),
                         "description": "Ads", "category": "Marketing",
                         "amount": round(-float(rng.uniform(400, 1400)), 2)})

    df = pd.DataFrame(rows)
    df["amount_abs"] = df["amount"].abs()
    df["type"]       = np.where(df["amount"] >= 0, "income", "expense")
    df["date"]       = pd.to_datetime(df["date"])
    df["month"]      = df["date"].dt.to_period("M")
    return df.sort_values("date")


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### SME Co-Pilot")
    st.markdown(
        "<p style='font-size:0.8rem;color:#6b7280;margin-top:-8px;'>"
        "AI analytics for Singapore businesses</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    business_name = st.text_input("Business name", value="My Business",
                                  placeholder="e.g. Kim's Café")
    email_addr    = st.text_input("Your email", placeholder="you@example.com",
                                  help="Used to send your weekly report")
    industry      = st.selectbox("Industry", ["F&B", "Retail", "Services", "General"])
    api_key       = st.text_input("OpenAI API key (optional)", type="password",
                                  placeholder="sk-...",
                                  help="Enables AI-powered insights. Leave blank for rule-based.")

    st.divider()
    st.markdown("**Connect your accounts**")

    # Xero connect button
    xero_connected = email_addr and xero_conn.is_connected(email_addr) if XERO_ENABLED else False
    xero_class     = "connect-card connected" if xero_connected else "connect-card"
    xero_status    = "✓ Connected" if xero_connected else "Not connected"
    st.markdown(
        f"<div class='{xero_class}'>"
        f"<strong style='font-size:0.85rem;'>Xero</strong> "
        f"<span style='font-size:0.75rem;color:#6b7280;float:right;'>{xero_status}</span>"
        f"</div>", unsafe_allow_html=True,
    )
    if XERO_ENABLED and not xero_connected:
        if st.button("Connect Xero", key="xero_btn"):
            import secrets
            state = secrets.token_hex(8)
            st.session_state["xero_state"] = state
            auth_url = xero_conn.get_auth_url(state)
            st.markdown(f"[Click here to authorise Xero]({auth_url})")

    # QuickBooks connect button
    qb_connected = email_addr and qb_conn.is_connected(email_addr) if QB_ENABLED else False
    qb_class     = "connect-card connected" if qb_connected else "connect-card"
    qb_status    = "✓ Connected" if qb_connected else "Not connected"
    st.markdown(
        f"<div class='{qb_class}'>"
        f"<strong style='font-size:0.85rem;'>QuickBooks</strong> "
        f"<span style='font-size:0.75rem;color:#6b7280;float:right;'>{qb_status}</span>"
        f"</div>", unsafe_allow_html=True,
    )
    if QB_ENABLED and not qb_connected:
        if st.button("Connect QuickBooks", key="qb_btn"):
            import secrets
            auth_url = qb_conn.get_auth_url(secrets.token_hex(8))
            st.markdown(f"[Click here to authorise QuickBooks]({auth_url})")

    if not XERO_ENABLED and not QB_ENABLED:
        st.caption("Add XERO_CLIENT_ID or QB_CLIENT_ID to .env to enable direct connections.")

    st.divider()

    send_test = st.button("Send test email report", disabled=not email_addr)
    if st.button("Try with demo data"):
        st.session_state["use_demo"] = True

    st.markdown(
        "<p style='font-size:0.72rem;color:#9ca3af;margin-top:1rem;'>"
        "Phase 2 MVP · Data stays in your session</p>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  HANDLE OAUTH CALLBACKS
#  Streamlit ignores URL paths — it only reads query params.
#  Fix: set redirect URI to http://localhost:8501 (no path) in Xero dev portal
#  AND in your .env XERO_REDIRECT_URI=http://localhost:8501
#  Xero will redirect to http://localhost:8501?code=xxx&state=xxx
#  which Streamlit CAN read via st.query_params.
# ══════════════════════════════════════════════════════════════════════════════

params = st.query_params

# Auto-detect Xero callback: has "code" param and no "realmId" (which is QB)
if "code" in params:
    code     = params["code"]
    state    = params.get("state", "")
    realm_id = params.get("realmId", "")

    # Determine provider: QB always sends realmId, Xero never does
    is_xero = not realm_id
    is_qb   = bool(realm_id)

    if is_xero and XERO_ENABLED:
        if not email_addr:
            st.warning("⚠️ Enter your email in the sidebar, then paste this URL in your browser again.")
            st.code(f"Code received: {code[:20]}...  (paste your email first, then refresh)")
        else:
            with st.spinner("Connecting Xero..."):
                try:
                    xero_conn.exchange_code(code, email_addr)
                    db.upsert_user(email_addr, business_name)
                    st.success("✅ Xero connected! Scroll down to see your data.")
                    st.query_params.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Xero connection failed: {e}")
                    st.info("Common fix: make sure XERO_REDIRECT_URI in .env exactly matches "
                            "the redirect URI in your Xero developer app settings.")

    elif is_qb and QB_ENABLED:
        if email_addr:
            with st.spinner("Connecting QuickBooks..."):
                try:
                    qb_conn.exchange_code(code, realm_id, email_addr)
                    db.upsert_user(email_addr, business_name)
                    st.success("✅ QuickBooks connected!")
                    st.query_params.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"QuickBooks connection failed: {e}")

# ── Manual code entry fallback ────────────────────────────────────────────────
# If the redirect went to /callback/xero (wrong URL) and lost the code,
# the user can paste the full redirect URL here to complete the connection.
if XERO_ENABLED and not (email_addr and xero_conn.is_connected(email_addr)):
    with st.sidebar:
        with st.expander("Paste redirect URL (if connect failed)"):
            pasted = st.text_input("Paste the full URL you were redirected to",
                                   placeholder="http://localhost:8501?code=...")
            if pasted and email_addr:
                import urllib.parse as urlparse
                try:
                    parsed   = urlparse.urlparse(pasted)
                    qp       = dict(urlparse.parse_qsl(parsed.query))
                    man_code = qp.get("code", "")
                    if man_code:
                        with st.spinner("Connecting..."):
                            xero_conn.exchange_code(man_code, email_addr)
                            db.upsert_user(email_addr, business_name)
                            st.success("✅ Xero connected!")
                            st.rerun()
                    else:
                        st.error("No code found in that URL. Copy the full URL from your browser.")
                except Exception as e:
                    st.error(f"Failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

df = None
data_source = None

# 1. Try Xero direct connection
if email_addr and XERO_ENABLED and xero_connected:
    with st.spinner("Fetching data from Xero..."):
        try:
            from datetime import date
            today = date.today()
            pl    = xero_conn.get_profit_and_loss(
                email_addr,
                (today.replace(day=1) - pd.DateOffset(months=6)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d"),
            )
            parsed = xero_conn.parse_xero_pl(pl)
            # Convert API response to DataFrame (simplified for MVP)
            df = _api_parsed_to_df(parsed, str(today)[:7])
            data_source = "Xero"
        except Exception as e:
            st.warning(f"Xero data fetch failed: {e}. Upload a CSV instead.")

# 2. Try QuickBooks direct connection
if df is None and email_addr and QB_ENABLED and qb_connected:
    with st.spinner("Fetching data from QuickBooks..."):
        try:
            from datetime import date
            today = date.today()
            pl    = qb_conn.get_profit_and_loss(
                email_addr,
                (today.replace(day=1) - pd.DateOffset(months=6)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d"),
            )
            parsed = qb_conn.parse_qb_pl(pl)
            df = _api_parsed_to_df(parsed, str(today)[:7])
            data_source = "QuickBooks"
        except Exception as e:
            st.warning(f"QuickBooks data fetch failed: {e}. Upload a CSV instead.")

# 3. Demo data
if st.session_state.get("use_demo"):
    df = make_demo_df()
    data_source = "Demo (Kim's Café)"
    if "use_demo" in st.session_state:
        del st.session_state["use_demo"]


def _api_parsed_to_df(parsed, period):
    """Shim: convert API P&L dict to normalised DataFrame."""
    rows = []
    period_dt = pd.Period(period, freq="M")
    rows.append({"date": period_dt.to_timestamp(), "description": "Revenue",
                 "category": "Revenue", "amount": parsed.get("revenue", 0),
                 "amount_abs": parsed.get("revenue", 0), "type": "income", "month": period_dt})
    for cat, amt in parsed.get("expenses", {}).items():
        rows.append({"date": period_dt.to_timestamp(), "description": cat,
                     "category": cat, "amount": -abs(amt),
                     "amount_abs": abs(amt), "type": "expense", "month": period_dt})
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
#  FILE UPLOAD (shown when no direct connection)
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(f"## {business_name} — Financial Co-Pilot")
if data_source:
    st.markdown(
        f"<p style='color:#6b7280;margin-top:-10px;font-size:0.85rem;'>"
        f"Data source: <strong>{data_source}</strong></p>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<p style='color:#6b7280;margin-top:-10px;font-size:0.85rem;'>"
        "Upload your accounting CSV or connect Xero/QuickBooks in the sidebar</p>",
        unsafe_allow_html=True,
    )

if df is None:
    uploaded = st.file_uploader(
        "Upload CSV", type=["csv", "txt"], label_visibility="collapsed"
    )
    if uploaded:
        with st.spinner("Parsing..."):
            try:
                df = load_csv(uploaded)
                data_source = "CSV upload"
                st.success(f"Loaded {len(df):,} transactions.")
            except Exception as e:
                st.error(f"Could not parse file: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

if df is not None and not df.empty:

    summary    = eng.compute_summary(df)
    anomalies  = eng.detect_anomalies(df)
    forecast   = eng.forecast_revenue(summary.get("revenue_trend", []))
    runway     = eng.compute_runway(summary)
    benchmarks = eng.benchmark(summary, industry)

    if not summary:
        st.warning("Not enough data. Check your CSV has date and amount columns.")
        st.stop()

    with st.spinner("Generating insights..."):
        insights_dict = ins.generate(
            summary=summary, anomalies=anomalies, benchmarks=benchmarks,
            forecast=forecast, runway=runway, business_name=business_name,
            industry=industry, api_key=api_key,
        )

    # ── KPI ROW ──────────────────────────────────────────────────────────────
    st.markdown("<div class='section-title'>This month at a glance</div>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Revenue",     f"S${summary['revenue']:,.0f}",    f"{summary['revenue_change']:+.1f}%")
    c2.metric("Expenses",    f"S${summary['expenses']:,.0f}",   f"{summary['expenses_change']:+.1f}%")
    c3.metric("Net profit",  f"S${summary['net_profit']:,.0f}", f"{summary['profit_change']:+.1f}%")
    c4.metric("Margin",      f"{summary['profit_margin']:.1f}%")
    c5.metric("Transactions",f"{summary['transaction_count']}")

    rp_cls = f"rp-{runway['status']}"
    st.markdown(
        f"<p style='font-size:0.82rem;color:#6b7280;margin:2px 0 0;'>"
        f"Cash runway: <span class='runway-pill {rp_cls}'>{runway['label']}</span>"
        f"&nbsp;&nbsp;<span style='color:#9ca3af;'>{runway.get('advice','')}</span></p>",
        unsafe_allow_html=True,
    )

    # ── MAIN CONTENT COLUMNS ─────────────────────────────────────────────────
    left, right = st.columns([3, 2], gap="large")

    # ── LEFT: Insights ───────────────────────────────────────────────────────
    with left:
        st.markdown("<div class='section-title'>AI insights</div>", unsafe_allow_html=True)
        for key, label, cls in [
            ("win",   "This month's win",  "win"),
            ("alert", "Alert",             "alert"),
            ("tip",   "Action this week",  "tip"),
        ]:
            if insights_dict.get(key):
                anom_tag = (
                    "<span style='background:#fef2f2;color:#991b1b;font-size:0.68rem;"
                    "font-weight:700;padding:1px 7px;border-radius:99px;margin-left:6px;'>"
                    "Anomaly detected</span>"
                    if key == "alert" and anomalies else ""
                )
                st.markdown(
                    f"<div class='insight-card {cls}'>"
                    f"<div class='insight-label {cls}'>{label}{anom_tag}</div>"
                    f"<p class='insight-text'>{insights_dict[key]}</p>"
                    f"</div>", unsafe_allow_html=True,
                )

        # Benchmark table
        if benchmarks:
            st.markdown("<div class='section-title'>Industry benchmarks ({industry})</div>".replace("{industry}", industry), unsafe_allow_html=True)
            for b in benchmarks:
                pill_cls = f"pill-{b.get('colour','teal')}"
                st.markdown(
                    f"<div class='bm-row'>"
                    f"<span style='color:#374151;'>{b['label']}</span>"
                    f"<span>"
                    f"<strong>{b['value']}</strong> "
                    f"<span class='bm-pill {pill_cls}'>{b['rating']}</span> "
                    f"<span style='color:#9ca3af;font-size:0.75rem;'>median {b['median']}</span>"
                    f"</span></div>", unsafe_allow_html=True,
                )

        # Anomalies
        if anomalies:
            st.markdown("<div class='section-title'>Expense anomalies</div>", unsafe_allow_html=True)
            for a in anomalies[:4]:
                sev_col = "#dc2626" if a["severity"] == "high" else "#d97706"
                st.markdown(
                    f"<div class='anomaly-box'>"
                    f"<strong style='color:{sev_col};'>{a['category']}</strong> — "
                    f"S${a['current']:,.0f} this month vs usual S${a['average']:,.0f} "
                    f"<span style='color:{sev_col};font-weight:700;'>(+{a['change_pct']:.0f}%)</span>"
                    f"</div>", unsafe_allow_html=True,
                )

    # ── RIGHT: Charts + Expenses ─────────────────────────────────────────────
    with right:
        # Revenue trend chart
        st.markdown("<div class='section-title'>Revenue trend</div>", unsafe_allow_html=True)
        trend_vals   = summary.get("revenue_trend", [])
        trend_labels = summary.get("trend_labels", [f"M-{i}" for i in range(len(trend_vals), 0, -1)])
        exp_trend    = summary.get("expense_trend", [])

        if len(trend_vals) > 1:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Revenue", x=trend_labels, y=trend_vals,
                marker_color=["#22c55e" if v >= trend_vals[0] else "#93c5fd" for v in trend_vals],
                text=[f"S${v/1000:.0f}k" for v in trend_vals],
                textposition="outside", textfont=dict(size=10, color="#6b7280"),
            ))
            if exp_trend and len(exp_trend) == len(trend_vals):
                fig.add_trace(go.Scatter(
                    name="Expenses", x=trend_labels, y=exp_trend,
                    mode="lines+markers", line=dict(color="#ef4444", width=2, dash="dot"),
                    marker=dict(size=5),
                ))
            fig.update_layout(
                plot_bgcolor="white", paper_bgcolor="white", height=200,
                margin=dict(l=0, r=0, t=10, b=0), showlegend=True,
                legend=dict(orientation="h", y=1.1, x=0, font=dict(size=10)),
                yaxis=dict(showgrid=True, gridcolor="#f3f4f6", showticklabels=False),
                xaxis=dict(showgrid=False, tickfont=dict(size=10)),
                bargap=0.3,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Forecast
        fc_list = forecast.get("forecasts", [])
        if fc_list:
            st.markdown(
                f"<div style='background:#f0f9ff;border-radius:8px;padding:10px 14px;"
                f"font-size:0.82rem;color:#0c4a6e;margin-bottom:0.5rem;'>"
                f"<strong>Forecast</strong> (next 3 months): "
                f"S${fc_list[0]:,.0f} → S${fc_list[1]:,.0f} → S${fc_list[2]:,.0f}"
                f"<br><span style='color:#6b7280;'>{forecast.get('trend','').capitalize()} · "
                f"{forecast.get('confidence','?')} confidence</span></div>",
                unsafe_allow_html=True,
            )

        # Expense donut
        st.markdown("<div class='section-title'>Expense breakdown</div>", unsafe_allow_html=True)
        top_exp = summary.get("top_expenses", {})
        if top_exp:
            cats = list(top_exp.keys())[:6]
            vals = [top_exp[c] for c in cats]
            colours = ["#1a1a2e","#374151","#6b7280","#9ca3af","#d1d5db","#f3f4f6"]
            fig2 = go.Figure(go.Pie(
                labels=cats, values=vals, hole=0.55,
                marker=dict(colors=colours[:len(cats)]),
                textinfo="percent", textfont=dict(size=10),
                hovertemplate="%{label}<br>S$%{value:,.0f}<extra></extra>",
            ))
            fig2.update_layout(
                plot_bgcolor="white", paper_bgcolor="white", height=220,
                margin=dict(l=0, r=0, t=0, b=0), showlegend=True,
                legend=dict(font=dict(size=10), orientation="v",
                            x=1.0, y=0.5, xanchor="left"),
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        # Category trends (sparklines)
        cat_trends = summary.get("category_trends", {})
        if cat_trends:
            st.markdown("<div class='section-title'>Category trends (4 months)</div>", unsafe_allow_html=True)
            for cat, vals in list(cat_trends.items())[:4]:
                if len(vals) < 2:
                    continue
                direction = "↑" if vals[-1] > vals[-2] else "↓"
                colour    = "#dc2626" if vals[-1] > vals[-2] else "#16a34a"
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"font-size:0.82rem;padding:5px 0;border-bottom:1px solid #f9f9f9;'>"
                    f"<span style='color:#374151;'>{cat}</span>"
                    f"<span style='color:{colour};font-weight:600;'>"
                    f"{direction} S${vals[-1]:,.0f}</span></div>",
                    unsafe_allow_html=True,
                )

    # ── BREAK-EVEN ───────────────────────────────────────────────────────────
    be = eng.break_even(summary)
    st.markdown("<div class='section-title'>Break-even analysis</div>", unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Break-even revenue", f"S${be['break_even_revenue']:,.0f}")
    b2.metric("Fixed costs",         f"S${be['fixed_costs']:,.0f}")
    b3.metric("Variable costs",      f"S${be['variable_costs']:,.0f}")
    b4.metric("Contribution margin", f"{be['contribution_margin']:.1f}%")
    if be["above_break_even"]:
        st.markdown(
            f"<p style='font-size:0.82rem;color:#16a34a;'>"
            f"✓ Above break-even by S${be['buffer']:,.0f}</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<p style='font-size:0.82rem;color:#dc2626;'>"
            f"✗ Below break-even by S${abs(be['buffer']):,.0f} — revenue needs to reach "
            f"S${be['break_even_revenue']:,.0f} to cover all costs.</p>",
            unsafe_allow_html=True,
        )

    # ── RAW DATA ─────────────────────────────────────────────────────────────
    with st.expander("View transactions"):
        preview = df[["date","description","category","amount"]].copy()
        preview["amount"] = preview["amount"].apply(lambda x: f"S${x:,.2f}")
        preview["date"]   = preview["date"].dt.strftime("%d %b %Y")
        st.dataframe(preview.tail(60), use_container_width=True, hide_index=True)

    # ── EMAIL TEST ────────────────────────────────────────────────────────────
    if send_test and email_addr:
        with st.spinner(f"Sending report to {email_addr}..."):
            ok = mailer.send_weekly_report(
                to_email=email_addr, business_name=business_name,
                summary=summary, insights=insights_dict, anomalies=anomalies,
                runway=runway, forecast=forecast, benchmarks=benchmarks,
            )
        if ok:
            st.success(f"Report sent to {email_addr}!")
        else:
            st.warning("Sending failed. Check your email provider settings in .env")

    # ── DOWNLOAD ──────────────────────────────────────────────────────────────
    st.divider()
    html_report = mailer.render_html(
        business_name, summary, insights_dict, anomalies, runway, forecast, benchmarks
    )
    plain_report = mailer.render_plain(business_name, summary, insights_dict, anomalies)

    col_a, col_b, _ = st.columns([1, 1, 3])
    with col_a:
        st.download_button("Download HTML report", data=html_report,
                           file_name=f"report_{summary['period']}.html",
                           mime="text/html")
    with col_b:
        st.download_button("Download text report", data=plain_report,
                           file_name=f"report_{summary['period']}.txt",
                           mime="text/plain")

else:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """<div style='text-align:center;padding:3rem 1rem;'>
        <div style='font-size:2.5rem;margin-bottom:1rem;'>📂</div>
        <p style='font-size:1rem;color:#374151;font-weight:500;'>
          Upload a CSV or connect Xero/QuickBooks to get started</p>
        <p style='font-size:0.85rem;color:#9ca3af;'>
          Or click <strong>Try with demo data</strong> in the sidebar</p>
        </div>""", unsafe_allow_html=True,
    )
