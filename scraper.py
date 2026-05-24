"""
BD Lecturer Job Tracker — v5 STRICT
Only real CSE/IT Lecturer job postings. No nav links. No foreign results. No old jobs.
"""

import requests, json, os, hashlib, time, re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
})

DATA_FILE    = "docs/jobs.json"
MAX_AGE_DAYS = 30   # only show jobs from last 30 days

# ─────────────────────────────────────────────────────────────────────────────
# STRICT FILTER: title must EXPLICITLY be a CSE/IT lecturer job posting
# ─────────────────────────────────────────────────────────────────────────────

# MUST contain at least one of these (it's a hiring post, not a page/list)
HIRING_WORDS = [
    "lecturer", "লেকচারার",
    "assistant professor", "associate professor",
    "adjunct lecturer", "visiting lecturer",
    "faculty position", "faculty opening", "faculty vacancy",
    "job circular", "circular", "vacancy", "recruitment",
    "নিয়োগ বিজ্ঞপ্তি", "শিক্ষক নিয়োগ",
]

# AND must also contain a CSE/IT department signal
CSE_WORDS = [
    "computer science", "computer engineering",
    " cse", "cse ", "(cse)", "cse,", "cse/",
    "information technology", " it ", "(it)",
    "software engineering", "ict", "computing",
    "data science", "artificial intelligence",
    "কম্পিউটার", "তথ্য প্রযুক্তি",
]

# REJECT if title matches any of these — these are nav links / page names, NOT job ads
REJECT_PATTERNS = [
    r"^faculty members?$",
    r"^all faculty",
    r"^faculty list",
    r"^faculty of ",
    r"^faculty & ",
    r"^faculty profile",
    r"^faculty publication",
    r"^visiting faculty members?$",
    r"^department of ",
    r"^dept\.? of ",
    r"^b\.?sc in ",
    r"^m\.?sc in ",
    r"^bachelor",
    r"^master",
    r"official email",
    r"class-3 employment",
    r"application form$",
    r"^বিস্তারিত দেখুন$",
    r"download job description",
    r"faculty & hr",
    r"welcomes \d+ new faculty",
    r"new faculty members join",
    r"ten new",
    r"five new",
    r"campus welcomes",
    r"faculty honored",
    r"recruitment committee",
]

# Reject Google News results from non-BD sources
BD_NEWS_DOMAINS = [
    "thefinancialexpress.com", "thedailystar.net", "bdnews24.com",
    "prothomalo.com", "tbsnews.net", "newagebd.net", "businesspostbd.com",
    "bssnews.net", "bbc.com/bengali", "dhakatribune.com",
    "dailyobserver.net", "theindependentbd.com", "manabzamin.com",
    "samakal.com", "jugantor.com", "kalerkantho.com",
]

def is_bd_source(url: str) -> bool:
    url_lower = url.lower()
    return ".bd/" in url_lower or any(d in url_lower for d in BD_NEWS_DOMAINS)

def is_real_job_posting(title: str) -> bool:
    t = title.strip().lower()

    # reject nav/page links
    for pat in REJECT_PATTERNS:
        if re.search(pat, t):
            return False

    # must be short enough to be a job title (not a paragraph)
    if len(title) > 200:
        return False

    has_hiring = any(w in t for w in HIRING_WORDS)
    has_cse    = any(w in t for w in CSE_WORDS)
    return has_hiring and has_cse

def make_id(title, source):
    return hashlib.md5(f"{title.lower().strip()}{source.lower()}".encode()).hexdigest()[:12]

def is_recent(iso_str: str) -> bool:
    if not iso_str:
        return True
    try:
        dt  = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).days <= MAX_AGE_DAYS
    except Exception:
        return True

def load_existing():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"jobs": [], "last_updated": ""}

def save_data(data):
    os.makedirs("docs", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_html(url, timeout=15):
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return BeautifulSoup(r.content, "lxml")
        print(f"    HTTP {r.status_code} → {url[:55]}")
    except Exception as e:
        print(f"    ERR → {url[:55]} | {e}")
    return None

def get_rss(url, timeout=15):
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return ET.fromstring(r.content)
    except Exception as e:
        print(f"    RSS ERR → {url[:55]} | {e}")
    return None

def parse_pub_date(raw: str) -> str:
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(raw).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()

# ════════════════════════════════════════════════════════════════════════════════
# SOURCE 1 — BDJobs RSS
# ════════════════════════════════════════════════════════════════════════════════
BDJOBS_RSS_URLS = [
    "https://jobs.bdjobs.com/rss/rss.asp?fcat=10",
    "https://jobs.bdjobs.com/rss/rss.asp?txtsearch=lecturer+CSE",
    "https://jobs.bdjobs.com/rss/rss.asp?txtsearch=lecturer+computer",
    "https://jobs.bdjobs.com/rss/rss.asp?txtsearch=lecturer+information+technology",
]

def scrape_bdjobs_rss():
    jobs, seen = [], set()
    print("  [BDJobs RSS]")
    for url in BDJOBS_RSS_URLS:
        root = get_rss(url)
        if not root:
            continue
        items = root.findall(".//item")
        print(f"    {len(items)} items ← {url[-35:]}")
        for item in items:
            title    = (item.findtext("title") or "").strip()
            link     = (item.findtext("link")  or "").strip()
            desc     = (item.findtext("description") or "").strip()
            pub      = (item.findtext("pubDate") or "").strip()
            combined = f"{title} {desc}"

            if not is_real_job_posting(combined):
                continue

            found_at = parse_pub_date(pub)
            if not is_recent(found_at):
                print(f"    ⏭  Old ({found_at[:10]}): {title[:50]}")
                continue

            jid = make_id(title, link)
            if jid in seen: continue
            seen.add(jid)

            soup_d = BeautifulSoup(desc, "lxml")
            inst   = soup_d.get_text(" ", strip=True)[:80] or "BDJobs"
            jobs.append({"id": jid, "title": title, "source": "BDJobs",
                         "institution": inst, "url": link,
                         "found_at": found_at, "notified": False})
        time.sleep(0.5)

    print(f"  → {len(jobs)} valid CSE/IT lecturer jobs from BDJobs")
    return jobs

# ════════════════════════════════════════════════════════════════════════════════
# SOURCE 2 — Google News RSS (Bangladesh ONLY)
# ════════════════════════════════════════════════════════════════════════════════
GNEWS_QUERIES = [
    "lecturer+CSE+university+Bangladesh+circular",
    "assistant+professor+computer+science+Bangladesh+university+circular",
    "lecturer+information+technology+Bangladesh+university+job",
    "CSE+lecturer+job+circular+Bangladesh",
]
GNEWS_BASE = "https://news.google.com/rss/search?q={q}&hl=en-BD&gl=BD&ceid=BD:en"

def scrape_google_news():
    jobs, seen = [], set()
    print("  [Google News RSS — BD only]")
    for q in GNEWS_QUERIES:
        root = get_rss(GNEWS_BASE.format(q=q))
        if not root:
            continue
        items = root.findall(".//item")
        print(f"    {len(items)} items ← {q[:45]}")
        for item in items:
            title    = (item.findtext("title") or "").strip()
            link     = (item.findtext("link")  or "").strip()
            desc     = (item.findtext("description") or "").strip()
            pub      = (item.findtext("pubDate") or "").strip()
            combined = f"{title} {desc}"

            # STRICT: only Bangladesh sources
            if not is_bd_source(link):
                continue

            # STRICT: must be an actual job posting
            if not is_real_job_posting(combined):
                continue

            found_at = parse_pub_date(pub)
            if not is_recent(found_at):
                continue

            jid = make_id(title, link[:30])
            if jid in seen: continue
            seen.add(jid)

            # clean up title (Google News appends " - Source Name")
            clean_title = re.sub(r"\s*-\s*[^-]+$", "", title).strip()

            jobs.append({"id": jid, "title": clean_title, "source": "Google News",
                         "institution": "See link", "url": link,
                         "found_at": found_at, "notified": False})
        time.sleep(0.5)

    print(f"  → {len(jobs)} valid BD items from Google News")
    return jobs

# ════════════════════════════════════════════════════════════════════════════════
# SOURCE 3 — University websites
# ════════════════════════════════════════════════════════════════════════════════
UNIVERSITIES = [
    # Tier 1 Private
    {"name": "North South University",          "url": "https://www.northsouth.edu/administration/offices/human-resources/job-opportunities.html"},
    {"name": "BRAC University",                 "url": "https://www.bracu.ac.bd/about/offices/human-resources/job-opportunities"},
    {"name": "IUB",                             "url": "https://iub.edu.bd/career"},
    {"name": "AIUB",                            "url": "https://www.aiub.edu/career"},
    {"name": "AUST",                            "url": "https://www.aust.edu/career"},
    {"name": "East West University",            "url": "https://www.ewubd.edu/job-circular"},
    {"name": "UIU",                             "url": "https://www.uiu.ac.bd/career/"},
    {"name": "ULAB",                            "url": "https://ulab.edu.bd/career/"},
    {"name": "Daffodil Intl University",        "url": "https://daffodilvarsity.edu.bd/article/career"},
    {"name": "Stamford University",             "url": "https://www.stamforduniversity.edu.bd/job-circular"},
    # Strong Dhaka Private
    {"name": "Southeast University",            "url": "https://seu.edu.bd/career/"},
    {"name": "Prime University",                "url": "https://www.primeuniversity.edu.bd/career/"},
    {"name": "City University",                 "url": "https://cityuniversity.edu.bd/career/"},
    {"name": "Eastern University",              "url": "https://www.easternuni.edu.bd/career/"},
    {"name": "Green University",                "url": "https://green.edu.bd/career/"},
    {"name": "World University of Bangladesh",  "url": "https://wub.edu.bd/career/"},
    {"name": "Bangladesh University",           "url": "https://www.bu.edu.bd/job/"},
    {"name": "Primeasia University",            "url": "https://primeasia.edu.bd/career/"},
    {"name": "UODA",                            "url": "https://uda.ac.bd/career/"},
    # Mid-tier
    {"name": "Manarat Intl University",         "url": "https://manarat.ac.bd/career/"},
    {"name": "Sonargaon University",            "url": "https://su.edu.bd/career/"},
    {"name": "State University of Bangladesh",  "url": "https://sub.edu.bd/career/"},
    {"name": "Northern University Bangladesh",  "url": "https://nub.ac.bd/career/"},
    {"name": "Atish Dipankar University",       "url": "https://adust.edu.bd/career/"},
    {"name": "BUBT",                            "url": "https://www.bubt.edu.bd/home/career"},
    {"name": "BUP",                             "url": "https://www.bup.edu.bd/notice"},
    {"name": "Notre Dame Univ Bangladesh",      "url": "https://ndub.edu.bd/career/"},
    {"name": "Presidency University",           "url": "https://presidency.edu.bd/career/"},
    # Public Universities
    {"name": "Dhaka University",                "url": "https://www.du.ac.bd/body/notice_list/NTC"},
    {"name": "CUET",                            "url": "https://www.cuet.ac.bd/notice"},
    {"name": "RUET",                            "url": "https://www.ruet.ac.bd/all-notice-circular"},
    {"name": "KUET",                            "url": "https://www.kuet.ac.bd/index.php/notice-circulars/"},
    {"name": "DUET",                            "url": "https://duet.ac.bd/notices/"},
    {"name": "SUST",                            "url": "https://www.sust.edu/4"},
    {"name": "JU",                              "url": "https://www.juniv.edu/notice"},
    {"name": "Rajshahi University",             "url": "https://www.ru.ac.bd/notice/"},
    {"name": "Chittagong University",           "url": "https://cu.ac.bd/notice/"},
    {"name": "Khulna University",               "url": "https://www.ku.ac.bd/notice/"},
    {"name": "NSTU",                            "url": "https://nstu.edu.bd/notice/"},
    {"name": "MBSTU",                           "url": "https://www.mbstu.ac.bd/notice"},
    {"name": "Barishal University",             "url": "https://barisaluniv.edu.bd/notice/"},
]

# URLs that are job/career pages — links from here are more likely to be actual postings
JOB_PAGE_SIGNALS = ["career", "job", "vacancy", "circular", "recruit", "notice", "নিয়োগ"]

def scrape_university(uni: dict) -> list:
    jobs, seen = [], set()
    base = "/".join(uni["url"].split("/")[:3])
    soup = get_html(uni["url"])
    if not soup:
        return jobs

    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href  = a.get("href", "").strip()

        if not href or href in ("#", "javascript:void(0)"): continue
        if len(title) < 8 or len(title) > 180:             continue

        full_url = urljoin(base, href) if not href.startswith("http") else href

        # STRICT check on title
        if not is_real_job_posting(title):
            continue

        jid = make_id(title, uni["name"])
        if jid in seen: continue
        seen.add(jid)

        jobs.append({"id": jid, "title": title, "source": uni["name"],
                     "institution": uni["name"], "url": full_url,
                     "found_at": datetime.now(timezone.utc).isoformat(),
                     "notified": False})
    return jobs

# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════
def main():
    all_new = []

    print("\n📡 SOURCE 1: BDJobs RSS")
    all_new += scrape_bdjobs_rss()

    print("\n📡 SOURCE 2: Google News (BD only)")
    all_new += scrape_google_news()

    print(f"\n📡 SOURCE 3: {len(UNIVERSITIES)} Universities")
    for uni in UNIVERSITIES:
        results = scrape_university(uni)
        if results:
            print(f"    ✅ {uni['name']}: {len(results)}")
        all_new += results
        time.sleep(0.35)

    # Prune stale jobs from stored data
    existing = load_existing()
    existing["jobs"] = [j for j in existing["jobs"] if is_recent(j.get("found_at",""))]

    existing_ids = {j["id"] for j in existing["jobs"]}
    added = []
    for job in all_new:
        if job["id"] not in existing_ids:
            existing["jobs"].insert(0, job)
            added.append(job)
            existing_ids.add(job["id"])

    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    existing["jobs"]         = existing["jobs"][:300]
    save_data(existing)

    with open("new_jobs.json", "w", encoding="utf-8") as f:
        json.dump(added, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*55}")
    print(f"✅ Scraped: {len(all_new)} | New: {len(added)} | Stored: {len(existing['jobs'])}")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
