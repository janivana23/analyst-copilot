"""
utils/storage.py — Local JSON storage for settings and report history.
Saves to sme_data/ folder next to the app. No database needed.
"""
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "sme_data"
DATA_DIR.mkdir(exist_ok=True)

SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORY_FILE  = DATA_DIR / "reports.json"


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    return dict(
        business="My Business", industry="F&B",
        smtp_user="", smtp_pass="",
        whatsapp_to="", twilio_sid="",
        twilio_token="", twilio_from="",
        openai_key="",
    )


def save_settings(s: dict):
    SETTINGS_FILE.write_text(json.dumps(s, indent=2))


def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return []


def save_report(period: str, summary: dict, insights: dict,
                anomalies: list, benchmarks: list, business: str):
    history = load_history()
    history.insert(0, dict(
        period=period,
        business=business,
        generated=datetime.today().strftime("%d %b %Y %H:%M"),
        revenue=summary.get("revenue", 0),
        net=summary.get("net", 0),
        margin=summary.get("margin", 0),
        rev_chg=summary.get("rev_chg", 0),
        insights=insights,
        anomalies=anomalies,
        benchmarks=benchmarks,
    ))
    HISTORY_FILE.write_text(json.dumps(history[:12], indent=2))


def clear_history():
    HISTORY_FILE.write_text("[]")
