"""
utils/styles.py — Shared CSS injected on every page.
"""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1rem 2rem 2rem; }

.hero {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
    border-radius: 16px; padding: 1.8rem 2.2rem; margin-bottom: 1.4rem;
    display: flex; justify-content: space-between; align-items: center;
}
.hero h1 { color: #fff; font-size: 1.5rem; font-weight: 700; margin: 0 0 4px; }
.hero p  { color: #94a3b8; font-size: 0.83rem; margin: 0; }
.hero-badge {
    text-align: center; background: rgba(255,255,255,0.1);
    border-radius: 12px; padding: 0.9rem 1.4rem; min-width: 80px;
}
.hero-badge .grade { font-size: 2rem; font-weight: 700; line-height: 1; }
.hero-badge .grade-label { font-size: 0.68rem; color: #94a3b8;
    text-transform: uppercase; letter-spacing: 0.08em; margin-top: 3px; }

[data-testid="metric-container"] {
    background: #fff; border: 1px solid #e5e7eb;
    border-radius: 12px; padding: 1rem 1.2rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
[data-testid="stMetricValue"] { font-size: 1.55rem !important; font-weight: 700 !important; }

.sec { font-size: 0.7rem; font-weight: 700; color: #9ca3af;
    text-transform: uppercase; letter-spacing: 0.09em;
    margin: 1.4rem 0 0.7rem; padding-bottom: 0.4rem;
    border-bottom: 1px solid #f0f0f0; }

.ins { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
    padding: 1rem 1.2rem; margin-bottom: 0.7rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.ins.g { border-left: 4px solid #22c55e; }
.ins.r { border-left: 4px solid #ef4444; }
.ins.b { border-left: 4px solid #3b82f6; }
.ins-lbl { font-size: 0.67rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.08em; margin-bottom: 0.3rem; }
.ins-lbl.g { color: #16a34a; }
.ins-lbl.r { color: #dc2626; }
.ins-lbl.b { color: #2563eb; }
.ins-txt { font-size: 0.88rem; color: #374151; line-height: 1.65; margin: 0; }

.pill { font-size: 0.67rem; font-weight: 700; padding: 2px 8px;
    border-radius: 99px; display: inline-block; }
.pg { background: #dcfce7; color: #166534; }
.pa { background: #fef3c7; color: #92400e; }
.pr { background: #fef2f2; color: #991b1b; }
.pt { background: #e0f2fe; color: #0369a1; }

.bm-row { display: flex; justify-content: space-between; align-items: center;
    padding: 7px 0; border-bottom: 1px solid #f3f4f6; font-size: 0.83rem; }

.anom { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px;
    padding: 10px 14px; margin-bottom: 6px; font-size: 0.85rem; }

.rp { display: inline-block; padding: 3px 12px; border-radius: 99px;
    font-size: 0.78rem; font-weight: 700; }
.rp-g { background: #dcfce7; color: #166534; }
.rp-a { background: #fef3c7; color: #92400e; }
.rp-r { background: #fef2f2; color: #991b1b; }

.fc-box { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 10px;
    padding: 12px 16px; font-size: 0.84rem; color: #0c4a6e; margin-top: 8px; }

.report-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
    padding: 1rem 1.2rem; margin-bottom: 0.7rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04); }

.stButton > button { background: #1a1a2e; color: #fff; border: none;
    border-radius: 8px; font-weight: 500; }
.stButton > button:hover { background: #16213e; }
</style>
"""
