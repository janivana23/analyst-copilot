# SME Co-Pilot v2 — Multi-page App

Professional financial analytics for Singapore SMEs.
3 pages: Dashboard · Reports history · Settings

## Features
- **Dashboard** — revenue, expenses, profit, health score, benchmarks,
  forecasting, break-even, anomaly detection
- **Reports** — saved report history with full insights
- **Settings** — Gmail email, WhatsApp (Twilio), OpenAI, saved to disk
- **Smart CSV parser** — auto-detects Xero, QuickBooks, bank formats
- **Beautiful HTML email** — professional report sent via Gmail
- **WhatsApp reports** — instant summary via Twilio

## Setup

```bash
# 1. Unzip and enter folder
cd sme_v2

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 3. Install packages
pip install -r requirements.txt

# 4. Run
streamlit run app.py
```

Open http://localhost:8501

## Getting your CSV

**Xero:** Accounting → Reports → Profit & Loss → Export CSV

**QuickBooks:** Reports → Profit & Loss → Export → CSV

**Bank:** Download transactions as CSV

The parser auto-detects the format.

## Email setup (Gmail)

1. Enable 2FA: myaccount.google.com/security
2. Get app password: myaccount.google.com/apppasswords
3. Go to Settings page in the app → fill in Gmail + app password → Save

## WhatsApp setup (Twilio)

1. Sign up at twilio.com (free $15 credit)
2. Go to Messaging → Try it out → Send a WhatsApp message
3. Follow Twilio's sandbox setup
4. Copy Account SID, Auth Token, WhatsApp number to Settings page

## Deploy to Railway

```bash
git init && git add . && git commit -m "SME Co-Pilot v2"
git push origin main
```

Railway → New Project → Deploy from GitHub
Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

Note: On Railway, the `sme_data/` folder for settings/history resets on redeploy.
For persistent storage, add a Supabase database later.
