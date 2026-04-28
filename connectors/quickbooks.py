"""
connectors/quickbooks.py — QuickBooks Online OAuth2 connector

Handles the full OAuth2 flow for QuickBooks Online:
  1. Generate auth URL → redirect user
  2. Exchange auth code for tokens
  3. Auto-refresh expired tokens
  4. Pull P&L, transactions, invoices

Setup:
  1. Create app at https://developer.intuit.com
  2. Keys & OAuth → copy Client ID and Client Secret
  3. Set redirect URI: https://yourapp.com/callback/qb
  4. Set QB_CLIENT_ID, QB_CLIENT_SECRET in .env
  5. Set QB_ENV=production (or sandbox for testing)

Sandbox tip: use https://sandbox-quickbooks.api.intuit.com for testing
with the pre-populated sandbox company from developer.intuit.com
"""

import os
import time
import logging
import requests
from typing import Optional
from db import save_token, load_token, is_token_expired

log = logging.getLogger(__name__)

QB_AUTH_URL   = "https://appcenter.intuit.com/connect/oauth2"
QB_TOKEN_URL  = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QB_REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"

QB_SCOPE = "com.intuit.quickbooks.accounting"


def _api_base(realm_id: str) -> str:
    env = os.getenv("QB_ENV", "production")
    host = (
        "https://sandbox-quickbooks.api.intuit.com"
        if env == "sandbox"
        else "https://quickbooks.api.intuit.com"
    )
    return f"{host}/v3/company/{realm_id}"


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH FLOW
# ══════════════════════════════════════════════════════════════════════════════

def get_auth_url(state: str = "qb_connect") -> str:
    """
    Step 1: URL to redirect the user to QuickBooks login.
    """
    client_id    = os.getenv("QB_CLIENT_ID", "")
    redirect_uri = os.getenv("QB_REDIRECT_URI", "http://localhost:8501/callback/qb")

    if not client_id:
        raise ValueError("QB_CLIENT_ID not set in environment")

    params = {
        "client_id":     client_id,
        "scope":         QB_SCOPE,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "state":         state,
    }
    return QB_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())


def exchange_code(code: str, realm_id: str, user_email: str) -> dict:
    """
    Step 2: Exchange auth code for tokens.
    realm_id is passed as a query param by QuickBooks in the callback URL.
    """
    client_id     = os.getenv("QB_CLIENT_ID", "")
    client_secret = os.getenv("QB_CLIENT_SECRET", "")
    redirect_uri  = os.getenv("QB_REDIRECT_URI", "http://localhost:8501/callback/qb")

    resp = requests.post(
        QB_TOKEN_URL,
        auth=(client_id, client_secret),
        data={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": redirect_uri,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    raw = resp.json()

    token_data = {
        "access_token":  raw["access_token"],
        "refresh_token": raw["refresh_token"],
        "expires_at":    time.time() + raw.get("expires_in", 3600),
        "realm_id":      realm_id,
    }
    save_token(user_email, "quickbooks", token_data)
    log.info("QuickBooks tokens saved for %s (realm: %s)", user_email, realm_id)
    return token_data


def _refresh_if_needed(user_email: str) -> Optional[dict]:
    """Load and auto-refresh QuickBooks tokens."""
    token_data = load_token(user_email, "quickbooks")
    if not token_data:
        return None

    if is_token_expired(token_data):
        log.info("Refreshing QuickBooks token for %s", user_email)
        client_id     = os.getenv("QB_CLIENT_ID", "")
        client_secret = os.getenv("QB_CLIENT_SECRET", "")

        resp = requests.post(
            QB_TOKEN_URL,
            auth=(client_id, client_secret),
            data={
                "grant_type":    "refresh_token",
                "refresh_token": token_data["refresh_token"],
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()

        token_data["access_token"] = raw["access_token"]
        token_data["expires_at"]   = time.time() + raw.get("expires_in", 3600)
        if "refresh_token" in raw:
            token_data["refresh_token"] = raw["refresh_token"]
        save_token(user_email, "quickbooks", token_data)

    return token_data


def _headers(token_data: dict) -> dict:
    return {
        "Authorization": f"Bearer {token_data['access_token']}",
        "Accept":        "application/json",
    }


# ══════════════════════════════════════════════════════════════════════════════
#  DATA PULLING
# ══════════════════════════════════════════════════════════════════════════════

def get_profit_and_loss(
    user_email: str,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Pull P&L report from QuickBooks Online.
    Dates: "YYYY-MM-DD"
    """
    token = _refresh_if_needed(user_email)
    if not token:
        raise RuntimeError(f"QuickBooks not connected for {user_email}")

    resp = requests.get(
        f"{_api_base(token['realm_id'])}/reports/ProfitAndLoss",
        headers=_headers(token),
        params={
            "start_date":       start_date,
            "end_date":         end_date,
            "summarize_column_by": "Month",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_balance_sheet(user_email: str, date: str) -> dict:
    """Balance sheet for cash on hand."""
    token = _refresh_if_needed(user_email)
    if not token:
        raise RuntimeError(f"QuickBooks not connected for {user_email}")

    resp = requests.get(
        f"{_api_base(token['realm_id'])}/reports/BalanceSheet",
        headers=_headers(token),
        params={"date_macro": "Today", "as_of_date": date},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_transactions(
    user_email: str,
    start_date: str,
    end_date: str,
) -> list[dict]:
    """
    Pull transaction list (GeneralLedger) for the period.
    Returns simplified list of dicts.
    """
    token = _refresh_if_needed(user_email)
    if not token:
        raise RuntimeError(f"QuickBooks not connected for {user_email}")

    resp = requests.get(
        f"{_api_base(token['realm_id'])}/reports/GeneralLedger",
        headers=_headers(token),
        params={"start_date": start_date, "end_date": end_date},
        timeout=20,
    )
    resp.raise_for_status()
    return _parse_gl(resp.json())


def get_accounts_receivable(user_email: str) -> dict:
    """Outstanding invoices / money owed to the business."""
    token = _refresh_if_needed(user_email)
    if not token:
        raise RuntimeError(f"QuickBooks not connected for {user_email}")

    resp = requests.get(
        f"{_api_base(token['realm_id'])}/reports/AgedReceivables",
        headers=_headers(token),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ══════════════════════════════════════════════════════════════════════════════
#  QB REPORT → NORMALISED SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def parse_qb_pl(report_json: dict) -> dict:
    """
    Flatten QuickBooks P&L JSON into the same summary format as Xero.
    QB structure: Rows[].Rows[] → Header (section name), ColData (amounts)
    """
    summary = {
        "revenue":        0.0,
        "cogs":           0.0,
        "gross":          0.0,
        "expenses":       {},
        "net_profit":     0.0,
        "total_expenses": 0.0,
    }

    try:
        rows = report_json["Rows"]["Row"]
    except (KeyError, TypeError):
        return summary

    INCOME_LABELS  = {"income", "revenue", "total income", "other income"}
    COGS_LABELS    = {"cost of goods sold", "cogs", "cost of sales", "direct costs"}
    EXPENSE_LABELS = {"expenses", "operating expenses", "other expenses"}

    for section in rows:
        header = ""
        if "Header" in section:
            header = section["Header"].get("ColData", [{}])[0].get("value", "").lower()

        inner_rows = section.get("Rows", {}).get("Row", [])

        for line in inner_rows:
            cols = line.get("ColData", [])
            if len(cols) < 2:
                continue
            name   = cols[0].get("value", "").strip()
            amount = _qb_val(cols[1].get("value", "0"))

            if any(lbl in header for lbl in INCOME_LABELS):
                summary["revenue"] += amount
            elif any(lbl in header for lbl in COGS_LABELS):
                summary["cogs"] += amount
            elif any(lbl in header for lbl in EXPENSE_LABELS):
                if name and "total" not in name.lower():
                    summary["expenses"][name] = summary["expenses"].get(name, 0) + amount

    summary["gross"]          = summary["revenue"] - summary["cogs"]
    summary["total_expenses"] = sum(summary["expenses"].values())
    summary["net_profit"]     = summary["gross"] - summary["total_expenses"]
    return summary


def _parse_gl(gl_json: dict) -> list[dict]:
    """Convert GeneralLedger report to flat transaction list."""
    txns = []
    try:
        rows = gl_json["Rows"]["Row"]
    except (KeyError, TypeError):
        return txns

    for section in rows:
        account = ""
        if "Header" in section:
            account = section["Header"].get("ColData", [{}])[0].get("value", "")
        for line in section.get("Rows", {}).get("Row", []):
            cols = line.get("ColData", [])
            if len(cols) >= 4:
                txns.append({
                    "date":    cols[0].get("value", ""),
                    "account": account,
                    "name":    cols[1].get("value", ""),
                    "amount":  _qb_val(cols[3].get("value", "0")),
                })
    return txns


def _qb_val(v: str) -> float:
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return 0.0


def is_connected(user_email: str) -> bool:
    return load_token(user_email, "quickbooks") is not None
