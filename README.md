# SME Co-Pilot — Phase 2

Full-stack AI analytics platform for Singapore SMEs.

**What's new vs Phase 1:**
- Direct Xero & QuickBooks OAuth2 connections (no CSV upload needed)
- Supabase user accounts with secure token storage
- Industry benchmark comparisons (F&B / Retail / Services / General)
- Revenue forecasting (3-month linear regression)
- Break-even analysis
- Category trend sparklines
- Automated weekly HTML email reports (Monday 8am SGT)
- Downloadable HTML report

---

## Quick start

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — add your API keys (see Setup section below)

# 4. Run the app
streamlit run app.py
```

Open http://localhost:8501

---

## Setup guide

### Minimum setup (CSV + rule-based insights — zero cost)
No keys needed. Just run the app and upload a CSV or click "Try with demo data."

### Add GPT-4o insights (~$0.01 per analysis)
1. Go to https://platform.openai.com → API keys
2. Copy your key into `OPENAI_API_KEY` in `.env`

### Add Xero connection (recommended)
1. Go to https://developer.xero.com/myapps → New App
2. App type: **Web App**
3. Redirect URI: `http://localhost:8501/callback/xero` (dev) or `https://yourapp.com/callback/xero` (prod)
4. Copy Client ID and Secret to `.env`

### Add QuickBooks connection
1. Go to https://developer.intuit.com → Dashboard → Create App
2. Select **QuickBooks Online and Payments**
3. Add redirect URI: `http://localhost:8501/callback/qb`
4. Copy Client ID and Secret to `.env`
5. Set `QB_ENV=sandbox` for testing with Intuit's sample company

### Add Supabase (user accounts + persistent token storage)
1. Create free project at https://supabase.com
2. Go to SQL Editor → paste contents of `schema.sql` → Run
3. Go to Settings → API → copy Project URL and `service_role` key to `.env`

### Add email reports
Option A — Resend (easiest, free 100 emails/day):
1. Sign up at https://resend.com
2. Verify your domain
3. Copy API key to `RESEND_API_KEY` in `.env`
4. Set `FROM_EMAIL` to your verified address

Option B — Gmail SMTP:
1. Enable 2FA on your Google account
2. Go to myaccount.google.com/apppasswords → generate app password
3. Set `SMTP_USER`, `SMTP_PASS`, `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=465` in `.env`

---

## Project structure

```
sme_phase2/
├── app.py                    # Main Streamlit application
├── db.py                     # Supabase database layer
├── scheduler.py              # Weekly email automation
├── schema.sql                # Supabase table definitions
├── requirements.txt
├── .env.example              # Copy to .env and fill in keys
│
├── connectors/
│   ├── xero.py               # Xero OAuth2 + data pulling
│   └── quickbooks.py         # QuickBooks OAuth2 + data pulling
│
└── engine/
    ├── analytics.py          # ML models, benchmarks, forecasting
    └── insights.py           # GPT-4o + rule-based insight generator
│
└── email_report/
    └── sender.py             # HTML email renderer + multi-provider sender
```

---

## Running the weekly scheduler

```bash
# Send reports to all users right now (for testing)
python scheduler.py --now

# Send report for one specific user
python scheduler.py --user owner@kimscafe.sg

# Start continuous scheduler (blocks — runs every Monday 08:00 SGT)
python scheduler.py
```

### Deploy on Railway (recommended — free tier)
1. Push to GitHub
2. Connect repo at https://railway.app
3. Add environment variables in Railway dashboard
4. Add a Cron Service with:
   - Schedule: `0 0 * * 1` (Monday 00:00 UTC = 08:00 SGT)
   - Command: `python scheduler.py --now`

### Deploy app on Render (free)
1. Connect GitHub repo at https://render.com
2. Build command: `pip install -r requirements.txt`
3. Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
4. Add environment variables in Render dashboard

---

## Supported CSV formats

| Source | How to export |
|--------|--------------|
| Xero | Reports → Profit & Loss → Export CSV |
| QuickBooks | Reports → Profit & Loss → Export → CSV |
| Bank statement | Download transactions as CSV from your bank |
| Any accounting software | Export general ledger or transaction list as CSV |

---

## Analytics features

| Feature | Description |
|---------|-------------|
| Revenue vs expenses | MoM comparison with % change |
| Net profit & margin | Current period with trend |
| Cash runway | Estimate based on burn rate |
| Anomaly detection | Z-score flagging of unusual expense spikes |
| Revenue forecast | 3-month OLS regression with confidence |
| Break-even analysis | Fixed vs variable cost split |
| Industry benchmarks | vs Singapore SME medians (F&B/Retail/Services) |
| Category trends | 4-month sparklines per expense category |
| AI insights | GPT-4o WIN / ALERT / TIP (or rule-based fallback) |

---

## EntrePass application notes

Your proprietary IP for the application:
1. **ML anomaly detection engine** trained on Singapore SME financial patterns
2. **GPT prompt engineering layer** converting raw financials to actionable insights
3. **Multi-source connector architecture** (Xero + QuickBooks + CSV normalisation)
4. **Singapore-specific industry benchmarks** compiled from local SME data

Frame as: *"Proprietary AI-powered financial intelligence platform for Singapore SMEs,
combining statistical anomaly detection, predictive revenue forecasting,
and LLM-based natural language insight generation."*

---

## Roadmap (Phase 3)

- [ ] Stripe billing (S$199/month)
- [ ] Multi-month comparison view
- [ ] Shopify / Square POS integration
- [ ] WhatsApp alerts via Twilio
- [ ] Customer segmentation (RFM analysis)
- [ ] Tax optimisation tips (GST, corporate tax)
- [ ] White-label for accounting firms

---

*Built with Streamlit · FastAPI · Supabase · OpenAI · Resend*
