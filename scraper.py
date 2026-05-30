"""
BD CSE Lecturer Job Tracker — Claude AI Web Search Version
Uses Anthropic API to search — never gets blocked.
Requires: ANTHROPIC_API_KEY in GitHub Secrets
"""

import requests, json, os, hashlib
from datetime import datetime, timezone, timedelta

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "")
DATA_FILE         = "docs/jobs.json"

SEARCH_QUERIES = [
    "lecturer CSE computer science job circular Bangladesh university 2026 deadline",
    "lecturer information technology IT Bangladesh university job circular 2026",
    "BRAC NSU AIUB UIU EWU IUB AUST DIU lecturer CSE job circular 2026",
    "site:bdjobs.com lecturer CSE computer science Bangladesh 2026",
    "site:thefinancialexpress.com lecturer CSE university Bangladesh 2026",
]

SYSTEM_PROMPT = """You are a job search assistant for Bangladesh universities.
Search the web and find REAL, CURRENT CSE/IT Lecturer job postings in Bangladesh.

Return ONLY a valid JSON array. No markdown, no explanation.
Each object must have exactly:
{
  "title": "exact job title from the posting",
  "institution": "university name",
  "deadline": "deadline date e.g. 12 Jun 2026 or N/A",
  "url": "direct URL to the job posting (must be real, start with http)",
  "source": "BDJobs or university name or news source",
  "posted": "posted/published date or empty string"
}

STRICT RULES:
1. Position must be LECTURER or SENIOR LECTURER only (not professor, not admin)
2. Department must be CSE, Computer Science, Information Technology, or Software Engineering
3. University must be in Bangladesh
4. URL must be a real, working link (not homepage, not made up)
5. Job must currently be accepting applications (deadline not passed)
6. Maximum 15 results
7. If no real jobs found, return []
"""


def make_id(title, url):
    return hashlib.md5(f"{title.lower()}{url[:30]}".encode()).hexdigest()[:12]


def load_existing():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"jobs": [], "last_updated": ""}


def save_data(data):
    os.makedirs("docs", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def search_with_claude(query):
    """Use Claude with web_search to find real job postings."""
    if not ANTHROPIC_API_KEY:
        print("  ❌ No ANTHROPIC_API_KEY found in environment")
        return []

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "system": SYSTEM_PROMPT,
                "messages": [{
                    "role": "user",
                    "content": f"Search for: {query}\n\nSearch multiple times to find as many real current postings as possible. Return JSON array only."
                }]
            },
            timeout=60
        )

        if response.status_code != 200:
            print(f"  ❌ API error: {response.status_code} — {response.text[:200]}")
            return []

        data = response.json()
        full_text = "".join(
            block["text"] for block in data.get("content", [])
            if block.get("type") == "text"
        ).strip()

        import re
        match = re.search(r'\[[\s\S]*\]', full_text)
        if not match:
            print(f"  ⚠️  No JSON array in response")
            return []

        jobs = json.loads(match.group())
        valid = [j for j in jobs if j.get("url", "").startswith("http")]
        print(f"  ✅ {len(valid)} jobs found")
        return valid

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return []


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            },
            timeout=10
        )
    except Exception:
        pass


def main():
    print("\n🔍 BD CSE Lecturer Job Tracker — Claude AI Search")
    print("=" * 52)

    all_found = []
    seen_urls = set()

    for i, query in enumerate(SEARCH_QUERIES, 1):
        print(f"\n[{i}/{len(SEARCH_QUERIES)}] {query[:60]}")
        jobs = search_with_claude(query)
        for job in jobs:
            url = job.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                job["id"] = make_id(job.get("title", ""), url)
                job["found_at"] = datetime.now(timezone.utc).isoformat()
                job["notified"] = False
                all_found.append(job)

    print(f"\n📋 Total unique jobs found: {len(all_found)}")

    # Merge with existing
    existing = load_existing()

    # Remove jobs older than 45 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=45)
    existing["jobs"] = [
        j for j in existing["jobs"]
        if datetime.fromisoformat(j.get("found_at", "2000-01-01").replace("Z", "+00:00")).replace(tzinfo=timezone.utc) > cutoff
    ]

    existing_ids  = {j["id"] for j in existing["jobs"]}
    existing_urls = {j["url"] for j in existing["jobs"]}

    added = []
    for job in all_found:
        if job["id"] not in existing_ids and job.get("url") not in existing_urls:
            existing["jobs"].insert(0, job)
            added.append(job)
            existing_ids.add(job["id"])
            existing_urls.add(job.get("url", ""))

    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    existing["jobs"] = existing["jobs"][:300]
    save_data(existing)

    # Save new jobs for notifier
    with open("new_jobs.json", "w", encoding="utf-8") as f:
        json.dump(added, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 52}")
    print(f"✅ New: {len(added)} | Total stored: {len(existing['jobs'])}")
    print(f"{'=' * 52}")

    # Send Telegram for each new job
    if added:
        for job in added:
            dl = f"\n⏰ <b>Deadline:</b> {job['deadline']}" if job.get("deadline") and job["deadline"] != "N/A" else ""
            msg = (
                f"🎓 <b>New CSE/IT Lecturer Job!</b>\n\n"
                f"📌 <b>{job['title']}</b>\n"
                f"🏫 {job['institution']}\n"
                f"🌐 {job['source']}"
                f"{dl}\n"
                f"🔗 <a href='{job['url']}'>View Circular →</a>"
            )
            send_telegram(msg)
            import time; time.sleep(0.8)

        if len(added) >= 3:
            send_telegram(f"📊 <b>Summary:</b> {len(added)} new CSE/IT Lecturer jobs found! 🎉")
    else:
        print("No new jobs this run.")


if __name__ == "__main__":
    main()
