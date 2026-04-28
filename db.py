"""
db.py — Supabase database layer
Handles user accounts, OAuth tokens, and report history.

Setup:
  1. Create a free project at https://supabase.com
  2. Run the SQL in schema.sql to create tables
  3. Set SUPABASE_URL and SUPABASE_KEY in .env

Fallback: if Supabase is not configured, uses an in-memory dict
(fine for local dev / demos, data lost on restart).
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

# ── Try to import supabase client ─────────────────────────────────────────────
try:
    from supabase import create_client, Client
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False

# ── In-memory fallback store ──────────────────────────────────────────────────
_MEM: dict = {"users": {}, "tokens": {}, "reports": []}


def _get_client() -> Optional["Client"]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if _SUPABASE_AVAILABLE and url and key:
        return create_client(url, key)
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  USERS
# ══════════════════════════════════════════════════════════════════════════════

def upsert_user(email: str, business_name: str = "") -> dict:
    """Create or update a user record. Returns the user dict."""
    client = _get_client()
    now = datetime.utcnow().isoformat()

    if client:
        res = (
            client.table("users")
            .upsert(
                {"email": email, "business_name": business_name, "updated_at": now},
                on_conflict="email",
            )
            .execute()
        )
        return res.data[0] if res.data else {}

    # Fallback
    if email not in _MEM["users"]:
        _MEM["users"][email] = {
            "id": email,
            "email": email,
            "business_name": business_name,
            "created_at": now,
            "plan": "trial",
            "report_day": "monday",
        }
    else:
        _MEM["users"][email]["business_name"] = business_name
    return _MEM["users"][email]


def get_user(email: str) -> Optional[dict]:
    client = _get_client()
    if client:
        res = client.table("users").select("*").eq("email", email).execute()
        return res.data[0] if res.data else None
    return _MEM["users"].get(email)


def list_active_users() -> list[dict]:
    """Return all users who have at least one connected accounting source."""
    client = _get_client()
    if client:
        res = client.table("users").select("*").eq("active", True).execute()
        return res.data or []
    return list(_MEM["users"].values())


# ══════════════════════════════════════════════════════════════════════════════
#  OAUTH TOKENS
# ══════════════════════════════════════════════════════════════════════════════

def save_token(user_email: str, provider: str, token_data: dict) -> None:
    """
    Persist OAuth tokens for a user + provider pair.
    provider: "xero" | "quickbooks"
    token_data keys: access_token, refresh_token, expires_at, tenant_id (xero) / realm_id (qb)
    """
    client = _get_client()
    now = datetime.utcnow().isoformat()
    record = {
        "user_email": user_email,
        "provider": provider,
        "token_data": json.dumps(token_data),
        "updated_at": now,
    }

    if client:
        client.table("oauth_tokens").upsert(
            record, on_conflict="user_email,provider"
        ).execute()
        return

    key = f"{user_email}::{provider}"
    _MEM["tokens"][key] = record


def load_token(user_email: str, provider: str) -> Optional[dict]:
    """Load stored tokens. Returns None if not connected."""
    client = _get_client()
    if client:
        res = (
            client.table("oauth_tokens")
            .select("token_data")
            .eq("user_email", user_email)
            .eq("provider", provider)
            .execute()
        )
        if res.data:
            return json.loads(res.data[0]["token_data"])
        return None

    key = f"{user_email}::{provider}"
    raw = _MEM["tokens"].get(key)
    return json.loads(raw["token_data"]) if raw else None


def delete_token(user_email: str, provider: str) -> None:
    """Disconnect a provider."""
    client = _get_client()
    if client:
        client.table("oauth_tokens").delete().eq(
            "user_email", user_email
        ).eq("provider", provider).execute()
        return
    _MEM["tokens"].pop(f"{user_email}::{provider}", None)


def is_token_expired(token_data: dict, buffer_seconds: int = 120) -> bool:
    """True if the access token expires within buffer_seconds."""
    expires_at = token_data.get("expires_at", 0)
    return time.time() >= (expires_at - buffer_seconds)


# ══════════════════════════════════════════════════════════════════════════════
#  REPORT HISTORY
# ══════════════════════════════════════════════════════════════════════════════

def save_report(user_email: str, period: str, summary: dict, insights: dict) -> None:
    """Store a generated report for audit trail and history view."""
    client = _get_client()
    record = {
        "user_email": user_email,
        "period": period,
        "summary": json.dumps(summary),
        "insights": json.dumps(insights),
        "generated_at": datetime.utcnow().isoformat(),
    }
    if client:
        client.table("reports").insert(record).execute()
        return
    _MEM["reports"].append(record)


def get_report_history(user_email: str, limit: int = 6) -> list[dict]:
    """Last N reports for a user."""
    client = _get_client()
    if client:
        res = (
            client.table("reports")
            .select("*")
            .eq("user_email", user_email)
            .order("generated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    return [r for r in _MEM["reports"] if r["user_email"] == user_email][-limit:]
