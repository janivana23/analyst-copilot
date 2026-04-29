"""
pages/dashboard.py — Main analytics dashboard.
"""
import streamlit as st
import plotly.graph_objects as go
from utils.analytics import analyse, health_score, get_runway, break_even, get_benchmarks, get_insights
from utils.sender    import send_email, send_whatsapp
from utils.storage   import save_report


def show():
    df = st.session_state.get("df")

    # ── Empty state ───────────────────────────────────────────────────────────
    if df is None or df.empty:
        st.markdown("""
        <div style='text-align:center;padding:5rem 1rem;'>
          <div style='font-size:3.5rem;'>📊</div>
          <h2 style='color:#1a1a2e;margin-top:1rem;font-size:1.5rem;'>
            Welcome to SME Co-Pilot</h2>
          <p style='color:#6b7280;font-size:0.95rem;max-width:420px;margin:0.5rem auto 0;'>
            Upload a CSV from Xero, QuickBooks, or your bank —<br>
            or click <strong>Load demo data</strong> in the sidebar to see a sample analysis.
          </p>
        </div>""", unsafe_allow_html=True)
        return

    # ── Run analytics ─────────────────────────────────────────────────────────
    biz = st.session_state.get("business", "My Business")
    ind = st.session_state.get("industry", "F&B")
    key = st.session_state.get("openai_key", "")

    s         = analyse(df)
    r_status, r_label = get_runway(s)
    anomalies = s["anomalies"]
    bm_rows   = get_benchmarks(s, ind)
    be        = break_even(s)
    grade, score_val, score_color, score_label = health_score(s, ind)

    with st.spinner("Generating insights..."):
        insights = get_insights(s, anomalies, biz, ind, key)

    # ── Send actions (top of page so result shows before rerun) ───────────────
    col_e, col_w, col_s, _ = st.columns([1, 1, 1, 3])

    with col_e:
        if st.button("📧 Email report", use_container_width=True):
            ok, msg = send_email(
                to=st.session_state.get("email_to", ""),
                smtp_user=st.session_state.get("smtp_user", ""),
                smtp_pass=st.session_state.get("smtp_pass", ""),
                business=biz, s=s, insights=insights,
                anomalies=anomalies, bm_rows=bm_rows, runway_label=r_label,
            )
            st.success(msg) if ok else st.error(msg)

    with col_w:
        if st.button("💬 WhatsApp", use_container_width=True):
            ok, msg = send_whatsapp(
                to_number=st.session_state.get("wa_to", ""),
                sid=st.session_state.get("twilio_sid", ""),
                token=st.session_state.get("twilio_token", ""),
                from_number=st.session_state.get("twilio_from", ""),
                business=biz, s=s, insights=insights,
                anomalies=anomalies, runway_label=r_label,
            )
            st.success(msg) if ok else st.error(msg)

    with col_s:
        if st.button("💾 Save report", use_container_width=True):
            save_report(s["period"], s, insights, anomalies, bm_rows, biz)
            st.success("✓ Saved to Reports history")

    # Quick email recipient override on dashboard
    email_to = st.text_input("Recipient email (for email button above)",
                              placeholder="customer@example.com",
                              label_visibility="collapsed",
                              key="email_to")

    # ── Hero header ───────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="hero">
      <div>
        <h1>{biz}</h1>
        <p>{ind} · {s['period']} · {len(df):,} transactions</p>
      </div>
      <div class="hero-badge">
        <div class="grade" style="color:{score_color};">{grade}</div>
        <div class="grade-label">Health · {score_label}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Revenue",      f"S${s['revenue']:,.0f}",  f"{s['rev_chg']:+.1f}%")
    c2.metric("Expenses",     f"S${s['expenses']:,.0f}", f"{s['exp_chg']:+.1f}%")
    c3.metric("Net profit",   f"S${s['net']:,.0f}")
    c4.metric("Margin",       f"{s['margin']:.1f}%")
    c5.metric("Transactions", f"{s['tx_count']}")

    rp = f"rp-{r_status}"
    st.markdown(f"<p style='font-size:0.8rem;color:#6b7280;margin:4px 0 0;'>"
                f"Cash runway: <span class='rp {rp}'>{r_label}</span></p>",
                unsafe_allow_html=True)

    # ── Main columns ──────────────────────────────────────────────────────────
    left, right = st.columns([3, 2], gap="large")

    with left:
        # Insights
        st.markdown("<div class='sec'>Insights</div>", unsafe_allow_html=True)
        for key_name, label, cls in [
            ("win",   "✅ This month's win",  "g"),
            ("alert", "🚨 Alert",             "r"),
            ("tip",   "💡 Action this week",  "b"),
        ]:
            txt = insights.get(key_name, "")
            if txt:
                badge = (
                    " <span style='background:#fef2f2;color:#991b1b;font-size:0.67rem;"
                    "font-weight:700;padding:1px 6px;border-radius:99px;'>Anomaly</span>"
                    if key_name == "alert" and anomalies else ""
                )
                st.markdown(
                    f"<div class='ins {cls}'>"
                    f"<div class='ins-lbl {cls}'>{label}{badge}</div>"
                    f"<p class='ins-txt'>{txt}</p></div>",
                    unsafe_allow_html=True)

        # Benchmarks
        if bm_rows:
            st.markdown(f"<div class='sec'>Singapore {ind} benchmarks</div>",
                        unsafe_allow_html=True)
            for b in bm_rows:
                st.markdown(
                    f"<div class='bm-row'>"
                    f"<span style='color:#374151;'>{b['name']}</span>"
                    f"<span><strong>{b['val']}</strong> "
                    f"<span class='pill {b['cls']}'>{b['label']}</span> "
                    f"<span style='color:#9ca3af;font-size:0.73rem;'>"
                    f"median {b['median']}</span></span></div>",
                    unsafe_allow_html=True)

        # Anomalies
        if anomalies:
            st.markdown("<div class='sec'>🔴 Expense anomalies</div>",
                        unsafe_allow_html=True)
            for a in anomalies[:3]:
                st.markdown(
                    f"<div class='anom'>"
                    f"<strong style='color:#991b1b;'>{a['category']}</strong> — "
                    f"S${a['current']:,.0f} vs usual S${a['average']:,.0f} "
                    f"<strong style='color:#dc2626;'>(+{a['change_pct']:.0f}%)</strong>"
                    f"</div>", unsafe_allow_html=True)

        # Break-even
        st.markdown("<div class='sec'>Break-even analysis</div>", unsafe_allow_html=True)
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Break-even",      f"S${be['be']:,.0f}")
        b2.metric("Fixed costs",     f"S${be['fixed']:,.0f}")
        b3.metric("Variable costs",  f"S${be['var']:,.0f}")
        b4.metric("Contrib. margin", f"{be['cm']:.1f}%")
        color  = "#16a34a" if be["above"] else "#dc2626"
        symbol = "✓" if be["above"] else "✗"
        st.markdown(
            f"<p style='font-size:0.8rem;color:{color};margin:4px 0;'>"
            f"{symbol} {'Above' if be['above'] else 'Below'} break-even "
            f"by S${abs(be['buffer']):,.0f}</p>",
            unsafe_allow_html=True)

    with right:
        # Revenue trend
        st.markdown("<div class='sec'>Revenue trend</div>", unsafe_allow_html=True)
        if len(s["rev_trend"]) > 1:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=s["trend_labels"], y=s["rev_trend"],
                marker_color=["#22c55e" if v >= s["rev_trend"][0] else "#93c5fd"
                              for v in s["rev_trend"]],
                text=[f"S${v/1000:.0f}k" for v in s["rev_trend"]],
                textposition="outside",
                textfont=dict(size=10, color="#6b7280"),
                name="Revenue",
            ))
            if s["exp_trend"] and len(s["exp_trend"]) == len(s["rev_trend"]):
                fig.add_trace(go.Scatter(
                    x=s["trend_labels"], y=s["exp_trend"],
                    mode="lines+markers", name="Expenses",
                    line=dict(color="#ef4444", width=2, dash="dot"),
                    marker=dict(size=5),
                ))
            fig.update_layout(
                plot_bgcolor="white", paper_bgcolor="white", height=210,
                margin=dict(l=0, r=0, t=12, b=0), bargap=0.3,
                legend=dict(orientation="h", y=1.12, x=0, font=dict(size=10)),
                yaxis=dict(showgrid=True, gridcolor="#f3f4f6", showticklabels=False),
                xaxis=dict(showgrid=False, tickfont=dict(size=10)),
            )
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})

        # Forecast
        fc = s.get("forecast", [])
        if fc and len(fc) >= 3:
            direction = "growing" if fc[0] > s["revenue"] else "declining"
            fc_color  = "#16a34a" if direction == "growing" else "#dc2626"
            st.markdown(
                f"<div class='fc-box'><strong>📈 3-month forecast</strong><br>"
                f"S${fc[0]:,.0f} → S${fc[1]:,.0f} → S${fc[2]:,.0f} "
                f"<span style='color:{fc_color};font-weight:600;'>({direction})</span>"
                f"</div>", unsafe_allow_html=True)

        # Expense breakdown with bars
        st.markdown("<div class='sec'>Expense breakdown</div>", unsafe_allow_html=True)
        top   = s["top_exp"]
        total = sum(top.values()) or 1
        for cat, amt in top.items():
            pct     = amt / total * 100
            is_anom = any(a["category"] == cat for a in anomalies)
            flag    = " 🔴" if is_anom else ""
            bar_col = "#ef4444" if is_anom else "#1a1a2e"
            st.markdown(
                f"<div style='margin-bottom:8px;'>"
                f"<div style='display:flex;justify-content:space-between;"
                f"font-size:0.82rem;margin-bottom:3px;'>"
                f"<span style='color:#374151;'>{cat}{flag}</span>"
                f"<span><strong>S${amt:,.0f}</strong> "
                f"<span style='color:#9ca3af;'>({pct:.0f}%)</span></span></div>"
                f"<div style='background:#f3f4f6;border-radius:99px;height:5px;'>"
                f"<div style='background:{bar_col};width:{int(pct)}%;height:5px;"
                f"border-radius:99px;'></div></div></div>",
                unsafe_allow_html=True)

    # ── Raw data ──────────────────────────────────────────────────────────────
    with st.expander("📄 View transactions"):
        preview = df[["date", "category", "amount"]].copy()
        preview["amount"] = preview["amount"].apply(lambda x: f"S${x:,.2f}")
        preview["date"]   = preview["date"].dt.strftime("%d %b %Y")
        st.dataframe(preview.tail(60), use_container_width=True, hide_index=True)

    # ── Download ──────────────────────────────────────────────────────────────
    st.divider()
    from datetime import datetime
    report = "\n".join([
        f"SME Co-Pilot — {biz} ({ind}) — {s['period']}",
        f"Generated: {datetime.today().strftime('%d %b %Y')}",
        "=" * 55,
        f"Health: {grade} ({score_label})",
        f"Revenue: S${s['revenue']:,.0f} ({s['rev_chg']:+.1f}%)",
        f"Net profit: S${s['net']:,.0f} ({s['margin']:.1f}%)",
        f"Runway: {r_label}",
        f"Break-even: S${be['be']:,.0f} ({'above' if be['above'] else 'below'})",
        "", "INSIGHTS", "-" * 40,
        f"WIN:   {insights.get('win','')}",
        f"ALERT: {insights.get('alert','')}",
        f"TIP:   {insights.get('tip','')}",
    ] + (["", "ANOMALIES"] +
         [f"• {a['category']}: +{a['change_pct']:.0f}%" for a in anomalies]
         if anomalies else []) +
    (["", "BENCHMARKS"] +
     [f"• {b['name']}: {b['val']} — {b['label']}" for b in bm_rows]
     if bm_rows else []))

    col1, _ = st.columns([1, 4])
    with col1:
        st.download_button(
            "📥 Download report", data=report,
            file_name=f"report_{s['period']}.txt", mime="text/plain",
        )
