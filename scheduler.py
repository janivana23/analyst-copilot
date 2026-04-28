"""
scheduler.py — Automated weekly report scheduler

Runs every Monday at 8:00 AM Singapore time (UTC+8).
For each active user:
  1. Fetch latest financial data (Xero / QuickBooks / stored CSV)
  2. Run analytics engine
  3. Generate GPT insights
  4. Send HTML email report
  5. Store report in history

Run manually:   python scheduler.py --now
Run as service: python scheduler.py          (blocks, runs weekly)
Deploy on:      Railway.app, Render.com, or any VPS with cron

Railway cron syntax (add to railway.toml):
  [cron]
  schedule = "0 0 * * 1"   # every Monday 00:00 UTC = 08:00 SGT
  command  = "python scheduler.py --now"
"""

import os
import sys
import logging
import argparse
import time
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta   # pip install python-dateutil

# ── load .env ─────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── project imports ───────────────────────────────────────────────────────────
import db
from engine   import analytics as eng
from engine   import insights  as ins
from email_report import sender

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ══════════════════════════════════════════════════════════════════════════════
#  CORE JOB
# ══════════════════════════════════════════════════════════════════════════════

def run_for_user(user: dict) -> bool:
    """
    Generate and send the weekly report for one user.
    Returns True on success.
    """
    email    = user["email"]
    name     = user.get("business_name", email)
    industry = user.get("industry", "General")

    log.info("Processing report for %s (%s)", name, email)

    # ── Pull financial data ────────────────────────────────────────────────
    today       = date.today()
    month_start = today.replace(day=1)
    prev_start  = (month_start - relativedelta(months=1))
    six_ago     = (month_start - relativedelta(months=6))

    from_date = six_ago.strftime("%Y-%m-%d")
    to_date   = today.strftime("%Y-%m-%d")

    df = None

    # Try Xero first
    try:
        from connectors import xero
        if xero.is_connected(email):
            log.info("Fetching from Xero for %s", email)
            pl_json = xero.get_profit_and_loss(email, from_date, to_date)
            parsed  = xero.parse_xero_pl(pl_json)
            df      = _pl_dict_to_df(parsed, str(month_start)[:7])
    except Exception as e:
        log.warning("Xero fetch failed for %s: %s", email, e)

    # Try QuickBooks if Xero not connected / failed
    if df is None:
        try:
            from connectors import quickbooks as qb
            if qb.is_connected(email):
                log.info("Fetching from QuickBooks for %s", email)
                pl_json = qb.get_profit_and_loss(email, from_date, to_date)
                parsed  = qb.parse_qb_pl(pl_json)
                df      = _pl_dict_to_df(parsed, str(month_start)[:7])
        except Exception as e:
            log.warning("QuickBooks fetch failed for %s: %s", email, e)

    if df is None:
        log.warning("No data source for %s — skipping", email)
        return False

    # ── Run analytics ──────────────────────────────────────────────────────
    summary   = eng.compute_summary(df)
    anomalies = eng.detect_anomalies(df)
    forecast  = eng.forecast_revenue(summary.get("revenue_trend", []))
    runway    = eng.compute_runway(summary)
    benchmarks= eng.benchmark(summary, industry)

    # ── Generate insights ─────────────────────────────────────────────────
    insights_dict = ins.generate(
        summary    = summary,
        anomalies  = anomalies,
        benchmarks = benchmarks,
        forecast   = forecast,
        runway     = runway,
        business_name = name,
        industry   = industry,
        api_key    = os.getenv("OPENAI_API_KEY", ""),
    )

    # ── Send email ────────────────────────────────────────────────────────
    ok = sender.send_weekly_report(
        to_email      = email,
        business_name = name,
        summary       = summary,
        insights      = insights_dict,
        anomalies     = anomalies,
        runway        = runway,
        forecast      = forecast,
        benchmarks    = benchmarks,
    )

    if ok:
        db.save_report(email, summary.get("period", ""), summary, insights_dict)
        log.info("Report sent + saved for %s", email)
    else:
        log.error("Email failed for %s", email)

    return ok


def run_all() -> None:
    """Process all active users."""
    users = db.list_active_users()
    log.info("Starting weekly reports for %d users", len(users))

    success, failed = 0, 0
    for user in users:
        try:
            if run_for_user(user):
                success += 1
            else:
                failed += 1
        except Exception as e:
            log.error("Unhandled error for %s: %s", user.get("email"), e)
            failed += 1
        time.sleep(1)   # rate-limit API calls

    log.info("Done — %d sent, %d failed", success, failed)


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _pl_dict_to_df(parsed: dict, period: str):
    """
    Convert a parsed P&L dict (from Xero/QB parser) into the
    normalised DataFrame format the analytics engine expects.

    This is a lightweight shim — in production you'd store the
    full transaction-level data and reprocess it here.
    """
    import pandas as pd
    import numpy as np

    rows = []
    period_dt = pd.Period(period, freq="M")

    # Revenue row
    rows.append({
        "date":       period_dt.to_timestamp(),
        "description":"Revenue",
        "category":   "Revenue",
        "amount":     parsed.get("revenue", 0),
        "amount_abs": parsed.get("revenue", 0),
        "type":       "income",
        "month":      period_dt,
    })

    # Expense rows
    for cat, amt in parsed.get("expenses", {}).items():
        rows.append({
            "date":       period_dt.to_timestamp(),
            "description": cat,
            "category":    cat,
            "amount":      -abs(amt),
            "amount_abs":  abs(amt),
            "type":        "expense",
            "month":       period_dt,
        })

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER LOOP
# ══════════════════════════════════════════════════════════════════════════════

def seconds_until_next_monday_8am_sgt() -> int:
    """Seconds until next Monday 08:00 SGT (UTC+8)."""
    from zoneinfo import ZoneInfo
    sgt   = ZoneInfo("Asia/Singapore")
    now   = datetime.now(sgt)
    days_until_monday = (7 - now.weekday()) % 7 or 7
    next_monday = now.replace(hour=8, minute=0, second=0, microsecond=0)
    next_monday += timedelta(days=days_until_monday)
    return max(0, int((next_monday - now).total_seconds()))


def main() -> None:
    parser = argparse.ArgumentParser(description="SME Co-Pilot scheduler")
    parser.add_argument(
        "--now", action="store_true",
        help="Run immediately instead of waiting for Monday 08:00 SGT"
    )
    parser.add_argument(
        "--user", type=str, default="",
        help="Run only for this email address (for testing)"
    )
    args = parser.parse_args()

    if args.user:
        user = db.get_user(args.user) or {"email": args.user}
        run_for_user(user)
        return

    if args.now:
        run_all()
        return

    # Continuous loop — sleep until Monday 08:00 SGT, run, repeat
    log.info("Scheduler started. Waiting for Monday 08:00 SGT.")
    while True:
        wait = seconds_until_next_monday_8am_sgt()
        log.info("Next run in %dh %dm", wait // 3600, (wait % 3600) // 60)
        time.sleep(wait)
        run_all()
        time.sleep(60)   # prevent double-fire on DST edge


if __name__ == "__main__":
    main()
