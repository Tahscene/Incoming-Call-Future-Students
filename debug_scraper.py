"""
debug_scraper.py — Run this locally to find exactly what's breaking.
Usage:  python debug_scraper.py
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

BDJOBS_URL = "https://jobs.bdjobs.com/jobsearch.asp?txtsearch=lecturer+CSE&Country=0"

# ── Test 1: Can we reach BDJobs? ──────────────────────────────────────────────
print("=" * 60)
print("TEST 1: BDJobs connectivity")
print("=" * 60)
try:
    r = requests.get(BDJOBS_URL, headers=HEADERS, timeout=15)
    print(f"  Status Code : {r.status_code}")
    print(f"  Page size   : {len(r.text)} chars")

    soup = BeautifulSoup(r.text, "lxml")

    # Show ALL div class names on the page (helps find correct selector)
    all_divs = soup.find_all("div", class_=True)
    class_names = set()
    for d in all_divs:
        for c in d.get("class", []):
            if "job" in c.lower() or "title" in c.lower() or "position" in c.lower():
                class_names.add(c)

    print(f"\n  🔍 Job-related CSS classes found on BDJobs page:")
    for cn in sorted(class_names):
        print(f"     .{cn}")

    # Count all <a> tags
    all_links = soup.find_all("a", href=True)
    print(f"\n  Total <a> tags on page: {len(all_links)}")

    # Show first 15 links that look like job titles
    print("\n  First 15 job-looking links:")
    count = 0
    for a in all_links:
        txt = a.get_text(strip=True)
        if len(txt) > 10 and len(txt) < 120:
            print(f"     [{count+1}] {txt[:80]}")
            count += 1
            if count >= 15:
                break

except Exception as e:
    print(f"  ❌ ERROR: {e}")

# ── Test 2: Try a university site ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 2: NSU Career page")
print("=" * 60)
NSU_URL = "https://www.northsouth.edu/about-nsu/faculty-and-staff-resources/vacancy-announcements.html"
try:
    r = requests.get(NSU_URL, headers=HEADERS, timeout=15)
    print(f"  Status: {r.status_code}")
    soup = BeautifulSoup(r.text, "lxml")
    links = [a.get_text(strip=True) for a in soup.find_all("a") if len(a.get_text(strip=True)) > 8]
    print(f"  Links found: {len(links)}")
    for l in links[:10]:
        print(f"    → {l[:80]}")
except Exception as e:
    print(f"  ❌ ERROR: {e}")

# ── Test 3: BRAC University ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 3: BRAC University Jobs page")
print("=" * 60)
BRAC_URL = "https://www.bracu.ac.bd/about/offices/human-resources/job-opportunities"
try:
    r = requests.get(BRAC_URL, headers=HEADERS, timeout=15)
    print(f"  Status: {r.status_code}")
    soup = BeautifulSoup(r.text, "lxml")
    links = [a.get_text(strip=True) for a in soup.find_all("a") if len(a.get_text(strip=True)) > 8]
    print(f"  Links found: {len(links)}")
    for l in links[:10]:
        print(f"    → {l[:80]}")
except Exception as e:
    print(f"  ❌ ERROR: {e}")

# ── Test 4: DIU (Daffodil) ────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 4: Daffodil University Career page")
print("=" * 60)
DIU_URL = "https://daffodilvarsity.edu.bd/article/career"
try:
    r = requests.get(DIU_URL, headers=HEADERS, timeout=15)
    print(f"  Status: {r.status_code}")
    soup = BeautifulSoup(r.text, "lxml")
    links = [a.get_text(strip=True) for a in soup.find_all("a") if len(a.get_text(strip=True)) > 8]
    print(f"  Links found: {len(links)}")
    for l in links[:10]:
        print(f"    → {l[:80]}")
except Exception as e:
    print(f"  ❌ ERROR: {e}")

print("\n" + "=" * 60)
print("✅ Debug complete. Share this output so we can fix selectors.")
print("=" * 60)
