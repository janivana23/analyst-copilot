"""
pages/reports.py — Report history view.
"""
import streamlit as st
from utils.storage import load_history, clear_history


def show():
    st.markdown("<div class='hero'><div><h1>📋 Reports</h1>"
                "<p>Your saved financial reports</p></div></div>",
                unsafe_allow_html=True)

    history = load_history()

    if not history:
        st.markdown("""
        <div style='text-align:center;padding:4rem 1rem;'>
          <div style='font-size:2.5rem;'>📂</div>
          <h3 style='color:#374151;margin-top:1rem;'>No reports yet</h3>
          <p style='color:#6b7280;'>
            Go to the Dashboard, analyse your data, and click
            <strong>Save report</strong> to store it here.
          </p>
        </div>""", unsafe_allow_html=True)
        return

    # Summary stats
    c1, c2, c3 = st.columns(3)
    avg_margin  = sum(r.get("margin", 0) for r in history) / len(history)
    avg_rev_chg = sum(r.get("rev_chg", 0) for r in history) / len(history)
    c1.metric("Reports saved",    len(history))
    c2.metric("Avg profit margin", f"{avg_margin:.1f}%")
    c3.metric("Avg revenue growth", f"{avg_rev_chg:+.1f}%")

    st.markdown("<div class='sec'>Report history</div>", unsafe_allow_html=True)

    for r in history:
        rev_color  = "#16a34a" if r.get("rev_chg", 0) >= 0 else "#dc2626"
        rev_arrow  = "↑" if r.get("rev_chg", 0) >= 0 else "↓"
        net_color  = "#16a34a" if r.get("net", 0) >= 0 else "#dc2626"
        anom_count = len(r.get("anomalies", []))

        with st.expander(
            f"📅 {r.get('period','')} — {r.get('business','')} "
            f"· S${r.get('revenue',0):,.0f} revenue "
            f"· {r.get('margin',0):.1f}% margin"
        ):
            # KPIs
            ca, cb, cc, cd = st.columns(4)
            ca.metric("Revenue",    f"S${r.get('revenue',0):,.0f}",
                      f"{r.get('rev_chg',0):+.1f}%")
            cb.metric("Net profit", f"S${r.get('net',0):,.0f}")
            cc.metric("Margin",     f"{r.get('margin',0):.1f}%")
            cd.metric("Anomalies",  anom_count)

            # Insights
            ins = r.get("insights", {})
            for key, label, cls in [
                ("win",   "✅ Win",   "g"),
                ("alert", "🚨 Alert", "r"),
                ("tip",   "💡 Tip",   "b"),
            ]:
                if ins.get(key):
                    st.markdown(
                        f"<div class='ins {cls}'>"
                        f"<div class='ins-lbl {cls}'>{label}</div>"
                        f"<p class='ins-txt'>{ins[key]}</p></div>",
                        unsafe_allow_html=True)

            # Anomalies
            if r.get("anomalies"):
                st.markdown("**Anomalies flagged:**")
                for a in r["anomalies"]:
                    st.markdown(
                        f"<div class='anom'>"
                        f"<strong style='color:#991b1b;'>{a['category']}</strong> — "
                        f"+{a['change_pct']:.0f}% above usual</div>",
                        unsafe_allow_html=True)

            # Benchmarks
            if r.get("benchmarks"):
                st.markdown("**Benchmarks:**")
                for b in r["benchmarks"]:
                    st.markdown(
                        f"<div class='bm-row'>"
                        f"<span>{b['name']}</span>"
                        f"<span><strong>{b['val']}</strong> "
                        f"<span class='pill {b['cls']}'>{b['label']}</span></span>"
                        f"</div>", unsafe_allow_html=True)

            st.caption(f"Generated: {r.get('generated','')}")

    st.divider()
    if st.button("🗑 Clear all reports", type="secondary"):
        clear_history()
        st.success("History cleared.")
        st.rerun()
