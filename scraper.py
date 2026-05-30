"""
BD CSE/IT Lecturer Tracker v9 — STRICT FILTER
==============================================
ONLY shows:
  ✅ Lecturer / Senior Lecturer positions only
  ✅ CSE / IT / Computer Science / Software Engineering dept only
  ✅ Active jobs (future deadline OR no deadline mentioned)
  ✅ Real job postings from BDJobs + university sites only

REJECTS:
  ❌ EEE, Pharmacy, Nursing, English, MBA, etc.
  ❌ Instagram, Facebook, LinkedIn posts
  ❌ Professor / Assistant Professor / Associate Professor
  ❌ Faculty list pages, vague titles like "We Are Hiring"
  ❌ Jobs with past deadlines
  ❌ Just a university name with no position title
"""

import requests, json, os, hashlib, re, time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

DATA_FILE      = "docs/jobs.json"
SERPER_KEY     = os.environ.get("SERPER_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── ONLY these position words accepted ───────────────────────────────────────
LECTURER_WORDS = [
    "lecturer",
    "senior lecturer",
    "লেকচারার",
    "প্রভাষক",
]

# ── CSE/IT department signals ─────────────────────────────────────────────────
# EEE deliberately NOT here
CSE_WORDS = [
    "computer science and engineering",
    "computer science & engineering",
    "computer science",
    "computer engineering",
    "cse",
    "information technology",
    "software engineering",
    "computing & information",
    "computing and information",
    "computational science",
    "school of data",
    "data science",
    "it department",
    "dept. of cse",
    "dept of cse",
    "কম্পিউটার বিজ্ঞান",
    "তথ্য প্রযুক্তি",
]

# ── Hard reject departments ───────────────────────────────────────────────────
REJECT_DEPT_PATTERNS = [
    r"\beee\b", r"\belectrical\b", r"\belectronics\b", r"\bmechanical\b",
    r"\bcivil\b", r"\btextile\b", r"\bpharmacy\b", r"\bnursing\b",
    r"\bmicrobiology\b", r"\bbiochemistry\b", r"\bbiotechnology\b",
    r"\benglish\b", r"\bbangla\b", r"\bhistory\b", r"\bpolitical\b",
    r"\bsociology\b", r"\beconomics\b", r"\bmathematics\b", r"\bphysics\b",
    r"\bchemistry\b", r"\bbiology\b", r"\bbotany\b", r"\bzoology\b",
    r"\bgeography\b", r"\blaw\b", r"\barchitecture\b", r"\bfinance\b",
    r"\baccounting\b", r"\bmba\b", r"\bbba\b", r"\bbusiness administration\b",
    r"\bmarketing\b", r"\bfashion\b", r"\bnutrition\b", r"\bfood technology\b",
    r"\bagriculture\b", r"\bveterinary\b", r"\bmedicine\b", r"\bdental\b",
    r"\bpublic health\b", r"\bislamic studies\b", r"\barabic\b",
]

# ── Hard reject position/page types ──────────────────────────────────────────
REJECT_TYPE = [
    "professor",        # catches assistant/associate/visiting professor
    "visiting faculty",
    "faculty list",
    "faculty members",
    "faculty of ",
    "faculty profile",
    "faculty & ",
    "we are hiring",
    "now hiring",
    "join our team",
    "current vacancies",
    "open positions",
    "career opportunities",
]

# ── Reject noisy/untrusted sources ───────────────────────────────────────────
REJECT_SOURCE = [
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "linkedin.com",
    "bdjobshour",
    "jobghor24",
    "ejobsbd",
    "bdgovtjob",
    "careerbangladesh",
    "careerzonebangladesh",
    "chakri.com.bd",
    "jobcircularbd",
    "bdcircular",
]

# ── Vague title patterns ──────────────────────────────────────────────────────
VAGUE_TITLE = [
    r"^[a-z][a-z\s\.]+ university bangladesh?$",
    r"^[a-z][a-z\s\.]+ university$",
    r"^[a-z][a-z\s\.]+ college$",
    r"^#\w",
    r"^we are hiring$",
    r"^now hiring$",
    r"^eee[-\s]?lec",
    r"^\w{1,5}$",
]

def make_id(title, url):
    return hashlib.md5(f"{title.lower()[:60]}{url[:30]}".encode()).hexdigest()[:12]

def has_lecturer(text):
    t = text.lower()
    return any(w in t for w in LECTURER_WORDS)

def has_professor(text):
    return "professor" in text.lower()

def has_cse(text):
    t = text.lower()
    return any(w in t for w in CSE_WORDS)

def is_bad_dept(text):
    t = text.lower()
    return any(re.search(p, t) for p in REJECT_DEPT_PATTERNS)

def is_bad_type(text):
    t = text.lower()
    return any(r in t for r in REJECT_TYPE)

def is_bad_source(url):
    u = url.lower()
    return any(s in u for s in REJECT_SOURCE)

def is_vague_title(title):
    t = title.strip().lower()
    for pat in VAGUE_TITLE:
        if re.match(pat, t):
            return True
    return False

def deadline_is_past(text):
    """True if a deadline is explicitly mentioned AND already passed today."""
    months = {
        "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
        "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12
    }
    today = datetime.now(timezone.utc).date()
    patterns = [
        r"(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,]+(\d{4})",
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})",
        r"deadline[:\s]+(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,]+(\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text.lower())
        if m:
            try:
                g = m.groups()
                if g[0].isdigit():
                    day, mon, yr = int(g[0]), months[g[1][:3]], int(g[2])
                else:
                    mon, day, yr = months[g[0][:3]], int(g[1]), int(g[2])
                if datetime(yr, mon, day).date() < today:
                    return True
            except:
                pass
    return False

def is_valid_job(title, desc="", url="", is_bdjobs=False):
    """
    Core validation. Returns True only for real active CSE/IT Lecturer postings.
    is_bdjobs=True relaxes CSE check slightly since BDJobs category filter already
    ensures education/lecturer context.
    """
    if not title or len(title) < 6 or len(title) > 220:
        return False

    # Source check
    if is_bad_source(url):
        return False

    # Vague title
    if is_vague_title(title):
        return False

    combined = f"{title} {desc}"

    # Wrong dept
    if is_bad_dept(title):   # title only — desc might mention other depts
        return False

    # Wrong position type
    if is_bad_type(combined):
        return False

    # Must have lecturer word, must NOT have professor
    if not has_lecturer(combined):
        return False
    if has_professor(title):  # title only — "Lecturer & Assistant Professor" in title = reject
        return False

    # CSE check:
    # For BDJobs URLs: if title has any CSE word OR desc has CSE word → accept
    # For other URLs: combined must have CSE word
    if is_bdjobs:
        if not has_cse(combined):
            return False
    else:
        if not has_cse(combined):
            return False

    # Past deadline
    if deadline_is_past(combined):
        return False

    return True

def is_recent(iso, days=45):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).days <= days
    except:
        return True

def extract_deadline(text):
    m = re.search(
        r"(?:deadline|last date|apply by)[:\s]+"
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

def _source_name(url):
    u = url.lower()
    mapping = {
        "bdjobs.com":          "BDJobs",
        "bracu.ac.bd":         "BRAC University",
        "northsouth.edu":      "North South University",
        "uiu.ac.bd":           "UIU",
        "aiub.edu":            "AIUB",
        "ewubd.edu":           "East West University",
        "iub.edu.bd":          "IUB",
        "aust.edu":            "AUST",
        "daffodilvarsity":     "Daffodil University",
        "thefinancialexpress": "Financial Express",
        "thedailystar":        "The Daily Star",
        "tbsnews":             "TBS News",
        "bdnews24":            "BD News 24",
        "dhakatribune":        "Dhaka Tribune",
    }
    for k, v in mapping.items():
        if k in u:
            return v
    # Only accept .bd domains
    if ".bd/" in u or ".bd" == u[-3:]:
        return "Web"
    return None  # None = untrusted, skip

def _parse_serper_date(raw):
    now = datetime.now(timezone.utc)
    if not raw:
        return now.isoformat()
    if m := re.search(r"(\d+)\s+day", raw):
        return (now - timedelta(days=int(m.group(1)))).isoformat()
    if re.search(r"\d+\s+hour", raw):
        return now.isoformat()
    if m := re.search(r"(\d+)\s+week", raw):
        return (now - timedelta(weeks=int(m.group(1)))).isoformat()
    return now.isoformat()

# ════════════════════════════════════════════════════════════════════════════
# SOURCE 1 — Serper: BDJobs + trusted BD news (bypasses 403)
# ════════════════════════════════════════════════════════════════════════════
SERPER_QUERIES = [
    'site:bdjobs.com "lecturer" "computer science" OR "cse" 2026',
    'site:bdjobs.com "lecturer" "information technology" OR "software engineering" 2026',
    'site:bdjobs.com "senior lecturer" university Bangladesh 2026',
    'site:bdjobs.com "BRAC" lecturer "computer science" OR "cse" 2026',
    'site:bdjobs.com "lecturer" "school of data" OR "computational" 2026',
    'site:bdjobs.com "lecturer" university Bangladesh 2026',
    '"lecturer" "computer science" OR "CSE" Bangladesh university circular 2026 site:thefinancialexpress.com.bd OR site:thedailystar.net OR site:tbsnews.net',
    '"lecturer" "information technology" Bangladesh university 2026 -site:instagram.com -site:facebook.com -site:linkedin.com',
]

def scrape_serper():
    if not SERPER_KEY:
        print("  ⚠️  SERPER_API_KEY missing — get free key at serper.dev")
        return []

    jobs, seen = [], set()
    print("  [Serper]")

    for query in SERPER_QUERIES:
        try:
            r = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                json={"q": query, "gl": "bd", "hl": "en", "num": 10},
                timeout=15,
            )
            if r.status_code != 200:
                print(f"    {r.status_code}: {query[:45]}")
                continue

            accepted = 0
            for res in r.json().get("organic", []):
                title    = res.get("title",   "").strip()
                url      = res.get("link",    "").strip()
                snippet  = res.get("snippet", "").strip()
                date_raw = res.get("date",    "")

                if not title or not url or url in seen:
                    continue

                # Clean title suffixes
                clean = re.sub(r"\s*[-|–]\s*(BDJobs|BD Jobs|bdjobs\.com).*$", "", title, flags=re.I).strip()
                clean = re.sub(r"\s*:\s*(BDJobs|BD Jobs).*$", "", clean, flags=re.I).strip()

                # Determine trusted source
                source = _source_name(url)
                if source is None:
                    continue

                is_bdj = "bdjobs.com" in url.lower()
                if not is_valid_job(clean, snippet, url, is_bdjobs=is_bdj):
                    continue

                found_at = _parse_serper_date(date_raw)
                if not is_recent(found_at):
                    continue

                seen.add(url)
                accepted += 1
                print(f"    ✅ {clean[:60]}")
                jobs.append({
                    "id":          make_id(clean, url),
                    "title":       clean,
                    "institution": source,
                    "source":      source,
                    "url":         url,
                    "deadline":    extract_deadline(f"{clean} {snippet}"),
                    "found_at":    found_at,
                    "notified":    False,
                })

            print(f"    {accepted} accepted ← {query[:50]}")

        except Exception as e:
            print(f"    ERR: {e}")
        time.sleep(0.4)

    print(f"  → {len(jobs)} from Serper")
    return jobs

# ════════════════════════════════════════════════════════════════════════════
# SOURCE 2 — University career pages
# ════════════════════════════════════════════════════════════════════════════
UNIVERSITIES = [
    {"name": "AUST",                           "url": "https://www.aust.edu/career"},
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
    {"name": "City University",                "url": "https://cityuniversity.edu.bd/career/"},
    {"name": "Eastern University",             "url": "https://www.easternuni.edu.bd/career/"},
    {"name": "Prime University",               "url": "https://www.primeuniversity.edu.bd/career/"},
    {"name": "Dhaka University",               "url": "https://www.du.ac.bd/body/notice_list/NTC"},
    {"name": "CUET",                           "url": "https://www.cuet.ac.bd/notice"},
    {"name": "RUET",                           "url": "https://www.ruet.ac.bd/all-notice-circular"},
    {"name": "KUET",                           "url": "https://www.kuet.ac.bd/index.php/notice-circulars/"},
    {"name": "DUET",                           "url": "https://duet.ac.bd/notices/"},
    {"name": "SUST",                           "url": "https://www.sust.edu/4"},
    {"name": "JU",                             "url": "https://www.juniv.edu/notice"},
    {"name": "NSTU",                           "url": "https://nstu.edu.bd/notice/"},
]

def _get_text(url, timeout=10):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return BeautifulSoup(r.content, "lxml").get_text(" ", strip=True)
    except:
        pass
    return ""

def scrape_universities():
    jobs = []
    print(f"  [{len(UNIVERSITIES)} University Pages]")

    for uni in UNIVERSITIES:
        base = "/".join(uni["url"].split("/")[:3])
        try:
            r = requests.get(uni["url"], headers=HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.content, "lxml")
            found = 0

            for a in soup.find_all("a", href=True):
                title = a.get_text(" ", strip=True)
                href  = a.get("href", "").strip()

                if not href or href.startswith("#") or "javascript" in href:
                    continue
                if len(title) < 5 or len(title) > 200:
                    continue

                # Must have lecturer word in link text
                if not has_lecturer(title):
                    continue
                # Must NOT have professor
                if has_professor(title):
                    continue
                # Must not be bad dept in title
                if is_bad_dept(title):
                    continue

                full_url = urljoin(base, href) if not href.startswith("http") else href

                # If title already confirms CSE → accept directly
                if has_cse(title) and not deadline_is_past(title):
                    pass

                # Generic "Lecturer" with no dept → fetch detail page
                else:
                    detail = _get_text(full_url)
                    if not detail:
                        continue
                    if not has_cse(detail):
                        continue
                    if deadline_is_past(detail):
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
                time.sleep(0.25)

            if found:
                print(f"    ✅ {uni['name']}: {found}")

        except Exception as e:
            print(f"    ✗ {uni['name']}: {e}")
        time.sleep(0.3)

    print(f"  → {len(jobs)} from university pages")
    return jobs

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
            print(f"  Telegram {r.status_code}: {r.text[:80]}")
    except Exception as e:
        print(f"  Telegram ERR: {e}")

# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
def main():
    print(f"\n🔍 BD CSE/IT Lecturer Tracker v9")
    print(f"   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 55)

    all_found = []

    print("\n📡 SOURCE 1: Serper (BDJobs + trusted BD sites)")
    all_found += scrape_serper()

    print("\n📡 SOURCE 2: University Career Pages")
    all_found += scrape_universities()

    print(f"\n📋 Valid jobs this run: {len(all_found)}")

    # Load existing, remove expired/past-deadline jobs
    existing = load_existing()

    def keep(j):
        if not is_recent(j.get("found_at", "")):
            return False
        dl = j.get("deadline", "")
        if dl and deadline_is_past(dl):
            return False
        return True

    existing["jobs"] = [j for j in existing["jobs"] if keep(j)]

    exist_ids  = {j["id"]  for j in existing["jobs"]}
    exist_urls = {j["url"] for j in existing["jobs"]}

    added, seen_new = [], set()
    for job in all_found:
        if (job["id"]  not in exist_ids  and
            job["url"] not in exist_urls and
            job["id"]  not in seen_new):
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

    print(f"✅ New: {len(added)} | Active stored: {len(existing['jobs'])}")

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
            f"📊 <b>{len(added)} new CSE/IT Lecturer jobs found!</b> Check dashboard 🎉"
        )

if __name__ == "__main__":
    main()
