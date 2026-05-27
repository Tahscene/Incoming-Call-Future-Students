"""
BD CSE/IT Lecturer Job Tracker — Final Version
Sources:
  1. BDJobs API (JSON endpoint — no JS rendering needed)
  2. Google News RSS (BD sources only)
  3. University career pages
"""

import requests, json, os, hashlib, time, re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://bdjobs.com/",
})

DATA_FILE    = "docs/jobs.json"
MAX_AGE_DAYS = 30

# ── Strict keyword filters ────────────────────────────────────────────────────
LECTURER_KW = ["lecturer", "লেকচারার", "senior lecturer"]

CSE_KW = [
    "computer science", "computer engineering",
    " cse", "cse ", "(cse)", "cse,", "cse/", "/cse",
    "information technology", "software engineering",
    "data science", "artificial intelligence", "ict",
    "কম্পিউটার", "তথ্য প্রযুক্তি",
]

REJECT_TITLES = [
    r"^faculty members?$", r"^all faculty", r"^faculty list",
    r"^faculty of ", r"^faculty & ", r"^faculty profile",
    r"^visiting faculty members?$", r"^department of ", r"^dept\.? of ",
    r"^b\.?sc in ", r"^m\.?sc in ", r"^bachelor", r"official email",
    r"application form$", r"^বিস্তারিত দেখুন$", r"faculty honored",
    r"new faculty members join", r"welcomes \d+ new", r"recruitment committee",
]

BD_NEWS_DOMAINS = [
    "thefinancialexpress.com", "thedailystar.net", "bdnews24.com",
    "prothomalo.com", "tbsnews.net", "newagebd.net", "dhakatribune.com",
    "dailyobserver.net", "theindependentbd.com", "bssnews.net",
]

def is_lecturer(t):    return any(k in t.lower() for k in LECTURER_KW)
def is_cse(t):         return any(k in t.lower() for k in CSE_KW)
def is_rejected(t):    return any(re.search(p, t.lower()) for p in REJECT_TITLES)
def is_bd_url(url):    return ".bd/" in url.lower() or any(d in url.lower() for d in BD_NEWS_DOMAINS)

def is_valid_job(title, desc=""):
    if is_rejected(title): return False
    if len(title) > 200:   return False
    combined = (title + " " + desc).lower()
    # Must have lecturer word AND CSE signal anywhere in title+desc
    return is_lecturer(combined) and is_cse(combined)

def is_recent(iso):
    if not iso: return True
    try:
        dt = datetime.fromisoformat(iso.replace("Z","+00:00"))
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).days <= MAX_AGE_DAYS
    except: return True

def make_id(title, src):
    return hashlib.md5(f"{title.lower().strip()}{src.lower()}".encode()).hexdigest()[:12]

def load_existing():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f: return json.load(f)
    return {"jobs": [], "last_updated": ""}

def save_data(data):
    os.makedirs("docs", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get(url, timeout=15, as_json=False):
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return r.json() if as_json else BeautifulSoup(r.content, "lxml")
        print(f"    HTTP {r.status_code} ← {url[:60]}")
    except Exception as e:
        print(f"    ERR ← {url[:60]} | {e}")
    return None

def get_rss(url):
    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code == 200: return ET.fromstring(r.content)
    except Exception as e:
        print(f"    RSS ERR ← {url[:55]} | {e}")
    return None

def parse_date(raw):
    if not raw: return datetime.now(timezone.utc).isoformat()
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(raw).isoformat()
    except: return datetime.now(timezone.utc).isoformat()

# ════════════════════════════════════════════════════════════════
# SOURCE 1 — BDJobs API (JSON — no JS needed!)
# ════════════════════════════════════════════════════════════════
BDJOBS_API_SEARCHES = [
    "https://bdjobs.com/api/job-search/?keyword=lecturer+CSE&page=1",
    "https://bdjobs.com/api/job-search/?keyword=lecturer+computer+science&page=1",
    "https://bdjobs.com/api/job-search/?keyword=lecturer+information+technology&page=1",
    "https://bdjobs.com/api/job-search/?keyword=lecturer+software+engineering&page=1",
    # RSS fallback
]

BDJOBS_RSS_URLS = [
    "https://jobs.bdjobs.com/rss/rss.asp?fcat=10&txtsearch=lecturer",
    "https://jobs.bdjobs.com/rss/rss.asp?fcat=10&txtsearch=senior+lecturer",
    "https://bdjobs.com/rss/rss.asp?fcat=10&txtsearch=lecturer",
    "https://bdjobs.com/rss/rss.asp?fcat=10",
    "https://jobs.bdjobs.com/rss/rss.asp?fcat=10",
]

def scrape_bdjobs():
    jobs, seen = [], set()
    print("  [BDJobs API]")

    # Try API endpoints first
    api_worked = False
    for url in BDJOBS_API_SEARCHES:
        data = get(url, as_json=True)
        if not data: continue

        # Handle different response shapes
        items = []
        if isinstance(data, list): items = data
        elif isinstance(data, dict):
            items = (data.get("jobs") or data.get("data") or
                     data.get("results") or data.get("items") or [])

        print(f"    {len(items)} items ← API")
        for item in items:
            title  = str(item.get("title") or item.get("job_title") or item.get("position") or "").strip()
            inst   = str(item.get("company") or item.get("organization") or item.get("employer") or "").strip()
            link   = str(item.get("url") or item.get("link") or item.get("job_url") or "").strip()
            desc   = str(item.get("description") or item.get("short_desc") or "").strip()
            posted = str(item.get("posted_date") or item.get("date") or "").strip()
            dl     = str(item.get("deadline") or item.get("apply_deadline") or "").strip()

            if not title or not link: continue
            if not is_valid_job(title, desc): continue
            if not is_recent(posted or None): continue

            jid = make_id(title, inst or link)
            if jid in seen: continue
            seen.add(jid)
            api_worked = True
            jobs.append({"id":jid,"title":title,"source":"BDJobs","institution":inst or "BDJobs",
                         "url":link,"deadline":dl,"found_at":posted or datetime.now(timezone.utc).isoformat(),
                         "notified":False})
        time.sleep(0.5)

    # RSS fallback (always run — catches what API misses)
    print("  [BDJobs RSS fallback]")
    for url in BDJOBS_RSS_URLS:
        root = get_rss(url)
        if not root: continue
        items = root.findall(".//item")
        print(f"    {len(items)} items ← {url[-40:]}")
        for item in items:
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or "").strip()
            pub   = (item.findtext("pubDate") or "").strip()
            soup_d = BeautifulSoup(desc, "lxml")
            desc_text = soup_d.get_text(" ", strip=True)

            # BDJobs education RSS is already category-filtered.
            # Accept if title has "lecturer" — CSE check done via job page fetch.
            if not is_lecturer(title + " " + desc_text):
                continue
            if is_rejected(title):
                continue
            found_at = parse_date(pub)
            if not is_recent(found_at): continue

            # Try to get institution + department from description
            soup_d2 = BeautifulSoup(desc_text, "lxml")
            inst = soup_d2.get_text(" ", strip=True)[:80] or "BDJobs"

            # If neither title nor desc mentions CSE, fetch job page briefly
            if not is_cse(title + " " + desc_text):
                try:
                    jp = SESSION.get(link, timeout=8)
                    page_text = BeautifulSoup(jp.content, "lxml").get_text(" ")[:3000]
                    if not is_cse(page_text):
                        continue   # really not CSE
                    # Extract institution from page
                    inst_match = re.search(r"(university|college|institute)[^
]{0,60}", page_text, re.I)
                except Exception:
                    pass   # if fetch fails, include anyway (better to show than miss)

            jid = make_id(title, link)
            if jid in seen: continue
            seen.add(jid)
            jobs.append({"id":jid,"title":title,"source":"BDJobs","institution":inst,
                         "url":link,"deadline":"","found_at":found_at,"notified":False})
        time.sleep(0.5)

    print(f"  → {len(jobs)} jobs from BDJobs")
    return jobs

# ════════════════════════════════════════════════════════════════
# SOURCE 2 — Google News RSS (BD only)
# ════════════════════════════════════════════════════════════════
GNEWS_QUERIES = [
    "lecturer+CSE+university+Bangladesh+circular+2025",
    "lecturer+computer+science+Bangladesh+university+job+circular",
    "lecturer+information+technology+Bangladesh+university+2025",
    "CSE+lecturer+job+circular+site:thefinancialexpress.com",
    "CSE+lecturer+job+circular+site:thedailystar.net",
]
GNEWS = "https://news.google.com/rss/search?q={q}&hl=en-BD&gl=BD&ceid=BD:en"

def scrape_gnews():
    jobs, seen = [], set()
    print("  [Google News RSS — BD only]")
    for q in GNEWS_QUERIES:
        root = get_rss(GNEWS.format(q=q))
        if not root: continue
        items = root.findall(".//item")
        print(f"    {len(items)} items ← {q[:45]}")
        for item in items:
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or "").strip()
            pub   = (item.findtext("pubDate") or "").strip()

            if not is_bd_url(link): continue
            if not is_valid_job(title, desc): continue
            found_at = parse_date(pub)
            if not is_recent(found_at): continue

            # Clean Google News title (removes " - Source" suffix)
            clean = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
            jid = make_id(clean, link[:30])
            if jid in seen: continue
            seen.add(jid)

            jobs.append({"id":jid,"title":clean,"source":"Google News","institution":"See link",
                         "url":link,"deadline":"","found_at":found_at,"notified":False})
        time.sleep(0.5)
    print(f"  → {len(jobs)} from Google News")
    return jobs

# ════════════════════════════════════════════════════════════════
# SOURCE 3 — University career pages
# ════════════════════════════════════════════════════════════════
UNIVERSITIES = [
    {"name":"Ahsanullah Univ (AUST)",         "url":"https://www.aust.edu/career"},
    {"name":"North South University",          "url":"https://www.northsouth.edu/administration/offices/human-resources/job-opportunities.html"},
    {"name":"BRAC University",                 "url":"https://www.bracu.ac.bd/about/offices/human-resources/job-opportunities"},
    {"name":"IUB",                             "url":"https://iub.edu.bd/career"},
    {"name":"AIUB",                            "url":"https://www.aiub.edu/career"},
    {"name":"East West University",            "url":"https://www.ewubd.edu/job-circular"},
    {"name":"UIU",                             "url":"https://www.uiu.ac.bd/career/"},
    {"name":"ULAB",                            "url":"https://ulab.edu.bd/career/"},
    {"name":"Daffodil Intl University",        "url":"https://daffodilvarsity.edu.bd/article/career"},
    {"name":"Stamford University",             "url":"https://www.stamforduniversity.edu.bd/job-circular"},
    {"name":"Southeast University",            "url":"https://seu.edu.bd/career/"},
    {"name":"Prime University",                "url":"https://www.primeuniversity.edu.bd/career/"},
    {"name":"City University",                 "url":"https://cityuniversity.edu.bd/career/"},
    {"name":"Eastern University",              "url":"https://www.easternuni.edu.bd/career/"},
    {"name":"Green University",                "url":"https://green.edu.bd/career/"},
    {"name":"World University of Bangladesh",  "url":"https://wub.edu.bd/career/"},
    {"name":"Bangladesh University",           "url":"https://www.bu.edu.bd/job/"},
    {"name":"Primeasia University",            "url":"https://primeasia.edu.bd/career/"},
    {"name":"UODA",                            "url":"https://uda.ac.bd/career/"},
    {"name":"Manarat Intl University",         "url":"https://manarat.ac.bd/career/"},
    {"name":"State University of Bangladesh",  "url":"https://sub.edu.bd/career/"},
    {"name":"Northern University Bangladesh",  "url":"https://nub.ac.bd/career/"},
    {"name":"BUBT",                            "url":"https://www.bubt.edu.bd/home/career"},
    {"name":"Notre Dame Univ Bangladesh",      "url":"https://ndub.edu.bd/career/"},
    {"name":"Presidency University",           "url":"https://presidency.edu.bd/career/"},
    {"name":"Dhaka University",                "url":"https://www.du.ac.bd/body/notice_list/NTC"},
    {"name":"CUET",                            "url":"https://www.cuet.ac.bd/notice"},
    {"name":"RUET",                            "url":"https://www.ruet.ac.bd/all-notice-circular"},
    {"name":"KUET",                            "url":"https://www.kuet.ac.bd/index.php/notice-circulars/"},
    {"name":"DUET",                            "url":"https://duet.ac.bd/notices/"},
    {"name":"SUST",                            "url":"https://www.sust.edu/4"},
    {"name":"JU",                              "url":"https://www.juniv.edu/notice"},
    {"name":"Rajshahi University",             "url":"https://www.ru.ac.bd/notice/"},
    {"name":"Chittagong University",           "url":"https://cu.ac.bd/notice/"},
    {"name":"Khulna University",               "url":"https://www.ku.ac.bd/notice/"},
    {"name":"NSTU",                            "url":"https://nstu.edu.bd/notice/"},
    {"name":"MBSTU",                           "url":"https://www.mbstu.ac.bd/notice"},
    {"name":"Barishal University",             "url":"https://barisaluniv.edu.bd/notice/"},
]

def scrape_universities():
    jobs, seen = [], set()
    print(f"  [{len(UNIVERSITIES)} University pages]")
    for uni in UNIVERSITIES:
        soup = get(uni["url"])
        if not soup: continue
        base = "/".join(uni["url"].split("/")[:3])
        found = 0
        for a in soup.find_all("a", href=True):
            title = a.get_text(" ", strip=True)
            href  = a.get("href","").strip()
            if not href or href in ("#","javascript:void(0)"): continue
            if len(title) < 8 or len(title) > 180: continue
            if not is_valid_job(title): continue
            full_url = urljoin(base, href) if not href.startswith("http") else href
            jid = make_id(title, uni["name"])
            if jid in seen: continue
            seen.add(jid)
            jobs.append({"id":jid,"title":title,"source":uni["name"],"institution":uni["name"],
                         "url":full_url,"deadline":"","found_at":datetime.now(timezone.utc).isoformat(),
                         "notified":False})
            found += 1
        if found: print(f"    ✅ {uni['name']}: {found}")
        time.sleep(0.4)
    print(f"  → {len(jobs)} from university pages")
    return jobs

# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════
def main():
    all_new = []
    print("\n📡 BDJobs")
    all_new += scrape_bdjobs()
    print("\n📡 Google News")
    all_new += scrape_gnews()
    print("\n📡 Universities")
    all_new += scrape_universities()

    existing = load_existing()
    # Remove stale jobs
    existing["jobs"] = [j for j in existing["jobs"] if is_recent(j.get("found_at",""))]
    existing_ids = {j["id"] for j in existing["jobs"]}

    added = []
    for job in all_new:
        if job["id"] not in existing_ids:
            existing["jobs"].insert(0, job)
            added.append(job)
            existing_ids.add(job["id"])

    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    existing["jobs"] = existing["jobs"][:300]
    save_data(existing)

    with open("new_jobs.json","w",encoding="utf-8") as f:
        json.dump(added, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ Scraped: {len(all_new)} | New: {len(added)} | Total stored: {len(existing['jobs'])}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
