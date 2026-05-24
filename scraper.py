"""
BD Lecturer Job Tracker — v3 (Reliable Edition)
Strategy:
  1. BDJobs RSS feed       → no bot block, always works
  2. Google News RSS        → finds university circulars Google already indexed
  3. University pages       → fixed URLs + PDF circular detection + session
"""

import requests, json, os, hashlib, time, sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import xml.etree.ElementTree as ET

# ── Session with realistic browser headers ────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.google.com/",
    "DNT":             "1",
})

DATA_FILE = "docs/jobs.json"

# ── Keywords ──────────────────────────────────────────────────────────────────
POSITION_KW = ["lecturer", "assistant professor", "associate professor",
               "faculty member", "লেকচারার", "শিক্ষক নিয়োগ", "faculty position"]

CSE_KW      = ["computer science", "computer engineering", "cse", "it ",
               "information technology", "software engineering", "ict",
               "computing", "data science", "artificial intelligence",
               "machine learning", "কম্পিউটার"]

BLOCK_KW    = ["student", "admission", "scholarship", "result", "exam",
               "routine", "notice of", "বিজ্ঞপ্তি", "payment"]

def is_position(txt):
    t = txt.lower()
    return any(k in t for k in POSITION_KW)

def is_cse(txt):
    t = txt.lower()
    return any(k in t for k in CSE_KW)

def is_blocked(txt):
    t = txt.lower()
    return any(k in t for k in BLOCK_KW)

def is_relevant(txt):
    if is_blocked(txt): return False
    return is_position(txt) and is_cse(txt)

def is_faculty_any_dept(txt):
    """Catch generic faculty/lecturer ads that might be CSE"""
    if is_blocked(txt): return False
    return is_position(txt) and len(txt.strip()) < 100

def make_id(title, source):
    return hashlib.md5(f"{title.lower().strip()}{source.lower().strip()}".encode()).hexdigest()[:12]

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
        print(f"    HTTP {r.status_code} → {url[:60]}")
    except Exception as e:
        print(f"    ERR → {url[:60]} | {e}")
    return None

def get_rss(url, timeout=15):
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return ET.fromstring(r.content)
    except Exception as e:
        print(f"    RSS ERR → {url[:60]} | {e}")
    return None

# ════════════════════════════════════════════════════════════════════════════════
# SOURCE 1 — BDJobs RSS feeds (no bot block!)
# ════════════════════════════════════════════════════════════════════════════════
BDJOBS_RSS = [
    # Category 10 = Education/Training
    "https://jobs.bdjobs.com/rss/rss.asp?fcat=10",
    # Keyword-based RSS (if available)
    "https://jobs.bdjobs.com/rss/rss.asp?txtsearch=lecturer",
    "https://jobs.bdjobs.com/rss/rss.asp?txtsearch=CSE+lecturer",
]

def scrape_bdjobs_rss():
    jobs, seen = [], set()
    print("  [BDJobs RSS] Fetching education category feed...")

    for rss_url in BDJOBS_RSS:
        root = get_rss(rss_url)
        if root is None:
            continue

        # RSS: <channel><item><title>...</title><link>...</link><description>...
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item")
        print(f"    → {len(items)} items in feed: {rss_url[-40:]}")

        for item in items:
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or "").strip()
            full  = f"{title} {desc}"

            if not is_relevant(full) and not is_faculty_any_dept(full):
                continue

            # extract institution from description
            soup_d  = BeautifulSoup(desc, "lxml")
            inst    = soup_d.get_text(" ", strip=True)[:60] or "Unknown"

            jid = make_id(title, link)
            if jid in seen: continue
            seen.add(jid)

            jobs.append({"id": jid, "title": title, "source": "BDJobs",
                         "institution": inst, "url": link,
                         "found_at": datetime.utcnow().isoformat(), "notified": False})
        time.sleep(0.5)

    print(f"  [BDJobs RSS] → {len(jobs)} relevant job(s)")
    return jobs

# ════════════════════════════════════════════════════════════════════════════════
# SOURCE 2 — Google News RSS (finds circulars Google already indexed!)
# ════════════════════════════════════════════════════════════════════════════════
GOOGLE_NEWS_QUERIES = [
    "lecturer+CSE+university+Bangladesh+circular",
    "assistant+professor+computer+science+Bangladesh+university",
    "faculty+position+CSE+Bangladesh+university+2025",
    "lecturer+IT+university+Bangladesh+job+circular",
]

GOOGLE_NEWS_BASE = "https://news.google.com/rss/search?q={q}&hl=en-BD&gl=BD&ceid=BD:en"

def scrape_google_news():
    jobs, seen = [], set()
    print("  [Google News RSS] Searching for university circulars...")

    for q in GOOGLE_NEWS_QUERIES:
        url  = GOOGLE_NEWS_BASE.format(q=q)
        root = get_rss(url)
        if root is None:
            continue

        items = root.findall(".//item")
        print(f"    → {len(items)} news items for: {q[:40]}")

        for item in items:
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or title).strip()
            full  = f"{title} {desc}"

            # Skip news articles, only want actual job postings
            skip_words = ["award", "research paper", "published", "conference",
                          "seminar", "workshop", "promoted", "election"]
            if any(w in full.lower() for w in skip_words):
                continue

            if not is_position(full):
                continue

            jid = make_id(title, link[:30])
            if jid in seen: continue
            seen.add(jid)

            jobs.append({"id": jid, "title": title, "source": "Google News",
                         "institution": "See link", "url": link,
                         "found_at": datetime.utcnow().isoformat(), "notified": False})

        time.sleep(0.5)

    print(f"  [Google News RSS] → {len(jobs)} item(s)")
    return jobs

# ════════════════════════════════════════════════════════════════════════════════
# SOURCE 3 — University websites (fixed URLs + PDF detection)
# ════════════════════════════════════════════════════════════════════════════════
UNIVERSITIES = [
    # ── Public ──────────────────────────────────────────────────────────────
    {"name": "BUET",              "url": "https://www.buet.ac.bd/web/#/noticeboard/vacancy",     "type": "spa"},
    {"name": "Dhaka University",  "url": "https://www.du.ac.bd/body/notice_list/NTC"},
    {"name": "CUET",              "url": "https://www.cuet.ac.bd/notice"},
    {"name": "RUET",              "url": "https://www.ruet.ac.bd/all-notice-circular"},
    {"name": "KUET",              "url": "https://www.kuet.ac.bd/index.php/notice-circulars/"},
    {"name": "DUET",              "url": "https://duet.ac.bd/notices/"},
    {"name": "SUST",              "url": "https://www.sust.edu/4"},
    {"name": "JU",                "url": "https://www.juniv.edu/notice"},
    {"name": "Rajshahi University","url": "https://www.ru.ac.bd/notice/"},
    {"name": "Chittagong Univ",   "url": "https://cu.ac.bd/notice/"},
    {"name": "Khulna University", "url": "https://www.ku.ac.bd/notice/"},
    {"name": "Comilla University","url": "https://www.cou.ac.bd/notice/"},
    {"name": "NSTU",              "url": "https://nstu.edu.bd/notice/"},
    {"name": "PUST",              "url": "https://www.pust.ac.bd/notices/"},
    {"name": "MBSTU",             "url": "https://www.mbstu.ac.bd/notice"},
    {"name": "HSTU",              "url": "https://www.hstu.ac.bd/notice"},
    {"name": "Barishal University","url":"https://barisaluniv.edu.bd/notice/"},
    {"name": "BRUR",              "url": "https://www.brur.ac.bd/notice/"},
    {"name": "RMSTU",             "url": "https://www.rmstu.edu.bd/notice/"},
    {"name": "Gopalganj Sci&Tech","url": "https://bsmstu.edu.bd/notice/"},
    {"name": "Patuakhali Sci&Tech","url":"https://pstu.ac.bd/notice/"},
    # ── Private ─────────────────────────────────────────────────────────────
    # BRAC blocks → use their career RSS / job feed URL
    {"name": "BRAC University",   "url": "https://www.bracu.ac.bd/about/offices/human-resources/job-opportunities",
                                   "alt": "https://www.bracu.ac.bd/career"},
    # NSU — updated URL
    {"name": "North South Univ",  "url": "https://www.northsouth.edu/administration/offices/human-resources/job-opportunities.html",
                                   "alt": "https://www.northsouth.edu/hr/"},
    {"name": "AIUB",              "url": "https://www.aiub.edu/career"},
    {"name": "DIU (Daffodil)",    "url": "https://daffodilvarsity.edu.bd/article/career"},
    {"name": "UIU",               "url": "https://www.uiu.ac.bd/career/"},
    {"name": "EWU",               "url": "https://www.ewubd.edu/job-circular"},
    {"name": "IUB",               "url": "https://iub.edu.bd/career"},
    {"name": "AUST",              "url": "https://www.aust.edu/career"},
    {"name": "Southeast Univ",    "url": "https://seu.edu.bd/career/"},
    {"name": "Stamford Univ",     "url": "https://www.stamforduniversity.edu.bd/job-circular"},
    {"name": "Green University",  "url": "https://green.edu.bd/career/"},
    {"name": "Metropolitan Univ", "url": "https://metrouni.edu.bd/career"},
    {"name": "Premier University","url": "https://www.puc.ac.bd/career/"},
    {"name": "IUBAT",             "url": "https://iubat.edu/career/"},
    {"name": "BGC Trust Univ",    "url": "https://bgctub.ac.bd/career/"},
    {"name": "BAUST",             "url": "https://baust.edu.bd/career/"},
    {"name": "Leading University","url": "https://lus.ac.bd/career/"},
    {"name": "Sylhet Intl Univ",  "url": "https://siu.edu.bd/career/"},
    {"name": "Manarat Intl Univ", "url": "https://manarat.ac.bd/career/"},
    {"name": "Primeasia Univ",    "url": "https://primeasia.edu.bd/career/"},
    {"name": "Uttara University", "url": "https://uttarauniversity.edu.bd/career/"},
    {"name": "World University",  "url": "https://wub.edu.bd/career/"},
    {"name": "Eastern University","url": "https://www.easternuni.edu.bd/career/"},
    {"name": "Atish Dipankar Univ","url":"https://adust.edu.bd/career/"},
    {"name": "Bangladesh Univ",   "url": "https://www.bu.edu.bd/job/"},
    {"name": "City University",   "url": "https://cityuniversity.edu.bd/career/"},
    {"name": "Shanto-Mariam Univ","url": "https://smuct.edu.bd/career/"},
    {"name": "University of Asia Pacific","url":"https://www.uap-bd.edu/career/"},
    {"name": "University of Development Alt.","url":"https://uda.ac.bd/career/"},
    {"name": "University of Liberal Arts","url":"https://ulab.edu.bd/career/"},
    {"name": "IBAIS University",  "url": "https://ibaisuniv.edu.bd/career/"},
    {"name": "ICAB",              "url": "https://www.icab.com.bd/career/"},
]

def scrape_university(uni):
    jobs, seen = [], set()
    base = "/".join(uni["url"].split("/")[:3])

    soup = get_html(uni["url"])
    # try alternate URL if main fails
    if soup is None and uni.get("alt"):
        print(f"    Trying alt URL for {uni['name']}...")
        soup = get_html(uni["alt"])
    if soup is None:
        return jobs

    for a in soup.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        href  = a.get("href", "").strip()

        if not href or href in ("#", "javascript:void(0)"):
            continue
        if len(title) < 6 or len(title) > 250:
            continue

        full_url = urljoin(base, href) if not href.startswith("http") else href

        # Priority 1: Title clearly matches CSE lecturer job
        if is_relevant(title):
            pass
        # Priority 2: PDF link whose URL contains faculty/recruitment keywords
        elif href.lower().endswith(".pdf") and any(
            k in href.lower() for k in ["faculty", "recruit", "lecturer", "appoint", "circular", "vacancy"]
        ):
            title = title or f"Job Circular (PDF) — {uni['name']}"
        # Priority 3: Generic faculty post (might be CSE — user decides)
        elif is_faculty_any_dept(title):
            title = f"[Faculty Post] {title}"
        else:
            continue

        jid = make_id(title, uni["name"])
        if jid in seen: continue
        seen.add(jid)

        jobs.append({"id": jid, "title": title, "source": uni["name"],
                     "institution": uni["name"], "url": full_url,
                     "found_at": datetime.utcnow().isoformat(), "notified": False})
    return jobs

# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════
def main():
    all_new = []

    print("\n📡 SOURCE 1: BDJobs RSS")
    all_new += scrape_bdjobs_rss()

    print("\n📡 SOURCE 2: Google News RSS")
    all_new += scrape_google_news()

    print(f"\n📡 SOURCE 3: {len(UNIVERSITIES)} University websites")
    ok, fail = 0, 0
    for uni in UNIVERSITIES:
        if uni.get("type") == "spa":
            print(f"    ⚠️  {uni['name']} is a SPA (JS-rendered), skipping")
            continue
        results = scrape_university(uni)
        if results:
            print(f"    ✅ {uni['name']}: {len(results)}")
            ok += 1
        else:
            fail += 1
        all_new += results
        time.sleep(0.4)
    print(f"    → {ok} sites returned data, {fail} sites blocked/empty")

    # Merge
    existing     = load_existing()
    existing_ids = {j["id"] for j in existing["jobs"]}
    added = []
    for job in all_new:
        if job["id"] not in existing_ids:
            existing["jobs"].insert(0, job)
            added.append(job)
            existing_ids.add(job["id"])

    existing["last_updated"] = datetime.utcnow().isoformat()
    existing["jobs"]         = existing["jobs"][:500]
    save_data(existing)

    with open("new_jobs.json", "w", encoding="utf-8") as f:
        json.dump(added, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ DONE → {len(all_new)} scraped | {len(added)} new this run")
    print(f"{'='*50}")

    if len(all_new) == 0:
        print("\n⚠️  All sources returned 0 results.")
        print("   Check GitHub Actions log for HTTP errors above.")

if __name__ == "__main__":
    main()
