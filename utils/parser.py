"""
utils/parser.py — Smart CSV parser
Auto-detects Xero P&L, Xero GL, QuickBooks, bank statements, and generic CSVs.
"""
import re
import pandas as pd
import numpy as np
from io import StringIO


# ══════════════════════════════════════════════════════════════════════════════
#  FORMAT DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def detect_format(raw: str, df: pd.DataFrame) -> str:
    cols = " ".join(df.columns.tolist()).lower()
    head = raw[:500].lower()

    if "xero" in head or "account code" in cols:
        return "xero"
    if "transaction type" in cols and "split" in cols:
        return "quickbooks"
    if "account type" in cols:
        return "xero_gl"
    if "debit" in cols and "credit" in cols:
        return "bank_debit_credit"
    return "generic"


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN PARSER
# ══════════════════════════════════════════════════════════════════════════════

def parse(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.read().decode("utf-8", errors="ignore")

    # Find the actual header row (skip Xero metadata lines at top)
    lines = raw.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if re.search(r'\bdate\b', line, re.I) and len(line.split(",")) >= 2:
            start = i
            break

    clean = "\n".join(lines[start:])
    df    = pd.read_csv(StringIO(clean), dtype=str)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    fmt = detect_format(raw, df)

    if fmt == "xero":
        return _parse_xero(df)
    if fmt == "xero_gl":
        return _parse_xero_gl(df)
    if fmt == "quickbooks":
        return _parse_quickbooks(df)
    if fmt == "bank_debit_credit":
        return _parse_bank_dc(df)
    return _parse_generic(df)


# ══════════════════════════════════════════════════════════════════════════════
#  FORMAT-SPECIFIC PARSERS
# ══════════════════════════════════════════════════════════════════════════════

def _parse_xero(df: pd.DataFrame) -> pd.DataFrame:
    """Xero Profit & Loss export."""
    cols  = df.columns.tolist()
    date  = _find_col(cols, ["date"])
    cat   = _find_col(cols, ["account_name", "account", "name", "description"])
    amt   = _find_col(cols, ["net_amount", "amount", "net", "total"])
    return _build(df, date, cat, amt)


def _parse_xero_gl(df: pd.DataFrame) -> pd.DataFrame:
    """Xero General Ledger export (has Account Type column)."""
    cols = df.columns.tolist()
    date = _find_col(cols, ["date"])
    cat  = _find_col(cols, ["account_type", "account_name", "account"])
    amt  = _find_col(cols, ["net_amount", "amount", "net"])
    return _build(df, date, cat, amt)


def _parse_quickbooks(df: pd.DataFrame) -> pd.DataFrame:
    """QuickBooks transaction list export."""
    cols = df.columns.tolist()
    date = _find_col(cols, ["date"])
    cat  = _find_col(cols, ["account", "name", "memo", "description"])
    amt  = _find_col(cols, ["amount", "total"])
    return _build(df, date, cat, amt)


def _parse_bank_dc(df: pd.DataFrame) -> pd.DataFrame:
    """Bank statement with separate Debit/Credit columns."""
    cols   = df.columns.tolist()
    date   = _find_col(cols, ["date", "transaction_date", "value_date"])
    cat    = _find_col(cols, ["description", "narration", "particulars", "details", "name"])
    debit  = _find_col(cols, ["debit", "withdrawals", "withdrawal"])
    credit = _find_col(cols, ["credit", "deposits", "deposit"])

    out = pd.DataFrame()
    out["date"]     = pd.to_datetime(df[date], dayfirst=True, errors="coerce") if date else pd.NaT
    out["category"] = df[cat].fillna("Other") if cat else "Other"

    d = df[debit].apply(_to_float) if debit else pd.Series(0.0, index=df.index)
    c = df[credit].apply(_to_float) if credit else pd.Series(0.0, index=df.index)
    out["amount"] = c - d  # credits positive, debits negative

    return _finalise(out)


def _parse_generic(df: pd.DataFrame) -> pd.DataFrame:
    """Fallback for any CSV with date + amount columns."""
    cols = df.columns.tolist()
    date = _find_col(cols, ["date", "transaction_date"])
    cat  = _find_col(cols, ["category", "account", "description",
                             "name", "type", "narration", "memo"])
    amt  = _find_col(cols, ["amount", "value", "net", "total", "sum"])
    return _build(df, date, cat, amt)


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _find_col(cols: list, candidates: list):
    for c in candidates:
        match = next((col for col in cols if c in col), None)
        if match:
            return match
    return None


def _to_float(v) -> float:
    if pd.isna(v):
        return 0.0
    s = str(v).strip().replace(",", "").replace("$", "").replace("S$", "")
    if s.startswith("(") and s.endswith(")"):
        try:
            return -float(s[1:-1])
        except ValueError:
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _build(df, date_col, cat_col, amount_col) -> pd.DataFrame:
    out = pd.DataFrame()
    out["date"]     = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce") if date_col else pd.NaT
    out["category"] = df[cat_col].fillna("Other") if cat_col else "Other"
    out["amount"]   = df[amount_col].apply(_to_float) if amount_col else 0.0
    return _finalise(out)


def _finalise(out: pd.DataFrame) -> pd.DataFrame:
    out["amount_abs"] = out["amount"].abs()
    out["type"]       = np.where(out["amount"] >= 0, "income", "expense")
    out = out.dropna(subset=["date"])
    out = out[out["amount_abs"] > 0]
    out["month"] = out["date"].dt.to_period("M")
    return out.sort_values("date").reset_index(drop=True)
