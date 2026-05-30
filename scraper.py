"""
BD CSE Lecturer Tracker v7 — Serper API + Direct HTML Scraping
=================================================================
WHY THIS WORKS WHERE OTHERS FAIL:
- BDJobs RSS: 403 from GitHub Actions IPs → REPLACED with Serper search
- Google News RSS: 403 from GitHub Actions → REPLACED with Serper news search  
- University pages: many 403 → kept but with better headers + fallback

SETUP (one-time):
1. Get free Serper API key: https://serper.dev (free: 2500 searches/month)
2. Add to GitHub Secrets as: SERPER_API_KEY
3. That's it. No other API key needed.
"""

import requests, json, os, hashlib, re, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

DATA_FILE      = "docs/jobs.json"
SERPER_KEY     = os.environ.get("SERPER_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_AGE_DAYS = 45

# ── What counts as a valid position ──────────────────────────────────────────
POSITION_WORDS = [
    "lecturer", "senior lecturer", "লেকচারার",
    "assistant professor", "associate professor",
    "faculty position", "faculty member", "open rank",
]

CSE_WORDS = [
    "computer science", "computer science and engineering",
    "computer science & engineering", "cse", "information technology",
    "software engineering", "ict", "computing", "it department",
    "school of data", "computational science", "কম্পিউটার",
]

# Hard-reject noise
REJECT = [
    "faculty list", "faculty of ", "department of", "b.sc in", "m.sc in",
    "admission", "scholarship", "result", "exam", "seminar", "workshop",
    "lakhimpur", "mppsc", "appsc", "jpsc", "uppsc", "india",
    "anna university", "uc san diego", "boston university", "trinity college",
    "united states", "australia", "canada",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def make_id(title, url):
    return hashlib.md5(f"{title.lower()[:50]}{url[:30]}".encode()).hexdigest()[:12]

def is_valid(title, desc=""):
    combined = f"{title} {desc}".lower()
    if len(title) > 220 or len(title) < 8:
        return False
    if any(r in combined for r in REJECT):
        return False
    has_pos = any(w in combined for w in POSITION_WORDS)
    has_cse = any(w in combined for w in CSE_WORDS)
    return has_pos and has_cse

def is_recent(iso, days=MAX_AGE_DAYS):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).days <= days
    except:
        return True

def parse_date(raw):
    try:
        return parsedate_to_datetime(raw).isoformat()
    except:
        return datetime.now(timezone.utc).isoformat()

def extract_deadline(text):
    m = re.search(
        r"(?:deadline|last date|apply by|application deadline)[:\s]+"
        r"([A-Za-z]+ \d{1,2},?\s*\d{4}|\d{1,2}[\s\-][A-Za-z]+[\s\-]\d{4})",
        text, re.I
    )
    return m.group(1).strip() if m else ""

def load_existing():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"jobs": [], "last_updated": ""}

def save(data):
    os.makedirs("docs", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ════════════════════════════════════════════════════════════════════════════
# SOURCE 1 — Serper API (Google Search) — works from ANY IP
# Get free key at serper.dev — 2500 free searches/month
# ════════════════════════════════════════════════════════════════════════════
SERPER_QUERIES = [
    # BDJobs specific — these find actual job listing pages
    'site:bdjobs.com "lecturer" "CSE" OR "computer science" OR "information technology"',
    'site:bdjobs.com "lecturer" "university" Bangladesh 2026',
    'site:bdjobs.com "faculty position" "CSE" OR "computer science" Bangladesh',
    # News searches
    '"lecturer" "CSE" OR "computer science" university Bangladesh circular 2026',
    '"faculty position" "CSE" OR "computer science" Bangladesh university 2026',
    'BRAC university faculty lecturer "computer science" OR "CSE" 2026',
    '"North South" OR "AIUB" OR "UIU" OR "AUST" lecturer CSE 2026',
    '"East West" OR "IUB" OR "ULAB" lecturer "computer science" circular 2026',
]

def scrape_serper():
    if not SERPER_KEY:
        print("  ⚠️  SERPER_API_KEY not set — skipping Serper search")
        print("  → Get free key at https://serper.dev and add to GitHub Secrets")
        return []

    jobs, seen_urls = [], set()
    print("  [Serper Google Search]")

    for query in SERPER_QUERIES:
        try:
            r = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "gl": "bd", "hl": "en", "num": 10},
                timeout=15,
            )
            if r.status_code != 200:
                print(f"    Serper HTTP {r.status_code} for: {query[:50]}")
                continue

            data = r.json()
            results = data.get("organic", []) + data.get("news", [])
            print(f"    {len(results)} results ← {query[:55]}")

            for res in results:
                title   = res.get("title", "").strip()
                url     = res.get("link", "").strip()
                snippet = res.get("snippet", "").strip()
                date_raw = res.get("date", "")

                if not title or not url or url in seen_urls:
                    continue

                clean_title = re.sub(r"\s*[|\-–]\s*[^|\-–]{3,40}$", "", title).strip()

                if not is_valid(clean_title, snippet):
                    continue

                # Parse date — Serper returns relative strings like "2 days ago"
                found_at = datetime.now(timezone.utc).isoformat()
                if date_raw:
                    m = re.search(r"(\d+)\s+day", date_raw)
                    if m:
                        days_ago = int(m.group(1))
                        from datetime import timedelta
                        found_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
                    elif re.search(r"(\d+)\s+hour", date_raw):
                        found_at = datetime.now(timezone.utc).isoformat()
                    elif re.search(r"(\d+)\s+week", date_raw):
                        weeks = int(re.search(r"(\d+)\s+week", date_raw).group(1))
                        from datetime import timedelta
                        found_at = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()

                if not is_recent(found_at):
                    continue

                seen_urls.add(url)
                source = _source_name(url)
                deadline = extract_deadline(snippet)

                print(f"    ✅ {clean_title[:60]}")
                jobs.append({
                    "id":          make_id(clean_title, url),
                    "title":       clean_title,
                    "institution": source,
                    "source":      source,
                    "url":         url,
                    "deadline":    deadline,
                    "found_at":    found_at,
                    "notified":    False,
                })

        except Exception as e:
            print(f"    ERR: {e}")
        time.sleep(0.4)

    print(f"  → {len(jobs)} jobs from Serper")
    return jobs

# ════════════════════════════════════════════════════════════════════════════
# SOURCE 2 — Serper News Search (separate endpoint)
# ════════════════════════════════════════════════════════════════════════════
NEWS_QUERIES = [
    "CSE lecturer job circular Bangladesh university 2026",
    "computer science lecturer vacancy Bangladesh 2026",
    "lecturer information technology Bangladesh university circular",
]

def scrape_serper_news():
    if not SERPER_KEY:
        return []

    jobs, seen_urls = [], set()
    print("  [Serper News Search]")

    for query in NEWS_QUERIES:
        try:
            r = requests.post(
                "https://google.serper.dev/news",
                headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "gl": "bd", "hl": "en", "num": 10},
                timeout=15,
            )
            if r.status_code != 200:
                continue

            for res in r.json().get("news", []):
                title   = res.get("title", "").strip()
                url     = res.get("link", "").strip()
                snippet = res.get("snippet", "").strip()

                if not title or not url or url in seen_urls:
                    continue

                clean_title = re.sub(r"\s*[|\-–]\s*[^|\-–]{3,40}$", "", title).strip()
                if not is_valid(clean_title, snippet):
                    continue

                seen_urls.add(url)
                print(f"    ✅ {clean_title[:60]}")
                jobs.append({
                    "id":          make_id(clean_title, url),
                    "title":       clean_title,
                    "institution": _source_name(url),
                    "source":      _source_name(url),
                    "url":         url,
                    "deadline":    extract_deadline(snippet),
                    "found_at":    datetime.now(timezone.utc).isoformat(),
                    "notified":    False,
                })
        except Exception as e:
            print(f"    ERR: {e}")
        time.sleep(0.4)

    print(f"  → {len(jobs)} jobs from Serper News")
    return jobs

# ════════════════════════════════════════════════════════════════════════════
# SOURCE 3 — Direct University Career Pages (HTML scraping)
# These work better than RSS because we control the parsing
# ════════════════════════════════════════════════════════════════════════════
UNIVERSITIES = [
    {"name": "Ahsanullah Univ (AUST)",         "url": "https://www.aust.edu/career"},
    {"name": "North South University",         "url": "https://www.northsouth.edu/administration/offices/human-resources/job-opportunities.html"},
    {"name": "BRAC University",                "url": "https://www.bracu.ac.bd/about/offices/human-resources/job-opportunities"},
    {"name": "IUB",                            "url": "https://iub.edu.bd/career"},
    {"name": "AIUB",                           "url": "https://www.aiub.edu/career"},
    {"name": "East West University",           "url": "https://www.ewubd.edu/job-circular"},
    {"name": "UIU",                            "url": "https://www.uiu.ac.bd/career/"},
    {"name": "ULAB",                           "url": "https://ulab.edu.bd/career/"},
    {"name": "Daffodil Intl University",       "url": "https://daffodilvarsity.edu.bd/article/career"},
    {"name": "Stamford University",            "url": "https://www.stamforduniversity.edu.bd/job-circular"},
    {"name": "Southeast University",           "url": "https://seu.edu.bd/career/"},
    {"name": "Green University",               "url": "https://green.edu.bd/career/"},
    {"name": "Bangladesh University",          "url": "https://www.bu.edu.bd/job/"},
    {"name": "BUBT",                           "url": "https://www.bubt.edu.bd/home/career"},
    {"name": "Northern University Bangladesh", "url": "https://nub.ac.bd/career/"},
    {"name": "Dhaka University",               "url": "https://www.du.ac.bd/body/notice_list/NTC"},
    {"name": "CUET",                           "url": "https://www.cuet.ac.bd/notice"},
    {"name": "RUET",                           "url": "https://www.ruet.ac.bd/all-notice-circular"},
    {"name": "KUET",                           "url": "https://www.kuet.ac.bd/index.php/notice-circulars/"},
    {"name": "DUET",                           "url": "https://duet.ac.bd/notices/"},
    {"name": "SUST",                           "url": "https://www.sust.edu/4"},
    {"name": "JU",                             "url": "https://www.juniv.edu/notice"},
]

def scrape_universities():
    jobs = []
    print(f"  [{len(UNIVERSITIES)} University Pages]")
    for uni in UNIVERSITIES:
        base = "/".join(uni["url"].split("/")[:3])
        try:
            r = requests.get(uni["url"], headers=HEADERS, timeout=12)
            if r.status_code != 200:
                print(f"    ✗ {uni['name']}: HTTP {r.status_code}")
                continue
            soup = BeautifulSoup(r.content, "lxml")
            found = 0
            for a in soup.find_all("a", href=True):
                title = a.get_text(" ", strip=True)
                href  = a.get("href", "").strip()
                if not href or href in ("#", "javascript:void(0)"):
                    continue
                if len(title) < 8 or len(title) > 200:
                    continue
                full_url = urljoin(base, href) if not href.startswith("http") else href
                if not is_valid(title):
                    continue
                jobs.append({
                    "id":          make_id(title, uni["name"]),
                    "title":       title,
                    "institution": uni["name"],
                    "source":      uni["name"],
                    "url":         full_url,
                    "deadline":    "",
                    "found_at":    datetime.now(timezone.utc).isoformat(),
                    "notified":    False,
                })
                found += 1
            if found:
                print(f"    ✅ {uni['name']}: {found} jobs")
        except Exception as e:
            print(f"    ✗ {uni['name']}: {e}")
        time.sleep(0.3)
    print(f"  → {len(jobs)} jobs from university pages")
    return jobs

# ════════════════════════════════════════════════════════════════════════════
# SOURCE 4 — BDJobs via Serper site: search (no direct RSS needed)
# ════════════════════════════════════════════════════════════════════════════
def scrape_bdjobs_via_serper():
    """Use Serper to search BDJobs specifically — bypasses 403 completely"""
    if not SERPER_KEY:
        return []

    jobs, seen = [], set()
    print("  [BDJobs via Serper site:search]")

    queries = [
        'site:bdjobs.com "lecturer" "computer" OR "CSE" OR "IT" 2026',
        'site:bdjobs.com/details lecturer "computer science" OR "information technology"',
        'site:bdjobs.com faculty lecturer university Bangladesh',
    ]

    for query in queries:
        try:
            r = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "gl": "bd", "num": 10},
                timeout=15,
            )
            if r.status_code != 200:
                continue
            for res in r.json().get("organic", []):
                title   = res.get("title", "").strip()
                url     = res.get("link", "").strip()
                snippet = res.get("snippet", "").strip()

                if "bdjobs.com" not in url or url in seen:
                    continue

                clean_title = re.sub(r"\s*[|\-–]\s*BDjobs.*$", "", title, flags=re.I).strip()
                clean_title = re.sub(r"\s*[|\-–]\s*BD Jobs.*$", "", clean_title, flags=re.I).strip()

                if not is_valid(clean_title, snippet):
                    continue

                seen.add(url)
                print(f"    ✅ BDJobs: {clean_title[:55]}")
                jobs.append({
                    "id":          make_id(clean_title, url),
                    "title":       clean_title,
                    "institution": "BDJobs",
                    "source":      "BDJobs",
                    "url":         url,
                    "deadline":    extract_deadline(snippet),
                    "found_at":    datetime.now(timezone.utc).isoformat(),
                    "notified":    False,
                })
        except Exception as e:
            print(f"    ERR: {e}")
        time.sleep(0.4)

    print(f"  → {len(jobs)} BDJobs results via Serper")
    return jobs

# ────────────────────────────────────────────────────────────────────────────
def _source_name(url):
    u = url.lower()
    if "bdjobs.com"            in u: return "BDJobs"
    if "bracu.ac.bd"           in u: return "BRAC University"
    if "northsouth.edu"        in u: return "North South University"
    if "uiu.ac.bd"             in u: return "UIU"
    if "aiub.edu"              in u: return "AIIB"
    if "ewubd.edu"             in u: return "East West University"
    if "iub.edu.bd"            in u: return "IUB"
    if "aust.edu"              in u: return "AUST"
    if "daffodilvarsity"       in u: return "Daffodil University"
    if "thefinancialexpress"   in u: return "Financial Express"
    if "thedailystar"          in u: return "The Daily Star"
    if "tbsnews"               in u: return "TBS News"
    if "bdnews24"              in u: return "BD News 24"
    if "dhakatribune"          in u: return "Dhaka Tribune"
    if "prothomalo"            in u: return "Prothom Alo"
    if "newagebd"              in u: return "New Age"
    return "Web"

# ════════════════════════════════════════════════════════════════════════════
# Telegram
# ════════════════════════════════════════════════════════════════════════════
def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": False},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"  Telegram error: {r.status_code} — {r.text[:80]}")
    except Exception as e:
        print(f"  Telegram ERR: {e}")

# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
def main():
    print("\n🔍 BD CSE Lecturer Tracker v7")
    print("=" * 52)

    all_found = []

    print("\n📡 SOURCE 1: Serper General Search")
    all_found += scrape_serper()

    print("\n📡 SOURCE 2: Serper News Search")
    all_found += scrape_serper_news()

    print("\n📡 SOURCE 3: University Career Pages")
    all_found += scrape_universities()

    print(f"\n📋 Total valid jobs found: {len(all_found)}")

    # Deduplicate
    existing     = load_existing()
    existing["jobs"] = [j for j in existing["jobs"] if is_recent(j.get("found_at", ""))]
    exist_ids    = {j["id"]  for j in existing["jobs"]}
    exist_urls   = {j["url"] for j in existing["jobs"]}

    added = []
    seen_new = set()
    for job in all_found:
        if job["id"] not in exist_ids and job["url"] not in exist_urls and job["id"] not in seen_new:
            existing["jobs"].insert(0, job)
            added.append(job)
            exist_ids.add(job["id"])
            exist_urls.add(job["url"])
            seen_new.add(job["id"])

    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    existing["jobs"]         = existing["jobs"][:300]
    save(existing)

    with open("new_jobs.json", "w", encoding="utf-8") as f:
        json.dump(added, f, ensure_ascii=False, indent=2)

    print(f"\n✅ New: {len(added)} | Total stored: {len(existing['jobs'])}")

    # Telegram notifications
    for job in added:
        dl  = f"\n⏰ <b>Deadline:</b> {job['deadline']}" if job.get("deadline") else ""
        msg = (
            f"🎓 <b>New CSE/IT Lecturer Job!</b>\n\n"
            f"📌 <b>{job['title']}</b>\n"
            f"🏫 {job['institution']}{dl}\n"
            f"🔗 <a href='{job['url']}'>View Circular →</a>"
        )
        send_telegram(msg)
        time.sleep(0.8)

    if len(added) >= 3:
        send_telegram(
            f"📊 <b>{len(added)} new CSE/IT jobs found!</b> Check your dashboard 🎉"
        )

if __name__ == "__main__":
    main()
