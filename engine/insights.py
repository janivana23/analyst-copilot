"""
engine/insights.py — GPT-4o insight generator

Converts computed financial metrics into plain-English,
actionable business advice tailored for Singapore SMEs.

Falls back to a deterministic rule engine if no API key is set.
"""

import os
import re
import logging
from typing import Optional

log = logging.getLogger(__name__)

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

SYSTEM_PROMPT = """You are a sharp, no-nonsense business advisor 
for Singapore SMEs (F&B, retail, services). You have 20 years 
of experience helping small business owners in Singapore manage 
cash flow, control costs, and grow sustainably.

Your style:
- Cite specific dollar figures from the data — never vague
- Compare to previous periods to show momentum
- Each insight ends with ONE concrete action the owner can do TODAY or THIS WEEK
- Plain English — no jargon, no filler like "it's worth noting"
- Be direct, like a trusted accountant friend over coffee
- Singapore-specific: reference CPF, GST, MOM regulations when relevant
- 2–3 sentences per insight maximum"""


def generate(
    summary: dict,
    anomalies: list,
    benchmarks: list,
    forecast: dict,
    runway: dict,
    business_name: str,
    industry: str = "General",
    api_key: str = "",
) -> dict:
    """
    Generate WIN / ALERT / TIP insights.
    Returns dict with keys: win, alert, tip (str each).
    """
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    if key and _OPENAI_AVAILABLE:
        try:
            return _gpt_insights(summary, anomalies, benchmarks, forecast,
                                  runway, business_name, industry, key)
        except Exception as e:
            log.warning("GPT call failed (%s) — using rule-based fallback", e)

    return _rule_insights(summary, anomalies, benchmarks, runway)


# ══════════════════════════════════════════════════════════════════════════════
#  GPT PATH
# ══════════════════════════════════════════════════════════════════════════════

def _gpt_insights(summary, anomalies, benchmarks, forecast,
                   runway, business_name, industry, api_key) -> dict:

    # Build anomaly block
    anom_block = ""
    if anomalies:
        lines = [
            f"  • {a['category']}: S${a['current']:,.0f} "
            f"(+{a['change_pct']}% vs usual S${a['average']:,.0f})"
            for a in anomalies[:3]
        ]
        anom_block = "ANOMALIES FLAGGED:\n" + "\n".join(lines)

    # Build benchmark block
    bm_lines = [
        f"  • {b['label']}: {b['value']} — {b['rating']} (industry median: {b['median']})"
        for b in benchmarks[:4]
    ]
    bm_block = "INDUSTRY BENCHMARKS:\n" + "\n".join(bm_lines) if bm_lines else ""

    # Build forecast block
    fc = forecast.get("forecasts", [])
    fc_block = ""
    if fc:
        fc_block = (
            f"REVENUE FORECAST (next 3 months): "
            f"S${fc[0]:,.0f} / S${fc[1]:,.0f} / S${fc[2]:,.0f} "
            f"[trend: {forecast.get('trend', 'unknown')}, "
            f"confidence: {forecast.get('confidence', 'low')}]"
        )

    # Build top expenses block
    top_exp = "\n".join(
        f"  • {cat}: S${amt:,.0f}"
        for cat, amt in list(summary.get("top_expenses", {}).items())[:5]
    )

    user_prompt = f"""Financial data for {business_name} ({industry} industry) — {summary['period']}:

SUMMARY:
  Revenue:    S${summary['revenue']:,.0f}  ({summary['revenue_change']:+.1f}% vs last month)
  Expenses:   S${summary['expenses']:,.0f}  ({summary['expenses_change']:+.1f}% vs last month)
  Net profit: S${summary['net_profit']:,.0f}  (margin: {summary['profit_margin']:.1f}%)
  Cash runway: {runway.get('label', 'unknown')}

TOP EXPENSES:
{top_exp}

{anom_block}

{bm_block}

{fc_block}

Write EXACTLY 3 insights using these labels (one per line, then the text):
WIN: [the biggest positive this month]
ALERT: [the most important risk or problem — be specific]
TIP: [one concrete action the owner should take this week — be specific]"""

    client = OpenAI(api_key=api_key)
    resp   = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    return _parse(resp.choices[0].message.content)


def _parse(text: str) -> dict:
    result = {"win": "", "alert": "", "tip": ""}
    for key in ("WIN", "ALERT", "TIP"):
        m = re.search(
            rf"{key}:\s*(.+?)(?=(?:WIN:|ALERT:|TIP:|$))",
            text, re.DOTALL | re.IGNORECASE
        )
        if m:
            result[key.lower()] = m.group(1).strip()
    # Final fallback: split by lines
    if not any(result.values()):
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) >= 3:
            result["win"]   = lines[0]
            result["alert"] = lines[1]
            result["tip"]   = lines[2]
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  RULE-BASED FALLBACK
# ══════════════════════════════════════════════════════════════════════════════

def _rule_insights(summary: dict, anomalies: list,
                   benchmarks: list, runway: dict) -> dict:
    rev     = summary.get("revenue", 0)
    exp     = summary.get("expenses", 0)
    net     = summary.get("net_profit", 0)
    rev_chg = summary.get("revenue_change", 0)
    exp_chg = summary.get("expenses_change", 0)
    margin  = summary.get("profit_margin", 0)
    top_exp = summary.get("top_expenses", {})

    # ── WIN ──
    if rev_chg >= 10:
        win = (
            f"Revenue jumped {rev_chg:+.1f}% to S${rev:,.0f} — "
            f"your strongest month in the data. "
            f"Identify which product or channel drove this and invest more there."
        )
    elif net > 0 and margin >= 15:
        win = (
            f"Solid {margin:.1f}% profit margin this month — "
            f"S${net:,.0f} net profit on S${rev:,.0f} revenue. "
            f"You're in the top quartile for Singapore SMEs in your sector."
        )
    elif rev_chg >= 0:
        win = (
            f"Revenue held steady at S${rev:,.0f} despite market pressures. "
            f"Your cost control is working — expenses at S${exp:,.0f} "
            f"({exp / rev * 100:.0f}% of revenue)."
        )
    else:
        win = (
            f"You have full visibility into your finances this month — "
            f"that alone puts you ahead of most Singapore SMEs. "
            f"Use these numbers to make one pricing or cost decision this week."
        )

    # ── ALERT ──
    if anomalies:
        a     = anomalies[0]
        alert = (
            f"{a['category']} spiked to S${a['current']:,.0f} this month — "
            f"{a['change_pct']:+.0f}% above your usual S${a['average']:,.0f}. "
            f"Pull every transaction in that category today and confirm whether "
            f"this is a one-off or a new recurring cost."
        )
    elif runway.get("status") == "red":
        alert = (
            f"Cash runway is only {runway.get('label', 'critical')} at current burn. "
            f"Call your top 3 customers with outstanding invoices today — "
            f"even partial payment this week improves your position significantly."
        )
    elif exp_chg > 15:
        top_cat = list(top_exp.keys())[0] if top_exp else "your biggest expense category"
        alert = (
            f"Expenses rose {exp_chg:+.1f}% this month — "
            f"your biggest cost is {top_cat} at S${top_exp.get(top_cat, 0):,.0f}. "
            f"Request competing quotes from two alternative suppliers this week."
        )
    elif margin < 8:
        alert = (
            f"Profit margin is {margin:.1f}% — below the Singapore SME median of ~10%. "
            f"Your highest-cost category is "
            f"{list(top_exp.keys())[0] if top_exp else 'unknown'}. "
            f"Consider a 5–8% price increase on your top sellers to recover margin."
        )
    else:
        top_cat = list(top_exp.keys())[0] if top_exp else "expenses"
        alert = (
            f"No critical alerts, but your largest cost is "
            f"{top_cat} at S${top_exp.get(top_cat, 0):,.0f} — "
            f"get three competing quotes this quarter to ensure you're not overpaying."
        )

    # ── TIP ──
    # Pick the highest-impact action based on current situation
    if net < 0:
        tip = (
            f"You're S${abs(net):,.0f} in the red this month. "
            f"Identify the one expense you can cut or defer by next Friday — "
            f"even S${abs(net) * 0.3:,.0f} in savings closes a third of that gap."
        )
    elif top_exp:
        top_cat, top_amt = list(top_exp.items())[0]
        saving = round(top_amt * 0.07, 0)
        tip = (
            f"Your top expense is {top_cat} at S${top_amt:,.0f}/month. "
            f"A 7% reduction — realistic with competitive quoting — "
            f"saves S${saving:,.0f} per month, or S${saving * 12:,.0f} per year."
        )
    else:
        tip = (
            f"Set up a 15-minute 'finance Monday' routine: "
            f"check your bank balance, outstanding invoices, and biggest expense. "
            f"Consistency here is worth more than any analytics tool."
        )

    return {"win": win, "alert": alert, "tip": tip}
