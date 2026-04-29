"""
utils/sender.py — Beautiful HTML email via Gmail + WhatsApp via Twilio.
"""
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ══════════════════════════════════════════════════════════════════════════════
#  EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def send_email(to: str, smtp_user: str, smtp_pass: str,
               business: str, s: dict, insights: dict,
               anomalies: list, bm_rows: list, runway_label: str) -> tuple:

    if not to:        return False, "Enter recipient email."
    if not smtp_user: return False, "Enter your Gmail address."
    if not smtp_pass: return False, "Enter your Gmail app password."

    subject = f"[SME Co-Pilot] {business} — {s['period']} financial report"
    html    = _build_html(business, s, insights, anomalies, bm_rows, runway_label)
    plain   = _build_plain(business, s, insights, anomalies)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = to
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        clean = smtp_pass.replace(" ", "")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(smtp_user, clean)
            srv.sendmail(smtp_user, [to], msg.as_string())
        return True, f"✓ Report sent to {to}"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail auth failed — use an App Password from myaccount.google.com/apppasswords"
    except Exception as e:
        return False, f"Send failed: {e}"


def _build_plain(biz, s, insights, anomalies) -> str:
    lines = [
        f"SME Co-Pilot — {biz} — {s['period']}",
        f"Generated: {datetime.today().strftime('%d %b %Y')}",
        "=" * 50,
        f"Revenue:    S${s['revenue']:,.0f} ({s['rev_chg']:+.1f}%)",
        f"Expenses:   S${s['expenses']:,.0f}",
        f"Net profit: S${s['net']:,.0f} ({s['margin']:.1f}% margin)",
        "",
        f"WIN:   {insights.get('win', '')}",
        f"ALERT: {insights.get('alert', '')}",
        f"TIP:   {insights.get('tip', '')}",
    ]
    if anomalies:
        lines += ["", "ANOMALIES:"] + [f"• {a['category']}: +{a['change_pct']:.0f}%" for a in anomalies]
    return "\n".join(lines)


def _build_html(biz, s, insights, anomalies, bm_rows, runway_label) -> str:
    date_str  = datetime.today().strftime("%d %B %Y")
    rev_color = "#16a34a" if s["rev_chg"] >= 0 else "#dc2626"
    rev_arrow = "↑" if s["rev_chg"] >= 0 else "↓"
    net_color = "#16a34a" if s["net"] >= 0 else "#dc2626"

    # Expense rows
    exp_rows = "".join(
        f'<tr>'
        f'<td style="padding:8px 0;font-size:13px;color:#374151;border-bottom:1px solid #f3f4f6;">{cat}</td>'
        f'<td style="padding:8px 0;text-align:right;font-weight:600;font-size:13px;'
        f'border-bottom:1px solid #f3f4f6;color:#111827;">S${amt:,.0f}</td>'
        f'</tr>'
        for cat, amt in list(s.get("top_exp", {}).items())[:5]
    )

    # Anomaly blocks
    anom_html = ""
    if anomalies:
        items = "".join(
            f'<div style="background:#fef2f2;border-left:4px solid #ef4444;border-radius:0 8px 8px 0;'
            f'padding:10px 14px;margin-bottom:8px;">'
            f'<strong style="color:#991b1b;">{a["category"]}</strong> — '
            f'S${a["current"]:,.0f} this month vs usual S${a["average"]:,.0f} '
            f'<strong style="color:#dc2626;">(+{a["change_pct"]:.0f}%)</strong></div>'
            for a in anomalies[:3]
        )
        anom_html = (
            f'<h3 style="font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin:20px 0 10px;">Anomalies flagged</h3>{items}'
        )

    # Benchmark rows
    bm_html = ""
    if bm_rows:
        pill_styles = {
            "pg": ("background:#dcfce7;color:#166534;"),
            "pt": ("background:#e0f2fe;color:#0369a1;"),
            "pa": ("background:#fef3c7;color:#92400e;"),
            "pr": ("background:#fef2f2;color:#991b1b;"),
        }
        rows = "".join(
            f'<tr>'
            f'<td style="padding:7px 0;font-size:12px;color:#374151;border-bottom:1px solid #f9f9f9;">{b["name"]}</td>'
            f'<td style="padding:7px 0;text-align:center;font-weight:600;font-size:12px;border-bottom:1px solid #f9f9f9;">{b["val"]}</td>'
            f'<td style="padding:7px 0;text-align:center;border-bottom:1px solid #f9f9f9;">'
            f'<span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;'
            f'{pill_styles.get(b["cls"], pill_styles["pt"])}">{b["label"]}</span></td>'
            f'<td style="padding:7px 0;text-align:right;font-size:11px;color:#9ca3af;border-bottom:1px solid #f9f9f9;">median {b["median"]}</td>'
            f'</tr>'
            for b in bm_rows
        )
        bm_html = (
            f'<h3 style="font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;'
            f'letter-spacing:0.08em;margin:20px 0 10px;">Industry benchmarks</h3>'
            f'<table style="width:100%;border-collapse:collapse;">{rows}</table>'
        )

    # Forecast
    fc = s.get("forecast", [])
    fc_html = ""
    if len(fc) >= 3:
        direction = "growing" if fc[0] > s["revenue"] else "declining"
        fc_color  = "#16a34a" if direction == "growing" else "#dc2626"
        fc_html = (
            f'<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;'
            f'padding:14px 16px;margin:16px 0;">'
            f'<p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#0369a1;'
            f'text-transform:uppercase;letter-spacing:0.06em;">3-month revenue forecast</p>'
            f'<p style="margin:0;font-size:14px;color:#0c4a6e;">'
            f'S${fc[0]:,.0f} → S${fc[1]:,.0f} → S${fc[2]:,.0f} '
            f'<span style="color:{fc_color};font-weight:700;">({direction})</span></p></div>'
        )

    def insight_block(label, text, accent, bg, fg):
        if not text:
            return ""
        return (
            f'<div style="border-left:4px solid {accent};background:{bg};'
            f'border-radius:0 10px 10px 0;padding:14px 16px;margin-bottom:10px;">'
            f'<p style="margin:0 0 4px;font-size:10px;font-weight:700;color:{fg};'
            f'text-transform:uppercase;letter-spacing:0.08em;">{label}</p>'
            f'<p style="margin:0;font-size:13px;color:#374151;line-height:1.65;">{text}</p></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>SME Co-Pilot Report</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0"
  style="background:#ffffff;border-radius:20px;overflow:hidden;
  border:1px solid #e2e8f0;box-shadow:0 4px 24px rgba(0,0,0,0.06);">

<!-- Header -->
<tr><td style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 60%,#0f3460 100%);
  padding:28px 32px;">
  <p style="margin:0 0 4px;color:#64748b;font-size:11px;text-transform:uppercase;
    letter-spacing:0.1em;">{date_str}</p>
  <h1 style="margin:0 0 4px;color:#ffffff;font-size:22px;font-weight:700;
    letter-spacing:-0.02em;">{biz}</h1>
  <p style="margin:0;color:#94a3b8;font-size:13px;">Monthly financial report · {s['period']}</p>
</td></tr>

<!-- KPI strip -->
<tr><td style="padding:24px 32px 0;">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
  <td width="33%" style="padding-right:8px;vertical-align:top;">
    <div style="background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;padding:14px 16px;">
      <p style="margin:0 0 2px;font-size:10px;font-weight:700;color:#94a3b8;
        text-transform:uppercase;letter-spacing:0.08em;">Revenue</p>
      <p style="margin:0 0 2px;font-size:22px;font-weight:700;color:#0f172a;
        letter-spacing:-0.02em;">S${s['revenue']:,.0f}</p>
      <p style="margin:0;font-size:11px;color:{rev_color};font-weight:600;">
        {rev_arrow} {abs(s['rev_chg']):.1f}% vs last month</p>
    </div>
  </td>
  <td width="33%" style="padding:0 4px;vertical-align:top;">
    <div style="background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;padding:14px 16px;">
      <p style="margin:0 0 2px;font-size:10px;font-weight:700;color:#94a3b8;
        text-transform:uppercase;letter-spacing:0.08em;">Net profit</p>
      <p style="margin:0 0 2px;font-size:22px;font-weight:700;color:#0f172a;
        letter-spacing:-0.02em;">S${s['net']:,.0f}</p>
      <p style="margin:0;font-size:11px;color:{net_color};font-weight:600;">
        Margin: {s['margin']:.1f}%</p>
    </div>
  </td>
  <td width="33%" style="padding-left:8px;vertical-align:top;">
    <div style="background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;padding:14px 16px;">
      <p style="margin:0 0 2px;font-size:10px;font-weight:700;color:#94a3b8;
        text-transform:uppercase;letter-spacing:0.08em;">Cash runway</p>
      <p style="margin:0 0 2px;font-size:22px;font-weight:700;color:#0f172a;
        letter-spacing:-0.02em;">{runway_label}</p>
      <p style="margin:0;font-size:11px;color:#64748b;">At current burn rate</p>
    </div>
  </td>
</tr></table>
</td></tr>

<!-- Insights -->
<tr><td style="padding:20px 32px 0;">
  <h3 style="font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;
    letter-spacing:0.08em;margin:0 0 12px;">AI Insights</h3>
  {insight_block("✅ This month's win",   insights.get("win",""),   "#22c55e","#f0fdf4","#16a34a")}
  {insight_block("🚨 Alert",              insights.get("alert",""), "#ef4444","#fef2f2","#991b1b")}
  {insight_block("💡 Action this week",   insights.get("tip",""),   "#3b82f6","#eff6ff","#1d4ed8")}
</td></tr>

<!-- Top expenses -->
<tr><td style="padding:16px 32px 0;">
  <h3 style="font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;
    letter-spacing:0.08em;margin:0 0 10px;">Top expenses</h3>
  <table style="width:100%;border-collapse:collapse;">{exp_rows}</table>
</td></tr>

<!-- Anomalies -->
<tr><td style="padding:0 32px;">{anom_html}</td></tr>

<!-- Benchmarks -->
<tr><td style="padding:0 32px;">{bm_html}</td></tr>

<!-- Forecast -->
<tr><td style="padding:0 32px;">{fc_html}</td></tr>

<!-- Footer -->
<tr><td style="padding:24px 32px;border-top:1px solid #f1f5f9;margin-top:8px;">
  <p style="margin:0;font-size:11px;color:#94a3b8;">
    Generated by <strong>SME Co-Pilot</strong> · {date_str}<br>
    Reply to this email with any questions about your numbers.
  </p>
</td></tr>

</table>
</td></tr></table>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  WHATSAPP VIA TWILIO
# ══════════════════════════════════════════════════════════════════════════════

def send_whatsapp(to_number: str, sid: str, token: str, from_number: str,
                  business: str, s: dict, insights: dict,
                  anomalies: list, runway_label: str) -> tuple:

    if not all([to_number, sid, token, from_number]):
        return False, "Fill in all Twilio credentials in Settings."

    try:
        from twilio.rest import Client
    except ImportError:
        return False, "Twilio not installed. Run: pip install twilio"

    rev_arrow = "↑" if s["rev_chg"] >= 0 else "↓"
    anom_line = ""
    if anomalies:
        a = anomalies[0]
        anom_line = f"\n⚠️ *Anomaly:* {a['category']} up +{a['change_pct']:.0f}% (S${a['current']:,.0f})"

    msg = (
        f"📊 *SME Co-Pilot — {business}*\n"
        f"_{s['period']} report_\n\n"
        f"💰 Revenue: *S${s['revenue']:,.0f}* ({rev_arrow}{abs(s['rev_chg']):.1f}%)\n"
        f"📈 Net profit: *S${s['net']:,.0f}* ({s['margin']:.1f}% margin)\n"
        f"⏱ Cash runway: *{runway_label}*"
        f"{anom_line}\n\n"
        f"✅ *Win:* {insights.get('win','')[:120]}...\n\n"
        f"🚨 *Alert:* {insights.get('alert','')[:120]}...\n\n"
        f"💡 *Tip:* {insights.get('tip','')[:120]}..."
    )

    # Ensure WhatsApp format
    from_wa = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"
    to_wa   = to_number   if to_number.startswith("whatsapp:")   else f"whatsapp:{to_number}"

    try:
        client = Client(sid, token)
        client.messages.create(body=msg, from_=from_wa, to=to_wa)
        return True, f"✓ WhatsApp report sent to {to_number}"
    except Exception as e:
        return False, f"WhatsApp failed: {e}"
