"""
connectors/xero.py — Xero OAuth2 connector (pyxero SDK)

Uses the official pyxero library which handles tenant selection,
token refresh, and the connections endpoint correctly.

Install: pip install pyxero requests-oauthlib

Setup:
  1. Register app at https://developer.xero.com/myapps
     - Integration type: Web app
     - Redirect URI: http://localhost:8501
  2. Set XERO_CLIENT_ID and XERO_CLIENT_SECRET in .env
"""

import os
import json
import time
import logging
import requests
from typing import Optional
from db import save_token, load_token, is_token_expired

log = logging.getLogger(__name__)

XERO_AUTH_URL  = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_API_BASE  = "https://api.xero.com/api.xro/2.0"

# Granular scopes — required for apps created after 2 March 2026
XERO_SCOPES = (
    "openid profile email offline_access "
    "accounting.reports.read "
    "accounting.transactions.read "
    "accounting.contacts.read "
    "accounting.settings.read"
)


def get_auth_url(state: str = "xero_connect") -> str:
    """Generate Xero OAuth2 authorisation URL."""
    import urllib.parse
    client_id    = os.getenv("XERO_CLIENT_ID", "")
    redirect_uri = os.getenv("XERO_REDIRECT_URI", "http://localhost:8501")
    if not client_id:
        raise ValueError("XERO_CLIENT_ID not set in .env")
    params = {
        "response_type": "code",
        "client_id":      client_id,
        "redirect_uri":   redirect_uri,
        "scope":          XERO_SCOPES,
        "state":          state,
    }
    return XERO_AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code(code: str, user_email: str) -> dict:
    """
    Exchange auth code for tokens, then fetch and store tenant ID.
    This is the critical step — we must call /connections BEFORE
    storing, so we get the tenant ID with the fresh token.
    """
    client_id     = os.getenv("XERO_CLIENT_ID", "")
    client_secret = os.getenv("XERO_CLIENT_SECRET", "")
    redirect_uri  = os.getenv("XERO_REDIRECT_URI", "http://localhost:8501")

    # Step 1: Exchange code for tokens
    resp = requests.post(
        XERO_TOKEN_URL,
        data={
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  redirect_uri,
            "client_id":     client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Token exchange failed: {resp.status_code} — {resp.text}")

    raw          = resp.json()
    access_token = raw.get("access_token", "")

    if not access_token:
        raise RuntimeError(f"No access token in response: {raw}")

    # Step 2: Get connections — this MUST use the fresh access token
    # immediately after exchange, before anything else
    conn_resp = requests.get(
        "https://api.xero.com/connections",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        },
        timeout=10,
    )

    log.info("Connections response: %s — %s", conn_resp.status_code, conn_resp.text)

    if conn_resp.status_code != 200:
        raise RuntimeError(
            f"Failed to get Xero connections: {conn_resp.status_code} — {conn_resp.text}"
        )

    connections = conn_resp.json()
    log.info("Connections found: %s", json.dumps(connections))

    # Filter to ORGANISATION type only (exclude Practice Manager tenants)
    orgs = [c for c in connections if c.get("tenantType") == "ORGANISATION"]

    if not orgs:
        # Try all connections if no ORGANISATION type found
        if connections:
            orgs = connections
        else:
            raise RuntimeError(
                "No Xero organisations found. "
                "Please make sure you selected an organisation during the Xero login. "
                "Go to go.xero.com, enter your Demo Company or trial org, "
                "then try connecting again."
            )

    tenant_id   = orgs[0]["tenantId"]
    tenant_name = orgs[0].get("tenantName", "Unknown")
    log.info("Using tenant: %s (%s)", tenant_name, tenant_id)

    # Step 3: Store tokens + tenant
    token_data = {
        "access_token":  access_token,
        "refresh_token": raw.get("refresh_token", ""),
        "expires_at":    time.time() + raw.get("expires_in", 1800),
        "tenant_id":     tenant_id,
        "tenant_name":   tenant_name,
        "all_tenants":   connections,
    }
    save_token(user_email, "xero", token_data)
    log.info("Xero connected for %s — org: %s", user_email, tenant_name)
    return token_data


def _get_valid_token(user_email: str) -> Optional[dict]:
    """Load token, refresh if needed. Returns None if not connected."""
    token_data = load_token(user_email, "xero")
    if not token_data:
        return None

    if is_token_expired(token_data):
        log.info("Refreshing Xero token for %s", user_email)
        client_id     = os.getenv("XERO_CLIENT_ID", "")
        client_secret = os.getenv("XERO_CLIENT_SECRET", "")

        resp = requests.post(
            XERO_TOKEN_URL,
            data={
                "grant_type":    "refresh_token",
                "refresh_token": token_data.get("refresh_token", ""),
                "client_id":     client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            log.error("Token refresh failed: %s", resp.text)
            return None

        raw = resp.json()
        token_data["access_token"] = raw["access_token"]
        token_data["expires_at"]   = time.time() + raw.get("expires_in", 1800)
        if "refresh_token" in raw:
            token_data["refresh_token"] = raw["refresh_token"]
        save_token(user_email, "xero", token_data)

    return token_data


def _headers(token_data: dict) -> dict:
    return {
        "Authorization":  f"Bearer {token_data['access_token']}",
        "Xero-Tenant-Id": token_data["tenant_id"],
        "Accept":         "application/json",
    }


def get_profit_and_loss(user_email: str, from_date: str, to_date: str) -> dict:
    """Pull P&L report. Dates: 'YYYY-MM-DD'"""
    token = _get_valid_token(user_email)
    if not token:
        raise RuntimeError(f"Xero not connected for {user_email}")

    resp = requests.get(
        f"{XERO_API_BASE}/Reports/ProfitAndLoss",
        headers=_headers(token),
        params={"fromDate": from_date, "toDate": to_date, "periods": 1, "timeframe": "MONTH"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_balance_sheet(user_email: str, date: str) -> dict:
    token = _get_valid_token(user_email)
    if not token:
        raise RuntimeError(f"Xero not connected for {user_email}")
    resp = requests.get(
        f"{XERO_API_BASE}/Reports/BalanceSheet",
        headers=_headers(token),
        params={"date": date},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_invoices(user_email: str, status: str = "OUTSTANDING") -> list:
    token = _get_valid_token(user_email)
    if not token:
        raise RuntimeError(f"Xero not connected for {user_email}")
    resp = requests.get(
        f"{XERO_API_BASE}/Invoices",
        headers=_headers(token),
        params={"Status": status, "Type": "ACCREC"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("Invoices", [])


def parse_xero_pl(report_json: dict) -> dict:
    """Convert Xero P&L JSON to flat summary dict."""
    summary = {"revenue": 0.0, "cogs": 0.0, "gross": 0.0, "expenses": {}, "net_profit": 0.0}
    try:
        rows = report_json["Reports"][0]["Rows"]
    except (KeyError, IndexError):
        return summary

    INCOME   = {"trading income", "other income", "revenue", "income"}
    COGS     = {"cost of sales", "direct costs", "cogs", "cost of goods sold"}
    EXPENSES = {"operating expenses", "expenses", "overheads", "less operating expenses"}

    for section in rows:
        title = section.get("Title", "").lower()
        for line in section.get("Rows", []):
            cells = line.get("Cells", [])
            if len(cells) < 2:
                continue
            name   = cells[0].get("Value", "").strip()
            amount = _xero_val(cells[1].get("Value", "0"))
            if any(t in title for t in INCOME):
                summary["revenue"] += amount
            elif any(t in title for t in COGS):
                summary["cogs"] += amount
            elif any(t in title for t in EXPENSES):
                if name and name.lower() not in ("total", "net profit", "gross profit"):
                    summary["expenses"][name] = summary["expenses"].get(name, 0) + amount

    summary["gross"]          = summary["revenue"] - summary["cogs"]
    summary["total_expenses"] = sum(summary["expenses"].values())
    summary["net_profit"]     = summary["gross"] - summary["total_expenses"]
    return summary


def _xero_val(v: str) -> float:
    v = str(v).strip().replace(",", "")
    if not v or v == "-":
        return 0.0
    if v.startswith("(") and v.endswith(")"):
        return -float(v[1:-1])
    try:
        return float(v)
    except ValueError:
        return 0.0


def get_tenant_name(user_email: str) -> str:
    token = load_token(user_email, "xero")
    return token.get("tenant_name", "Xero") if token else "Xero"


def is_connected(user_email: str) -> bool:
    return load_token(user_email, "xero") is not None
