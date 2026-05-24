# 🎓 Incoming Call: Future Students (BD CSE/IT Lecturer Job Tracker)

Auto-fetches lecturer/faculty job postings from **40+ Bangladesh universities** + **BDJobs** every 3 hours. Sends **Telegram notifications** for new circulars and hosts a live **dashboard** on GitHub Pages — completely free.

---

## ✅ Features

- Scrapes BDJobs for `lecturer CSE / IT / Computer Science` positions
- Checks notice/career pages of **40+ public & private universities**
- Sends instant **Telegram message** when a new circular is found
- Auto-deploys a **live dashboard website** (GitHub Pages, free)
- Runs automatically every **3 hours** via GitHub Actions
- You can also trigger it manually anytime

---

## 🚀 Setup Guide (Step by Step)

### Step 1 — Create your GitHub repo

1. Go to [github.com](https://github.com) → **New Repository**
2. Name it: `bd-lecturer-tracker`
3. Set to **Public** (required for free GitHub Pages)
4. Click **Create Repository**

### Step 2 — Upload all project files

Upload these files to your repo root:
```
scraper.py
notifier.py
build_dashboard.py
requirements.txt
.github/workflows/scrape.yml
```

You can drag-and-drop files on GitHub's web UI.

### Step 3 — Create a Telegram Bot (takes 2 minutes)

1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Give it a name (e.g., `BD Lecturer Alerts`)
4. Give it a username (e.g., `bd_lecturer_bot`)
5. BotFather will send you a **token** like:
   ```
   7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
   Save this — it's your `TELEGRAM_BOT_TOKEN`

6. Now get your Chat ID:
   - Start your bot (send `/start` to it)
   - Open this URL in browser:
     ```
     https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
     ```
   - Look for `"chat":{"id": 123456789}` — that number is your `TELEGRAM_CHAT_ID`

### Step 4 — Add secrets to GitHub

In your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add two secrets:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your bot token from Step 3 |
| `TELEGRAM_CHAT_ID` | Your chat ID from Step 3 |

### Step 5 — Enable GitHub Pages

1. Repo → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` → Folder: `/docs`
4. Click **Save**

Your dashboard will be live at:
```
https://YOUR_USERNAME.github.io/bd-lecturer-tracker
```

### Step 6 — Run it for the first time

1. Go to **Actions** tab in your repo
2. Click **BD Lecturer Job Tracker** workflow
3. Click **Run workflow** → **Run workflow**

It will scrape everything, send Telegram notifications, and deploy your dashboard!

---

## 📱 What you'll get

Every time a new CSE/IT lecturer circular is found, you'll receive a Telegram message like:

```
🎓 New Lecturer Job Found!

📌 Lecturer - Department of CSE
🏫 North South University
🌐 Source: NSU Website
🔗 View Circular → [link]
🕒 Found: 2025-06-01
```

---

## 🏫 Universities Monitored

**Public:** BUET, DU, CUET, RUET, KUET, DUET, SUST, JU, RU, CU, KU, COU, NSTU, PUST, MBSTU, HSTU, Barishal Univ, BRUR, RMSTU...

**Private:** BRAC, NSU, AIUB, DIU, UIU, EWU, IUB, AUST, Southeast, Stamford, Green, Metropolitan, Premier, IUBAT, BGC Trust, BAUST, Leading, Port City, Sylhet International, Manarat, Primeasia, Uttara, Victoria, World University...

---

## 🔧 Customization

**Add more universities:** Edit `UNIVERSITIES` list in `scraper.py`

**Change schedule:** Edit the cron in `.github/workflows/scrape.yml`
- Every 3 hours: `"0 */3 * * *"`
- Every 6 hours: `"0 */6 * * *"`
- Twice daily:   `"0 8,20 * * *"`

**Add more keywords:** Edit `CSE_KEYWORDS` list in `scraper.py`

---

## 💡 Tips

- Bookmark your GitHub Pages URL — it auto-refreshes every 30 minutes
- You can pin the Telegram bot chat to get job alerts instantly
- GitHub Actions gives **2,000 free minutes/month** — running every 3 hours uses ~720 min/month ✅

---

*Built for fresh CS graduates in Bangladesh 🇧🇩*
