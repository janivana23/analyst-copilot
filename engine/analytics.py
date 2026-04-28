"""
engine/analytics.py — Core analytics engine

Computes all financial metrics, ML models, and benchmarks.
Works on both CSV-uploaded DataFrames and API-pulled summary dicts.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  SINGAPORE SME BENCHMARKS
#  Sources: SPRING Singapore, MAS, Enterprise Singapore reports
# ══════════════════════════════════════════════════════════════════════════════

SG_BENCHMARKS = {
    "F&B": {
        "net_margin":     {"p25": 3.0,  "median": 8.0,  "p75": 14.0},
        "labour_pct":     {"p25": 28.0, "median": 35.0, "p75": 42.0},
        "rent_pct":       {"p25": 8.0,  "median": 12.0, "p75": 18.0},
        "food_cost_pct":  {"p25": 28.0, "median": 33.0, "p75": 38.0},
        "revenue_growth": {"p25": -3.0, "median": 5.0,  "p75": 15.0},
    },
    "Retail": {
        "net_margin":     {"p25": 2.0,  "median": 6.0,  "p75": 12.0},
        "labour_pct":     {"p25": 15.0, "median": 22.0, "p75": 30.0},
        "rent_pct":       {"p25": 10.0, "median": 15.0, "p75": 22.0},
        "cogs_pct":       {"p25": 45.0, "median": 55.0, "p75": 65.0},
        "revenue_growth": {"p25": -2.0, "median": 4.0,  "p75": 12.0},
    },
    "Services": {
        "net_margin":     {"p25": 8.0,  "median": 18.0, "p75": 30.0},
        "labour_pct":     {"p25": 40.0, "median": 55.0, "p75": 68.0},
        "rent_pct":       {"p25": 3.0,  "median": 7.0,  "p75": 12.0},
        "revenue_growth": {"p25": 0.0,  "median": 8.0,  "p75": 20.0},
    },
    "General": {
        "net_margin":     {"p25": 4.0,  "median": 10.0, "p75": 18.0},
        "labour_pct":     {"p25": 25.0, "median": 38.0, "p75": 50.0},
        "rent_pct":       {"p25": 5.0,  "median": 10.0, "p75": 16.0},
        "revenue_growth": {"p25": -2.0, "median": 6.0,  "p75": 15.0},
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  CORE SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def compute_summary(df: pd.DataFrame) -> dict:
    """
    Full financial summary from a normalised transaction DataFrame.
    Returns metrics for current month vs previous month.
    """
    if df.empty:
        return {}

    latest_month = df["month"].max()
    prev_month   = latest_month - 1

    cur  = df[df["month"] == latest_month]
    prev = df[df["month"] == prev_month]

    cur_rev   = _sum_type(cur, "income")
    prev_rev  = _sum_type(prev, "income")
    cur_exp   = _sum_type(cur, "expense")
    prev_exp  = _sum_type(prev, "expense")
    net       = cur_rev - cur_exp
    prev_net  = prev_rev - prev_exp
    margin    = (net / cur_rev * 100) if cur_rev > 0 else 0.0

    top_exp = (
        cur[cur["type"] == "expense"]
        .groupby("category")["amount_abs"]
        .sum()
        .sort_values(ascending=False)
        .head(8)
        .to_dict()
    )

    # Monthly trends (last 6 months)
    rev_trend = (
        df[df["type"] == "income"]
        .groupby("month")["amount_abs"].sum()
        .tail(6)
    )
    exp_trend = (
        df[df["type"] == "expense"]
        .groupby("month")["amount_abs"].sum()
        .tail(6)
    )

    # Category trends (MoM for each expense category)
    cat_trends = {}
    for cat in top_exp:
        cat_df = df[(df["category"] == cat) & (df["type"] == "expense")]
        monthly = cat_df.groupby("month")["amount_abs"].sum().tail(4)
        cat_trends[cat] = [round(float(v), 2) for v in monthly.values]

    # Detect highest-spend day of week
    cur_copy = cur.copy()
    cur_copy["dow"] = cur_copy["date"].dt.day_name()
    best_dow = (
        cur_copy[cur_copy["type"] == "income"]
        .groupby("dow")["amount_abs"].sum()
        .idxmax()
        if not cur_copy[cur_copy["type"] == "income"].empty else "N/A"
    )

    return {
        "period":            str(latest_month),
        "revenue":           round(cur_rev, 2),
        "prev_revenue":      round(prev_rev, 2),
        "revenue_change":    _pct(cur_rev, prev_rev),
        "expenses":          round(cur_exp, 2),
        "prev_expenses":     round(prev_exp, 2),
        "expenses_change":   _pct(cur_exp, prev_exp),
        "net_profit":        round(net, 2),
        "prev_profit":       round(prev_net, 2),
        "profit_change":     _pct(net, prev_net),
        "profit_margin":     round(margin, 1),
        "top_expenses":      top_exp,
        "revenue_trend":     [round(float(v), 2) for v in rev_trend.values],
        "expense_trend":     [round(float(v), 2) for v in exp_trend.values],
        "trend_labels":      [str(p) for p in rev_trend.index],
        "category_trends":   cat_trends,
        "transaction_count": len(cur),
        "best_revenue_day":  best_dow,
    }


def _sum_type(df: pd.DataFrame, type_: str) -> float:
    return float(df[df["type"] == type_]["amount_abs"].sum())


def _pct(new: float, old: float) -> float:
    if old == 0:
        return 0.0
    return round((new - old) / abs(old) * 100, 1)


# ══════════════════════════════════════════════════════════════════════════════
#  ANOMALY DETECTION  (z-score, no external ML library needed)
# ══════════════════════════════════════════════════════════════════════════════

def detect_anomalies(df: pd.DataFrame, z_threshold: float = 1.5) -> list[dict]:
    """
    Flag categories where this month's spend is z_threshold SDs above
    their historical mean.  Returns anomalies sorted by severity.
    """
    anomalies = []
    latest_month = df["month"].max()
    expenses = df[df["type"] == "expense"]

    for cat, grp in expenses.groupby("category"):
        monthly = grp.groupby("month")["amount_abs"].sum()
        if len(monthly) < 3:
            continue

        history = monthly[monthly.index < latest_month]
        current = monthly.get(latest_month, None)
        if current is None or len(history) < 2:
            continue

        mean = float(history.mean())
        std  = float(history.std())
        if std == 0:
            continue

        z = (float(current) - mean) / std
        if z > z_threshold:
            anomalies.append({
                "category":   cat,
                "current":    round(float(current), 2),
                "average":    round(mean, 2),
                "change_pct": round((float(current) - mean) / mean * 100, 1),
                "z_score":    round(z, 2),
                "severity":   "high" if z > 2.5 else "medium",
            })

    return sorted(anomalies, key=lambda x: x["z_score"], reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
#  REVENUE FORECAST  (linear regression, no sklearn needed)
# ══════════════════════════════════════════════════════════════════════════════

def forecast_revenue(monthly_revenue: list[float], periods: int = 3) -> dict:
    """
    Simple OLS linear regression on monthly revenue.
    Returns trend direction, next-N-month forecasts, and R².
    """
    n = len(monthly_revenue)
    if n < 3:
        return {"trend": "insufficient data", "forecasts": [], "r2": 0.0}

    x = np.arange(n, dtype=float)
    y = np.array(monthly_revenue, dtype=float)

    # OLS
    x_mean, y_mean = x.mean(), y.mean()
    slope     = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
    intercept = y_mean - slope * x_mean

    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r2     = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    forecasts = [
        round(max(0, float(intercept + slope * (n + i))), 2)
        for i in range(periods)
    ]

    monthly_change = slope
    trend = (
        "growing strongly" if slope > y_mean * 0.05 else
        "growing steadily" if slope > 0 else
        "declining" if slope < -y_mean * 0.02 else
        "flat"
    )

    return {
        "trend":          trend,
        "monthly_change": round(float(monthly_change), 2),
        "forecasts":      forecasts,
        "r2":             round(float(r2), 3),
        "confidence":     "high" if r2 > 0.7 else "medium" if r2 > 0.4 else "low",
    }


# ══════════════════════════════════════════════════════════════════════════════
#  CASH FLOW RUNWAY
# ══════════════════════════════════════════════════════════════════════════════

def compute_runway(
    summary: dict,
    cash_balance: float = 0.0,
    receivables: float = 0.0,
) -> dict:
    """
    Estimate cash runway. If no balance sheet data, uses net profit as proxy.
    """
    monthly_burn = summary.get("expenses", 0)
    monthly_rev  = summary.get("revenue", 0)
    net          = monthly_rev - monthly_burn

    # Use provided cash, or estimate from net profit buffer
    effective_cash = cash_balance if cash_balance > 0 else max(net * 1.5, 0)
    effective_cash += receivables * 0.8   # assume 80% of receivables will be collected

    runway_days = int(effective_cash / monthly_burn * 30) if monthly_burn > 0 else 999
    runway_days = min(runway_days, 365)   # cap display at 1 year

    if runway_days >= 90:
        status, advice = "green", "Healthy. Consider reinvesting surplus."
    elif runway_days >= 45:
        status, advice = "amber", "Monitor closely. Build a 3-month buffer."
    else:
        status, advice = "red", "Urgent. Review expenses and chase receivables now."

    return {
        "status":      status,
        "days":        runway_days,
        "label":       f"{runway_days}+ days" if runway_days >= 365 else f"~{runway_days} days",
        "advice":      advice,
        "monthly_net": round(net, 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  BENCHMARK COMPARISON
# ══════════════════════════════════════════════════════════════════════════════

def benchmark(summary: dict, industry: str = "General") -> list[dict]:
    """
    Compare this business's KPIs against Singapore SME industry benchmarks.
    Returns list of benchmark result dicts.
    """
    bench = SG_BENCHMARKS.get(industry, SG_BENCHMARKS["General"])
    results = []

    rev = summary.get("revenue", 0)
    exp = summary.get("expenses", 0)
    net = summary.get("net_profit", 0)

    # Net margin
    margin = (net / rev * 100) if rev > 0 else 0
    bm     = bench.get("net_margin", {})
    results.append(_bm_row("Net profit margin", f"{margin:.1f}%",
                            margin, bm, higher_is_better=True, unit="%"))

    # Labour as % of revenue
    labour = sum(v for k, v in summary.get("top_expenses", {}).items()
                 if any(w in k.lower() for w in ("staff", "salary", "wage", "labour", "labor", "payroll")))
    labour_pct = (labour / rev * 100) if rev > 0 else 0
    bm = bench.get("labour_pct", {})
    if labour > 0:
        results.append(_bm_row("Labour cost %", f"{labour_pct:.1f}%",
                                labour_pct, bm, higher_is_better=False, unit="%"))

    # Rent as % of revenue
    rent = sum(v for k, v in summary.get("top_expenses", {}).items()
               if "rent" in k.lower())
    rent_pct = (rent / rev * 100) if rev > 0 else 0
    bm = bench.get("rent_pct", {})
    if rent > 0:
        results.append(_bm_row("Rent %", f"{rent_pct:.1f}%",
                                rent_pct, bm, higher_is_better=False, unit="%"))

    # Revenue growth
    rev_chg = summary.get("revenue_change", 0)
    bm = bench.get("revenue_growth", {})
    results.append(_bm_row("Revenue growth (MoM)", f"{rev_chg:+.1f}%",
                            rev_chg, bm, higher_is_better=True, unit="%"))

    return [r for r in results if r is not None]


def _bm_row(label, display, value, bm, higher_is_better, unit):
    if not bm:
        return None
    p25, med, p75 = bm.get("p25", 0), bm.get("median", 0), bm.get("p75", 0)

    if higher_is_better:
        if value >= p75:
            rating, colour = "Top 25%", "green"
        elif value >= med:
            rating, colour = "Above median", "teal"
        elif value >= p25:
            rating, colour = "Below median", "amber"
        else:
            rating, colour = "Bottom 25%", "red"
    else:
        if value <= p25:
            rating, colour = "Lean (top 25%)", "green"
        elif value <= med:
            rating, colour = "Near median", "teal"
        elif value <= p75:
            rating, colour = "Above median", "amber"
        else:
            rating, colour = "High cost", "red"

    return {
        "label":    label,
        "value":    display,
        "rating":   rating,
        "colour":   colour,
        "median":   f"{med}{unit}",
        "p25":      f"{p25}{unit}",
        "p75":      f"{p75}{unit}",
    }


# ══════════════════════════════════════════════════════════════════════════════
#  BREAK-EVEN CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

def break_even(summary: dict) -> dict:
    """
    Estimate monthly break-even revenue.
    Splits expenses into fixed (rent, salaries) and variable (COGS, supplies).
    """
    top_exp = summary.get("top_expenses", {})
    rev     = summary.get("revenue", 1)

    fixed_keywords    = ("rent", "salary", "salaries", "staff", "wage", "insurance", "loan")
    variable_keywords = ("ingredient", "supply", "supplies", "cogs", "cost of goods",
                         "packaging", "delivery", "commission")

    fixed_costs    = sum(v for k, v in top_exp.items()
                        if any(w in k.lower() for w in fixed_keywords))
    variable_costs = sum(v for k, v in top_exp.items()
                        if any(w in k.lower() for w in variable_keywords))
    other_costs    = sum(top_exp.values()) - fixed_costs - variable_costs

    # Assume other costs split 50/50
    fixed_costs    += other_costs * 0.5
    variable_costs += other_costs * 0.5

    variable_ratio  = variable_costs / rev if rev > 0 else 0.5
    contribution_margin = 1 - variable_ratio
    break_even_rev  = (fixed_costs / contribution_margin) if contribution_margin > 0 else 0

    return {
        "break_even_revenue": round(break_even_rev, 2),
        "fixed_costs":        round(fixed_costs, 2),
        "variable_costs":     round(variable_costs, 2),
        "contribution_margin": round(contribution_margin * 100, 1),
        "above_break_even":   rev >= break_even_rev,
        "buffer":             round(rev - break_even_rev, 2),
    }
