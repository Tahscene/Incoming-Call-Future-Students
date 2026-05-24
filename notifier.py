"""
Notifier v2 — only sends Telegram for NEW, recent CSE/IT Lecturer jobs.
"""
import json, os, requests
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Missing credentials")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r   = requests.post(url, json={
        "chat_id":                  TELEGRAM_CHAT_ID,
        "text":                     text,
        "parse_mode":               "HTML",
        "disable_web_page_preview": False,
    }, timeout=10)
    return r.status_code == 200

def format_job(job):
    found = job.get("found_at", "")[:10]
    return (
        f"🎓 <b>New CSE/IT Lecturer Job!</b>\n\n"
        f"📌 <b>{job['title']}</b>\n"
        f"🏫 {job['institution']}\n"
        f"🌐 Source: {job['source']}\n"
        f"📅 Posted: {found}\n"
        f"🔗 <a href='{job['url']}'>View Circular →</a>"
    )

def main():
    try:
        with open("new_jobs.json", encoding="utf-8") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        print("new_jobs.json not found")
        return

    if not jobs:
        print("No new CSE/IT lecturer jobs to notify.")
        return

    print(f"📬 Sending {len(jobs)} notification(s)...")
    sent = 0
    for job in jobs:
        if send_telegram(format_job(job)):
            sent += 1
        # small delay between messages
        import time; time.sleep(0.8)

    print(f"✅ {sent}/{len(jobs)} messages sent")

    if len(jobs) >= 3:
        send_telegram(
            f"📊 <b>Summary:</b> {len(jobs)} new CSE/IT Lecturer postings found!\n"
            f"Check your dashboard for details. 🎉"
        )

if __name__ == "__main__":
    main()
