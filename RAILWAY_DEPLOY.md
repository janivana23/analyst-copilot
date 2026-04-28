# Railway Deployment Guide — SME Co-Pilot

Complete step-by-step instructions for deploying on Railway.
Estimated time: 20–30 minutes.

---

## What you'll set up

| Service | Purpose | Cost |
|---------|---------|------|
| Web app | The Streamlit dashboard users visit | ~$5/month on Railway Hobby |
| Cron job | Sends weekly Monday 8am reports | Included |
| Supabase | Database for users + OAuth tokens | Free tier |

---

## Part 1 — Push code to GitHub

### Step 1.1 — Create a GitHub repo

1. Go to https://github.com/new
2. Name it `sme-copilot` (or anything you like)
3. Set to **Private** (your API keys will be in Railway env vars, not the code)
4. Click **Create repository**

### Step 1.2 — Push your code

In your project folder (where `app.py` lives):

```bash
git init
git add .
git commit -m "Initial commit — SME Co-Pilot Phase 2"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/sme-copilot.git
git push -u origin main
```

Double-check `.gitignore` includes `.env` — never push your secret keys.

---

## Part 2 — Deploy the Streamlit app on Railway

### Step 2.1 — Create the project

1. Go to https://railway.app → **New Project**
2. Click **Deploy from GitHub repo**
3. Connect your GitHub account if not already connected
4. Select your `sme-copilot` repo
5. Railway will detect the `Procfile` / `railway.toml` automatically

### Step 2.2 — Add environment variables

In Railway dashboard → your project → **Variables** tab, add:

```
# Required for the app to work
OPENAI_API_KEY          = sk-...

# Required for Supabase (get from supabase.com → Settings → API)
SUPABASE_URL            = https://xxxx.supabase.co
SUPABASE_KEY            = eyJ...

# Required for email reports (get from resend.com → API Keys)
RESEND_API_KEY          = re_...
FROM_EMAIL              = reports@yourdomain.com

# Add these only after registering at developer.xero.com
XERO_CLIENT_ID          = (leave blank for now)
XERO_CLIENT_SECRET      = (leave blank for now)
XERO_REDIRECT_URI       = https://YOUR-APP.up.railway.app/callback/xero

# Add after registering at developer.intuit.com
QB_CLIENT_ID            = (leave blank for now)
QB_CLIENT_SECRET        = (leave blank for now)
QB_REDIRECT_URI         = https://YOUR-APP.up.railway.app/callback/qb
QB_ENV                  = sandbox
```

**Important:** After Railway deploys, copy the generated URL (e.g. `https://sme-copilot-production.up.railway.app`) and update `XERO_REDIRECT_URI` and `QB_REDIRECT_URI` with it.

### Step 2.3 — Set the start command

Railway should auto-read `railway.toml`, but verify:

1. Go to your service → **Settings** tab
2. Under **Deploy** → **Start Command**, confirm it shows:
   ```
   streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
   ```
3. If not, paste it in manually

### Step 2.4 — Generate a public domain

1. Go to your service → **Settings** → **Networking**
2. Click **Generate Domain**
3. You'll get a URL like `sme-copilot-production.up.railway.app`
4. That's your live app URL — share it with SME customers

### Step 2.5 — Verify it's running

Click the domain URL. You should see the SME Co-Pilot dashboard. Click "Try with demo data" to confirm everything works.

---

## Part 3 — Set up the weekly email cron job

This runs `scheduler.py --now` every Monday at 08:00 SGT (00:00 UTC).

### Step 3.1 — Add a Cron Service in Railway

1. In your Railway project, click **+ New** → **Empty Service**
2. Name it `scheduler`
3. Go to **Settings** → **Deploy**
4. Set **Start Command** to:
   ```
   python scheduler.py --now
   ```
5. Under **Cron Schedule**, enter:
   ```
   0 0 * * 1
   ```
   (This is `00:00 UTC` every Monday = `08:00 SGT`)

### Step 3.2 — Share environment variables

The scheduler service needs the same env vars as the web app.

Option A (easiest): In the scheduler service → **Variables** → click **Add Reference** → select your web service → all variables are shared automatically.

Option B: Copy-paste the same variables into the scheduler service.

### Step 3.3 — Test the cron manually

In the scheduler service → **Deployments** → click **Trigger Deploy**.

Check the logs — you should see:
```
Starting weekly reports for N users
Report sent + saved for user@example.com
Done — 1 sent, 0 failed
```

If you see `No data source for user — skipping`, that user isn't connected to Xero/QuickBooks yet (expected during setup).

---

## Part 4 — Register Xero OAuth app

Do this after the app is live (you need the Railway URL for the redirect).

### Step 4.1 — Register at Xero Developer

1. Go to https://developer.xero.com/myapps
2. Click **New App**
3. Fill in:
   - **App name**: SME Co-Pilot (or your brand name)
   - **Company or application URL**: your Railway URL
   - **OAuth 2.0 redirect URI**: `https://YOUR-APP.up.railway.app/callback/xero`
4. Click **Create App**
5. Copy **Client ID** and **Client Secret**
6. Paste into Railway → Variables → `XERO_CLIENT_ID` and `XERO_CLIENT_SECRET`
7. Redeploy (Railway auto-redeploys on variable change)

### Step 4.2 — Test the Xero connection

1. Open your app
2. Enter your email in the sidebar
3. Click **Connect Xero**
4. You'll be redirected to Xero login
5. After approving, you'll be redirected back and see "Xero connected!"

---

## Part 5 — Register QuickBooks OAuth app

### Step 5.1 — Create app at Intuit Developer

1. Go to https://developer.intuit.com → **Dashboard** → **Create an App**
2. Select **QuickBooks Online and Payments**
3. Name it `SME Co-Pilot`
4. Under **Keys & OAuth**, add redirect URI:
   `https://YOUR-APP.up.railway.app/callback/qb`
5. Copy **Client ID** and **Client Secret**
6. Paste into Railway → Variables → `QB_CLIENT_ID` and `QB_CLIENT_SECRET`

### Step 5.2 — Test with sandbox first

Set `QB_ENV=sandbox` in Railway variables. Intuit provides a pre-populated sandbox company at https://developer.intuit.com → **Sandbox Companies** — use it to test without real data.

When ready for real use: change `QB_ENV=production`.

---

## Part 6 — Set up Supabase database

### Step 6.1 — Create Supabase project

1. Go to https://supabase.com → **New Project**
2. Choose a region close to Singapore: `Southeast Asia (Singapore)`
3. Note your database password — you won't need it directly but save it

### Step 6.2 — Create the tables

1. Go to your Supabase project → **SQL Editor**
2. Copy the contents of `schema.sql` (in your project folder)
3. Paste and click **Run**
4. You should see: `users`, `oauth_tokens`, `reports` tables created

### Step 6.3 — Get your API keys

1. Go to **Settings** → **API**
2. Copy:
   - **Project URL** → paste as `SUPABASE_URL` in Railway
   - **service_role** key (under Secret) → paste as `SUPABASE_KEY` in Railway

⚠️ Use the `service_role` key (not the `anon` key) — the scheduler needs full DB access.

---

## Part 7 — Set up email with Resend

### Step 7.1 — Sign up and verify domain

1. Go to https://resend.com → sign up (free)
2. **Domains** → **Add Domain** → enter your domain (e.g. `yourbusiness.com`)
3. Add the DNS records Resend provides to your domain registrar (Namecheap, GoDaddy, etc.)
4. Wait 5–15 minutes for DNS to propagate → click **Verify**

### Step 7.2 — Create API key

1. Resend → **API Keys** → **Create API Key**
2. Copy it → paste as `RESEND_API_KEY` in Railway
3. Set `FROM_EMAIL` to `reports@yourdomain.com` (must match verified domain)

### Step 7.3 — Test email

1. Open your deployed app
2. Enter a real email in the sidebar
3. Upload the sample CSV or use demo data
4. Click **Send test email report**
5. Check your inbox — should arrive within 30 seconds

---

## Part 8 — Custom domain (optional but professional)

Railway gives you `your-app.up.railway.app` for free. To use your own domain:

1. Railway → your web service → **Settings** → **Networking** → **Custom Domain**
2. Enter your domain: `app.yourbusiness.com`
3. Add the CNAME record Railway shows to your DNS registrar
4. Wait for DNS → Railway auto-provisions an SSL certificate

Update `XERO_REDIRECT_URI` and `QB_REDIRECT_URI` to use your custom domain.

---

## Troubleshooting

**App crashes on startup**
- Check Railway logs (Deployments → click latest deployment → View Logs)
- Most common cause: missing env var. Confirm all required vars are set.

**"ModuleNotFoundError" in logs**
- `requirements.txt` didn't install correctly
- Go to Railway → Settings → Redeploy → watch build logs for pip errors

**Xero/QuickBooks redirect fails**
- Confirm `XERO_REDIRECT_URI` in Railway exactly matches the URI registered in Xero developer portal (including https://, no trailing slash)

**Scheduler runs but sends no emails**
- Check `RESEND_API_KEY` is set correctly
- Confirm FROM_EMAIL domain is verified in Resend
- Check scheduler logs for the error message

**Cron doesn't run**
- Verify cron syntax: `0 0 * * 1` (minute hour day month weekday)
- Railway cron uses UTC — `0 0 * * 1` = Monday 00:00 UTC = Monday 08:00 SGT ✓

---

## Cost estimate (Railway Hobby plan — $5/month)

| Resource | Usage | Cost |
|----------|-------|------|
| Web service | Always-on Streamlit app | ~$3/month |
| Cron service | Runs once per week | ~$0.10/month |
| Supabase | Free tier (500MB, plenty) | $0 |
| Resend | Free tier (100 emails/day) | $0 until ~100 customers |
| OpenAI | ~$0.01–0.02 per analysis | Minimal |
| **Total** | | **~$5–8/month** |

You'll be charging customers S$199/month each. One customer covers your infrastructure for 4 months.

---

## Quick reference — useful commands

```bash
# Test the scheduler locally before deploying
python scheduler.py --now

# Test for one specific user
python scheduler.py --user owner@kimscafe.sg

# Check if env vars loaded correctly
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY','NOT SET')[:8])"

# Deploy a new version (after code changes)
git add . && git commit -m "Update" && git push
# Railway auto-redeploys on every git push
```
