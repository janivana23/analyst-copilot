"""
utils/analytics.py — Core analytics engine shared across all pages.
"""
import numpy as np
import pandas as pd

BENCHMARKS = {
    "F&B":      {"net_margin": (3, 8, 14),  "labour_pct": (28, 35, 42), "rent_pct": (8, 12, 18)},
    "Retail":   {"net_margin": (2, 6, 12),  "labour_pct": (15, 22, 30), "rent_pct": (10, 15, 22)},
    "Services": {"net_margin": (8, 18, 30), "labour_pct": (40, 55, 68), "rent_pct": (3, 7, 12)},
    "General":  {"net_margin": (4, 10, 18), "labour_pct": (25, 38, 50), "rent_pct": (5, 10, 16)},
}


def analyse(df: pd.DataFrame) -> dict:
    latest = df["month"].max()
    prev   = latest - 1
    cur    = df[df["month"] == latest]
    prv    = df[df["month"] == prev]

    def si(d, t): return float(d[d["type"] == t]["amount_abs"].sum())
    def pc(n, o): return round((n - o) / abs(o) * 100, 1) if o else 0.0

    rev = si(cur, "income");  pv_rev = si(prv, "income")
    exp = si(cur, "expense"); pv_exp = si(prv, "expense")
    net    = rev - exp
    margin = round(net / rev * 100, 1) if rev else 0.0

    top_exp = (
        cur[cur["type"] == "expense"]
        .groupby("category")["amount_abs"].sum()
        .sort_values(ascending=False).head(6).to_dict()
    )

    rev_trend = df[df["type"] == "income"].groupby("month")["amount_abs"].sum().tail(6)
    exp_trend = df[df["type"] == "expense"].groupby("month")["amount_abs"].sum().tail(6)

    # Anomalies
    anomalies = []
    for cat, grp in df[df["type"] == "expense"].groupby("category"):
        monthly = grp.groupby("month")["amount_abs"].sum()
        if len(monthly) < 3:
            continue
        hist    = monthly[monthly.index < latest]
        cur_val = monthly.get(latest)
        if cur_val is None or len(hist) < 2:
            continue
        mean, std = float(hist.mean()), float(hist.std())
        if std == 0:
            continue
        z = (float(cur_val) - mean) / std
        if z > 1.5:
            anomalies.append(dict(
                category=cat,
                current=round(float(cur_val), 2),
                average=round(mean, 2),
                change_pct=round((float(cur_val) - mean) / mean * 100, 1),
                z=round(z, 2),
            ))

    # Forecast
    rv = [float(v) for v in rev_trend.values]
    fc = []
    if len(rv) >= 3:
        x         = np.arange(len(rv), dtype=float)
        slope     = np.polyfit(x, rv, 1)[0]
        intercept = np.mean(rv) - slope * np.mean(x)
        fc = [max(0, round(intercept + slope * (len(rv) + i), 2)) for i in range(3)]

    return dict(
        period=str(latest),
        revenue=round(rev, 2), pv_rev=round(pv_rev, 2), rev_chg=pc(rev, pv_rev),
        expenses=round(exp, 2), pv_exp=round(pv_exp, 2), exp_chg=pc(exp, pv_exp),
        net=round(net, 2), margin=margin,
        top_exp=top_exp,
        rev_trend=[round(float(v), 2) for v in rev_trend.values],
        exp_trend=[round(float(v), 2) for v in exp_trend.values],
        trend_labels=[str(p) for p in rev_trend.index],
        anomalies=sorted(anomalies, key=lambda x: x["z"], reverse=True),
        forecast=fc,
        tx_count=len(cur),
    )


def health_score(s: dict, ind: str) -> tuple:
    score = 100
    bm = BENCHMARKS.get(ind, BENCHMARKS["General"])
    p25_m, med_m, _ = bm["net_margin"]
    if s["margin"] < p25_m:   score -= 30
    elif s["margin"] < med_m: score -= 15
    if s["rev_chg"] < -5:     score -= 20
    elif s["rev_chg"] < 0:    score -= 10
    score -= 10 * min(len(s["anomalies"]), 2)
    if s["net"] < 0:           score -= 15
    score = max(score, 0)
    if score >= 80: return "A", score, "#22c55e", "Healthy"
    if score >= 60: return "B", score, "#eab308", "Good"
    if score >= 40: return "C", score, "#f97316", "Watch out"
    return "D", score, "#ef4444", "Critical"


def get_runway(s: dict) -> tuple:
    exp  = s["expenses"]
    cash = max(s["net"] * 1.5, 0)
    days = min(int(cash / exp * 30), 365) if exp > 0 else 999
    status = "g" if days >= 90 else "a" if days >= 45 else "r"
    label  = f"{days}+ days" if days >= 365 else f"~{days} days"
    return status, label


def break_even(s: dict) -> dict:
    top = s["top_exp"]
    rev = s["revenue"] or 1
    fixed_kw = ("rent", "salary", "salaries", "staff", "wage", "insurance")
    var_kw   = ("ingredient", "supply", "supplies", "cogs", "packaging", "delivery")
    fixed = sum(v for k, v in top.items() if any(w in k.lower() for w in fixed_kw))
    var   = sum(v for k, v in top.items() if any(w in k.lower() for w in var_kw))
    other = sum(top.values()) - fixed - var
    fixed += other * 0.5
    var   += other * 0.5
    cm  = max(1 - var / rev, 0.01)
    be  = round(fixed / cm, 2)
    buf = round(rev - be, 2)
    return dict(be=be, fixed=round(fixed, 2), var=round(var, 2),
                cm=round(cm * 100, 1), above=rev >= be, buffer=buf)


def get_benchmarks(s: dict, ind: str) -> list:
    bm  = BENCHMARKS.get(ind, BENCHMARKS["General"])
    rev = s["revenue"] or 1
    top = s["top_exp"]
    rows = []

    def rate(val, p25, med, p75, higher_good):
        if higher_good:
            if val >= p75: return "Top 25%", "pg"
            if val >= med: return "Above median", "pt"
            if val >= p25: return "Below median", "pa"
            return "Bottom 25%", "pr"
        else:
            if val <= p25: return "Lean (top 25%)", "pg"
            if val <= med: return "Near median", "pt"
            if val <= p75: return "Above median", "pa"
            return "High cost", "pr"

    p25, med, p75 = bm["net_margin"]
    lbl, cls = rate(s["margin"], p25, med, p75, True)
    rows.append(dict(name="Net profit margin", val=f"{s['margin']:.1f}%",
                     label=lbl, cls=cls, median=f"{med}%"))

    labour = sum(v for k, v in top.items()
                 if any(w in k.lower() for w in ("staff", "salary", "wage", "labour", "payroll")))
    if labour:
        lp = labour / rev * 100
        p25, med, p75 = bm["labour_pct"]
        lbl, cls = rate(lp, p25, med, p75, False)
        rows.append(dict(name="Labour cost", val=f"{lp:.1f}%",
                         label=lbl, cls=cls, median=f"{med}%"))

    rent = sum(v for k, v in top.items() if "rent" in k.lower())
    if rent:
        rp = rent / rev * 100
        p25, med, p75 = bm["rent_pct"]
        lbl, cls = rate(rp, p25, med, p75, False)
        rows.append(dict(name="Rent cost", val=f"{rp:.1f}%",
                         label=lbl, cls=cls, median=f"{med}%"))

    lbl, cls = rate(s["rev_chg"], -2, 6, 15, True)
    rows.append(dict(name="Revenue growth (MoM)", val=f"{s['rev_chg']:+.1f}%",
                     label=lbl, cls=cls, median="+6%"))
    return rows


def get_insights(s: dict, anomalies: list, biz: str, ind: str, key: str = "") -> dict:
    if key:
        try:
            from openai import OpenAI
            top  = "\n".join(f"  {c}: S${v:,.0f}" for c, v in list(s["top_exp"].items())[:5])
            anom = (f"\nANOMALY: {anomalies[0]['category']} S${anomalies[0]['current']:,.0f}"
                    f" (+{anomalies[0]['change_pct']:.0f}%)" if anomalies else "")
            prompt = (f"Singapore SME advisor. Specific numbers, no jargon.\n"
                      f"{biz} ({ind}) {s['period']}: Revenue S${s['revenue']:,.0f} "
                      f"({s['rev_chg']:+.1f}%), Net S${s['net']:,.0f} ({s['margin']:.1f}%){anom}\n"
                      f"Costs:\n{top}\nWIN: ...\nALERT: ...\nTIP: ...\n2-3 sentences each.")
            client = OpenAI(api_key=key)
            resp   = client.chat.completions.create(
                model="gpt-4o", temperature=0.2, max_tokens=450,
                messages=[{"role": "user", "content": prompt}])
            import re
            raw    = resp.choices[0].message.content
            result = {}
            for k2 in ("WIN", "ALERT", "TIP"):
                m = re.search(rf"{k2}:\s*(.+?)(?=(?:WIN:|ALERT:|TIP:|$))", raw, re.DOTALL | re.I)
                if m:
                    result[k2.lower()] = m.group(1).strip()
            if all(k2 in result for k2 in ("win", "alert", "tip")):
                return result
        except Exception:
            pass

    # Rule-based
    rev = s["revenue"]; exp = s["expenses"]; net = s["net"]
    margin = s["margin"]; rev_chg = s["rev_chg"]; top = s["top_exp"]
    fc = s.get("forecast", [])

    if rev_chg >= 10:
        win = (f"Revenue surged {rev_chg:+.1f}% to S${rev:,.0f} — best month in this dataset. "
               f"Identify what drove this and replicate it next month.")
    elif net > 0 and margin >= 12:
        win = (f"Strong {margin:.1f}% profit margin — S${net:,.0f} net on S${rev:,.0f} revenue. "
               f"Top quartile for Singapore {ind} businesses.")
    elif rev_chg >= 0:
        win = (f"Revenue held at S${rev:,.0f} — expenses at {exp/rev*100:.0f}% of revenue, under control.")
    else:
        win = (f"Full financial visibility is a real advantage. "
               f"Use this data to make one pricing or cost decision this week.")

    if anomalies:
        a = anomalies[0]
        alert = (f"{a['category']} jumped to S${a['current']:,.0f} — "
                 f"+{a['change_pct']:.0f}% above usual S${a['average']:,.0f}. "
                 f"Review every transaction in that category today.")
    elif margin < 8:
        alert = (f"Margin is {margin:.1f}% — below the Singapore {ind} median of ~10%. "
                 f"A 5-8% price increase on top sellers adds ~S${rev*0.06:,.0f}/month.")
    else:
        top_cat = list(top.keys())[0] if top else "expenses"
        top_amt = list(top.values())[0] if top else 0
        alert = (f"No critical alerts this month. "
                 f"Watch {top_cat} at S${top_amt:,.0f} — worth reviewing quarterly.")

    if fc and len(fc) >= 1:
        direction = "grow" if fc[0] > rev else "decline"
        tip = (f"Revenue forecast to {direction} to S${fc[0]:,.0f} next month. "
               f"{'Contact top 3 customers with a loyalty offer this week.' if direction == 'grow' else 'Chase all outstanding invoices and defer non-essential spend now.'}")
    elif top:
        cat, amt = list(top.items())[0]
        tip = (f"Top expense is {cat} at S${amt:,.0f}/month. "
               f"A 7% cut saves S${amt*0.07*12:,.0f}/year — call your supplier today.")
    else:
        tip = "Set a 15-min finance check every Monday: bank balance, invoices, biggest expense."

    return dict(win=win, alert=alert, tip=tip)


def make_demo() -> pd.DataFrame:
    import numpy as np
    from datetime import datetime
    rng   = np.random.default_rng(42)
    today = datetime.today()
    rows  = []
    for m in range(6, -1, -1):
        ms  = today.replace(day=1) - pd.DateOffset(months=m)
        for _ in range(rng.integers(15, 22)):
            rows.append(dict(date=ms + pd.DateOffset(days=int(rng.integers(0, 27))),
                             category="Revenue",
                             amount=round(float(rng.uniform(900, 3200)), 2)))
        rows.append(dict(date=ms, category="Rent", amount=-8500.0))
        rows.append(dict(date=ms + pd.DateOffset(days=28), category="Staff costs",
                         amount=round(-float(rng.uniform(18000, 22000)), 2)))
        ing = 9000 if m > 0 else 14200
        rows.append(dict(date=ms + pd.DateOffset(days=5), category="Ingredients",
                         amount=round(-float(rng.uniform(ing * 0.9, ing * 1.1)), 2)))
        rows.append(dict(date=ms + pd.DateOffset(days=14), category="Utilities",
                         amount=round(-float(rng.uniform(1200, 1800)), 2)))
        if rng.random() > 0.4:
            rows.append(dict(date=ms + pd.DateOffset(days=int(rng.integers(1, 20))),
                             category="Marketing",
                             amount=round(-float(rng.uniform(400, 1400)), 2)))
    df = pd.DataFrame(rows)
    df["date"]       = pd.to_datetime(df["date"])
    df["amount_abs"] = df["amount"].abs()
    df["type"]       = np.where(df["amount"] >= 0, "income", "expense")
    df["month"]      = df["date"].dt.to_period("M")
    return df.sort_values("date").reset_index(drop=True)
