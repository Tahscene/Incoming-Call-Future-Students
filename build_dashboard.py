"""Builds docs/index.html from docs/jobs.json"""
import json, os
from datetime import datetime, timezone

DATA_FILE = "docs/jobs.json"
OUTPUT    = "docs/index.html"

def load_jobs():
    if not os.path.exists(DATA_FILE):
        return {"jobs": [], "last_updated": ""}
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)

def time_ago(iso):
    try:
        dt  = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        d = (now - dt).days
        h = (now - dt).seconds // 3600
        if d == 0 and h == 0: return "Just now"
        if d == 0: return f"{h}h ago"
        if d == 1: return "Yesterday"
        if d < 7:  return f"{d}d ago"
        return f"{d//7}w ago"
    except: return ""

SRC_COLORS = {"BDJobs":"#059669","Google News":"#db2777"}

def card(job):
    color = SRC_COLORS.get(job["source"], "#7c3aed")
    ago   = time_ago(job.get("found_at",""))
    dl    = f'<span class="dl">⏰ {job["deadline"]}</span>' if job.get("deadline") else ""
    return f'''<article class="card" onclick="window.open('{job["url"]}','_blank')">
  <div class="ch"><span class="badge" style="background:{color}">{job["source"]}</span>{dl}<span class="ago">{ago}</span></div>
  <h3>{job["title"]}</h3>
  <p class="inst">🏫 {job["institution"]}</p>
  <a class="btn" href="{job["url"]}" target="_blank" onclick="event.stopPropagation()">View Circular →</a>
</article>'''

def build():
    data  = load_jobs()
    jobs  = data.get("jobs", [])
    upd   = data.get("last_updated","")[:16].replace("T"," ")+" UTC" if data.get("last_updated") else "—"
    cards = "\n".join(card(j) for j in jobs) if jobs else '<p class="empty">No active circulars right now — check back soon!</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CSE Lecturer Jobs · BD</title>
<link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,700;1,600&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'DM Sans',sans-serif;background:#fafaf8;color:#111;min-height:100vh}}
body::before{{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;background-image:radial-gradient(circle,#05966914 1.2px,transparent 1.2px);background-size:26px 26px}}
.bar{{height:3px;background:linear-gradient(90deg,#059669,#db2777,#059669);background-size:200%;animation:bar 3s linear infinite}}
@keyframes bar{{to{{background-position:200%}}}}
.page{{position:relative;z-index:1;max-width:1100px;margin:0 auto;padding:0 1.25rem 4rem}}
header{{text-align:center;padding:3rem 1rem 2rem;border-bottom:1px solid #e5e7eb;margin-bottom:2rem}}
.pill{{display:inline-flex;align-items:center;gap:5px;border:1.5px solid #05966930;background:#f0fdf4;border-radius:99px;padding:.28rem .9rem;font-size:.7rem;font-weight:600;color:#059669;text-transform:uppercase;letter-spacing:.07em;margin-bottom:1rem}}
h1{{font-family:'Lora',serif;font-size:clamp(1.7rem,4.5vw,2.8rem);font-weight:700;line-height:1.2;margin-bottom:.6rem}}
h1 em{{font-style:italic;background:linear-gradient(135deg,#059669,#db2777);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.sub{{font-size:.88rem;color:#6b7280;margin-bottom:1.5rem;line-height:1.6}}
.stats{{display:flex;gap:.6rem;flex-wrap:wrap;justify-content:center}}
.stat{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:.38rem .9rem;font-size:.78rem;color:#6b7280;box-shadow:0 1px 4px #0000000a}}
.stat b{{color:#059669;font-weight:600}}
.toolbar{{display:flex;flex-direction:column;gap:.6rem;margin-bottom:1.8rem}}
.sbox{{display:flex;gap:.5rem;align-items:center;background:#fff;border:1.5px solid #e5e7eb;border-radius:12px;padding:.5rem .5rem .5rem 1rem;box-shadow:0 2px 8px #05966910;transition:border-color .2s}}
.sbox:focus-within{{border-color:#059669}}
.sbox input{{flex:1;border:none;outline:none;font-family:inherit;font-size:.9rem;color:#111;background:transparent}}
.sbox input::placeholder{{color:#9ca3af}}
.clr{{background:#f3f4f6;border:1px solid #e5e7eb;border-radius:8px;padding:.35rem .85rem;font-size:.78rem;color:#6b7280;cursor:pointer;font-family:inherit}}
.clr:hover{{background:#e5e7eb}}
.chips{{display:flex;gap:.45rem;flex-wrap:wrap}}
.chip{{border:1px solid #e5e7eb;background:#fff;border-radius:99px;padding:.25rem .85rem;font-size:.75rem;font-weight:500;color:#6b7280;cursor:pointer;transition:all .15s;font-family:inherit}}
.chip.on{{background:#059669;border-color:#059669;color:#fff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:.9rem;margin-bottom:4rem}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:1.2rem;cursor:pointer;transition:border-color .2s,transform .18s,box-shadow .18s;box-shadow:0 1px 4px #0000000a}}
.card:hover{{border-color:#059669;transform:translateY(-2px);box-shadow:0 8px 24px #05966912}}
.ch{{display:flex;align-items:center;gap:.5rem;margin-bottom:.75rem;flex-wrap:wrap}}
.badge{{color:#fff;font-size:.66rem;font-weight:700;padding:.17rem .6rem;border-radius:99px;text-transform:uppercase;letter-spacing:.05em}}
.dl{{font-size:.7rem;font-weight:600;color:#dc2626;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;padding:.12rem .45rem}}
.ago{{font-size:.73rem;color:#9ca3af;margin-left:auto}}
.card h3{{font-size:.93rem;font-weight:600;line-height:1.4;color:#111;margin-bottom:.35rem}}
.inst{{font-size:.82rem;color:#6b7280;margin-bottom:.9rem}}
.btn{{display:inline-block;background:linear-gradient(135deg,#059669,#db2777);color:#fff;text-decoration:none;font-size:.77rem;font-weight:600;padding:.3rem .85rem;border-radius:8px;transition:opacity .15s;float:right}}
.btn:hover{{opacity:.85}}
.empty{{text-align:center;color:#9ca3af;padding:4rem 2rem;grid-column:1/-1;font-size:.95rem}}
footer{{text-align:center;padding:1.5rem;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:.77rem;position:relative;z-index:1}}
footer a{{color:#059669;text-decoration:none}}
</style>
</head>
<body>
<div class="bar"></div>
<div class="page">
<header>
  <div class="pill">🎓 CSE & IT · Bangladesh</div>
  <h1>Hello Ma'am,<br><em>Find Lecturer Jobs Before Others</em> ✨</h1>
  <p class="sub">Only <strong>CSE & IT Lecturer</strong> positions — auto-fetched every 2 hours</p>
  <div class="stats">
    <div class="stat">Active: <b>{len(jobs)}</b></div>
    <div class="stat">Updated: <b>{upd}</b></div>
    <div class="stat"><b>50+</b> universities</div>
    <div class="stat">Every <b>2 hrs</b></div>
  </div>
</header>
<div class="toolbar">
  <div class="sbox">
    <input id="q" type="text" placeholder="Search by title or university..." oninput="filt()"/>
    <button class="clr" onclick="document.getElementById('q').value='';filt()">Clear</button>
  </div>
  <div class="chips" id="chips"></div>
</div>
<div class="grid" id="grid">{cards}</div>
<footer>Made with 💚 & 💗 · Auto-updates via GitHub Actions · <a href="https://github.com" target="_blank">Source</a></footer>
</div>
<script>
const cards=[...document.querySelectorAll('.card')];
const PRIO=["Ahsanullah Univ (AUST)","North South University","BRAC University","AIUB","IUB","East West University","UIU","ULAB","Daffodil Intl University","Stamford University","BDJobs","Google News"];
const rawSrc=[...new Set(cards.map(c=>c.querySelector('.badge').textContent))];
const srcs=rawSrc.sort((a,b)=>{{const ai=PRIO.indexOf(a),bi=PRIO.indexOf(b);if(ai>-1&&bi>-1)return ai-bi;if(ai>-1)return -1;if(bi>-1)return 1;return a.localeCompare(b)}});
let act=null;
const el=document.getElementById('chips');
function buildChips(){{el.innerHTML='';['All',...srcs].forEach(s=>{{const b=document.createElement('button');b.className='chip'+(act===null&&s==='All'||act===s?' on':'');b.textContent=s;b.onclick=()=>{{act=s==='All'?null:s;buildChips();filt()}};el.appendChild(b)}})}}
function filt(){{const q=document.getElementById('q').value.toLowerCase();cards.forEach(c=>{{const t=c.innerText.toLowerCase(),s=c.querySelector('.badge').textContent;c.style.display=(!q||t.includes(q))&&(act===null||s===act)?'':'none'}})}}
buildChips();
setTimeout(()=>location.reload(),30*60*1000);
</script>
</body>
</html>"""

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Dashboard built → {len(jobs)} jobs")

if __name__ == "__main__":
    build()
