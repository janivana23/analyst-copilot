"""
email_report/sender.py — Email sender with Gmail SMTP + Resend support

Priority order:
  1. Gmail SMTP  — works immediately, no domain needed (recommended for now)
  2. Resend      — cleaner, needs domain verification
  3. Print       — fallback for local dev (prints to terminal)

Gmail setup (2 minutes):
  1. Go to myaccount.google.com/apppasswords
  2. Select app: Mail, device: Mac (or Other)
  3. Copy the 16-character password
  4. Add to .env:
       SMTP_USER=yourname@gmail.com
       SMTP_PASS=xxxx xxxx xxxx xxxx   (the 16-char app password)
"""

import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from datetime             import datetime

log = logging.getLogger(__name__)


def send_weekly_report(
    to_email: str,
    business_name: str,
    summary: dict,
    insights: dict,
    anomalies: list,
    runway: dict,
    forecast: dict,
    benchmarks: list,
) -> bool:
    subject = _subject(summary)
    html    = render_html(business_name, summary, insights, anomalies, runway, forecast, benchmarks)
    plain   = render_plain(business_name, summary, insights, anomalies)

    # Try Gmail SMTP first (no domain needed)
    if os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"):
        return _send_gmail(to_email, subject, html, plain)

    # Try Resend (needs verified domain)
    if os.getenv("RESEND_API_KEY"):
        return _send_resend(to_email, subject, html, plain)

    # Dev fallback — print to terminal
    log.warning("No email provider configured. Set SMTP_USER + SMTP_PASS in .env for Gmail.")
    print(f"\n{'='*60}\nEMAIL TO: {to_email}\nSUBJECT: {subject}\n{'='*60}")
    print(plain)
    return True


def _subject(summary: dict) -> str:
    rev_chg = summary.get("revenue_change", 0)
    period  = summary.get("period", "this month")
    arrow   = "↑" if rev_chg >= 0 else "↓"
    return f"[SME Co-Pilot] {period} report — Revenue {arrow} {abs(rev_chg):.1f}%"


# ══════════════════════════════════════════════════════
#  GMAIL SMTP  — works with any Gmail account
# ══════════════════════════════════════════════════════

def _send_gmail(to: str, subject: str, html: str, plain: str) -> bool:
    """
    Send via Gmail SMTP using an App Password.
    App passwords: myaccount.google.com/apppasswords
    Requires 2FA enabled on your Google account.
    """
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "").replace(" ", "")  # strip spaces from app password

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"SME Co-Pilot <{smtp_user}>"
    msg["To"]      = to
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [to], msg.as_string())
        log.info("Email sent via Gmail to %s", to)
        return True
    except smtplib.SMTPAuthenticationError:
        log.error(
            "Gmail auth failed. Make sure you used an App Password "
            "(myaccount.google.com/apppasswords), not your regular password."
        )
        return False
    except Exception as e:
        log.error("Gmail send failed: %s", e)
        return False


# ══════════════════════════════════════════════════════
#  RESEND  — needs verified domain
# ══════════════════════════════════════════════════════

def _send_resend(to: str, subject: str, html: str, plain: str) -> bool:
    try:
        import resend
        resend.api_key = os.getenv("RESEND_API_KEY", "")
        from_email = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
        resend.Emails.send({
            "from":    from_email,
            "to":      [to],
            "subject": subject,
            "html":    html,
            "text":    plain,
        })
        log.info("Email sent via Resend to %s", to)
        return True
    except Exception as e:
        log.error("Resend failed: %s", e)
        return False


# ══════════════════════════════════════════════════════
#  HTML TEMPLATE
# ══════════════════════════════════════════════════════

def render_html(business_name, summary, insights, anomalies, runway, forecast, benchmarks) -> str:
    rev     = summary.get("revenue", 0)
    exp     = summary.get("expenses", 0)
    net     = summary.get("net_profit", 0)
    margin  = summary.get("profit_margin", 0)
    rev_chg = summary.get("revenue_change", 0)
    period  = summary.get("period", "")
    date_str= datetime.today().strftime("%d %B %Y")

    runway_color = {"green": "#16a34a", "amber": "#d97706", "red": "#dc2626"}.get(
        runway.get("status", "green"), "#16a34a"
    )
    rev_color = "#16a34a" if rev_chg >= 0 else "#dc2626"
    rev_arrow = "↑" if rev_chg >= 0 else "↓"

    exp_rows = "".join(
        f'<tr><td style="padding:8px 0;color:#374151;font-size:14px;border-bottom:1px solid #f3f4f6;">{cat}</td>'
        f'<td style="padding:8px 0;text-align:right;font-weight:600;color:#111827;font-size:14px;border-bottom:1px solid #f3f4f6;">S${amt:,.0f}</td></tr>'
        for cat, amt in list(summary.get("top_expenses", {}).items())[:5]
    )

    anom_section = ""
    if anomalies:
        anom_items = "".join(
            f'<div style="background:#fef2f2;border-left:3px solid #ef4444;border-radius:6px;padding:10px 14px;margin-bottom:8px;">'
            f'<strong style="color:#991b1b;">{a["category"]}</strong>'
            f'<span style="color:#6b7280;"> — S${a["current"]:,.0f} vs usual S${a["average"]:,.0f} '
            f'<span style="color:#dc2626;font-weight:600;">(+{a["change_pct"]:.0f}%)</span></span></div>'
            for a in anomalies[:3]
        )
        anom_section = f'<h3 style="font-size:13px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:0.06em;margin:24px 0 12px;">Anomalies flagged</h3>{anom_items}'

    fc_section = ""
    fc = forecast.get("forecasts", [])
    if len(fc) >= 3:
        fc_section = (
            f'<div style="background:#f0f9ff;border-radius:10px;padding:16px 20px;margin:20px 0;">'
            f'<p style="margin:0 0 6px;font-size:13px;font-weight:600;color:#0369a1;">Revenue forecast (next 3 months)</p>'
            f'<p style="margin:0;font-size:14px;color:#0c4a6e;">S${fc[0]:,.0f} → S${fc[1]:,.0f} → S${fc[2]:,.0f}'
            f'<span style="color:#6b7280;font-size:12px;"> ({forecast.get("trend","")} · {forecast.get("confidence","")} confidence)</span></p></div>'
        )

    def insight_block(label, text, accent, bg, fg):
        if not text:
            return ""
        return (
            f'<div style="border-left:3px solid {accent};background:{bg};border-radius:0 8px 8px 0;padding:14px 16px;margin-bottom:12px;">'
            f'<p style="margin:0 0 4px;font-size:11px;font-weight:600;color:{fg};text-transform:uppercase;letter-spacing:0.06em;">{label}</p>'
            f'<p style="margin:0;font-size:14px;color:#374151;line-height:1.6;">{text}</p></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SME Co-Pilot Report</title></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;border:1px solid #e5e7eb;">

<tr><td style="background:#1a1a2e;padding:28px 32px;">
  <p style="margin:0;color:#9ca3af;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;">{date_str}</p>
  <h1 style="margin:6px 0 0;color:#fff;font-size:22px;font-weight:600;">{business_name}</h1>
  <p style="margin:4px 0 0;color:#6b7280;font-size:14px;">Monthly report · {period}</p>
</td></tr>

<tr><td style="padding:28px 32px 0;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr>
    <td width="33%" style="padding:0 6px 20px 0;vertical-align:top;">
      <div style="background:#f9fafb;border-radius:10px;padding:14px 16px;">
        <p style="margin:0 0 4px;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;">Revenue</p>
        <p style="margin:0 0 4px;font-size:22px;font-weight:700;color:#111827;">S${rev:,.0f}</p>
        <p style="margin:0;font-size:12px;color:{rev_color};">{rev_arrow} {abs(rev_chg):.1f}% vs last month</p>
      </div>
    </td>
    <td width="33%" style="padding:0 6px 20px;vertical-align:top;">
      <div style="background:#f9fafb;border-radius:10px;padding:14px 16px;">
        <p style="margin:0 0 4px;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;">Net profit</p>
        <p style="margin:0 0 4px;font-size:22px;font-weight:700;color:#111827;">S${net:,.0f}</p>
        <p style="margin:0;font-size:12px;color:#6b7280;">Margin: {margin:.1f}%</p>
      </div>
    </td>
    <td width="33%" style="padding:0 0 20px 6px;vertical-align:top;">
      <div style="background:#f9fafb;border-radius:10px;padding:14px 16px;">
        <p style="margin:0 0 4px;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;">Cash runway</p>
        <p style="margin:0 0 4px;font-size:22px;font-weight:700;color:#111827;">{runway.get("label","—")}</p>
        <p style="margin:0;font-size:12px;color:{runway_color};">{runway.get("advice","").split(".")[0]}</p>
      </div>
    </td>
  </tr></table>
</td></tr>

<tr><td style="padding:0 32px 20px;">
  <h3 style="font-size:13px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:0.06em;margin:0 0 16px;">AI insights</h3>
  {insight_block("This month's win",   insights.get("win",""),   "#22c55e","#f0fdf4","#16a34a")}
  {insight_block("Alert",              insights.get("alert",""), "#ef4444","#fef2f2","#991b1b")}
  {insight_block("Action this week",   insights.get("tip",""),   "#3b82f6","#eff6ff","#1d4ed8")}
</td></tr>

<tr><td style="padding:0 32px 20px;">
  <h3 style="font-size:13px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:0.06em;margin:0 0 12px;">Top expenses</h3>
  <table style="width:100%;border-collapse:collapse;">{exp_rows}</table>
</td></tr>

<tr><td style="padding:0 32px 20px;">{anom_section}{fc_section}</td></tr>

<tr><td style="padding:20px 32px;border-top:1px solid #f3f4f6;">
  <p style="margin:0;font-size:12px;color:#9ca3af;">
    Generated by SME Co-Pilot · Reply to this email with any questions
  </p>
</td></tr>

</table></td></tr></table>
</body></html>"""


def render_plain(business_name, summary, insights, anomalies) -> str:
    lines = [
        f"SME Co-Pilot — {business_name} — {summary.get('period','')}",
        "=" * 50,
        f"Revenue:    S${summary.get('revenue',0):,.0f} ({summary.get('revenue_change',0):+.1f}%)",
        f"Expenses:   S${summary.get('expenses',0):,.0f}",
        f"Net profit: S${summary.get('net_profit',0):,.0f} ({summary.get('profit_margin',0):.1f}% margin)",
        "",
        f"WIN:   {insights.get('win','')}",
        f"ALERT: {insights.get('alert','')}",
        f"TIP:   {insights.get('tip','')}",
    ]
    if anomalies:
        lines += ["", "ANOMALIES:"]
        for a in anomalies:
            lines.append(f"  • {a['category']}: S${a['current']:,.0f} (+{a['change_pct']:.0f}% above usual)")
    return "\n".join(lines)
