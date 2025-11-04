import os, hashlib, requests, yaml
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
import smtplib

# ---- time helpers (IST + 24h cutoff)
IST = timezone(timedelta(hours=5, minutes=30))
def now_ist(): return datetime.now(IST)
def cutoff_24h(): return now_ist() - timedelta(hours=24)

def to_ist(dt):
    # handle ISO (e.g., "2024-10-01T12:00:00Z") or epoch ms
    if isinstance(dt, datetime): return dt.astimezone(IST)
    if isinstance(dt, str):
        try: return datetime.fromisoformat(dt.replace("Z","+00:00")).astimezone(IST)
        except: pass
    try: return datetime.fromtimestamp(int(dt)/1000, tz=IST)
    except: return now_ist()

# ---- config
def load_cfg(path="sources.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

# ---- sources (ATS APIs)
def fetch_greenhouse(board):
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    data = requests.get(url, timeout=25).json().get("jobs", [])
    out=[]
    for j in data:
        out.append({
            "title": j.get("title",""),
            "company": board,
            "location": (j.get("location") or {}).get("name",""),
            "url": j.get("absolute_url",""),
            "posted": to_ist(j.get("updated_at") or j.get("created_at")),
            "source": "greenhouse"
        })
    return out

def fetch_lever(company):
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    data = requests.get(url, timeout=25).json()
    out=[]
    for j in data:
        loc = " / ".join([v for v in (j.get("categories") or {}).values() if v])
        out.append({
            "title": j.get("text",""),
            "company": company,
            "location": loc,
            "url": j.get("hostedUrl",""),
            "posted": to_ist(j.get("createdAt") or j.get("updatedAt")),
            "source": "lever"
        })
    return out

def fetch_ashby(company):
    url = f"https://jobs.ashbyhq.com/{company}.json"
    data = requests.get(url, timeout=25).json()
    out=[]
    for j in data.get("jobs", []):
        out.append({
            "title": j.get("title",""),
            "company": company,
            "location": ", ".join([l.get("locationName","") for l in j.get("locations",[])]),
            "url": j.get("jobUrl",""),
            "posted": to_ist(j.get("publishedAt")),
            "source": "ashby"
        })
    return out

def fetch_all(cfg):
    jobs=[]
    for b in cfg.get("greenhouse_boards",[]) or []: jobs += fetch_greenhouse(b)
    for c in cfg.get("lever_companies",[]) or []: jobs += fetch_lever(c)
    for c in cfg.get("ashby_companies",[]) or []: jobs += fetch_ashby(c)
    return jobs

# ---- filtering + dedupe
def uid(item):
    base = f'{item.get("company","")}|{item.get("title","")}|{item.get("location","")}|{item.get("url","")}'
    return hashlib.sha1(base.encode()).hexdigest()

def filter_recent_and_match(jobs, keywords, locations):
    cutoff = cutoff_24h()
    kw = [k.lower() for k in (keywords or [])]
    locs = [l.lower() for l in (locations or [])]
    out=[]
    for j in jobs:
        if not j.get("posted"): 
            continue
        if j["posted"] < cutoff:
            continue
        text = f'{j.get("title","")} {j.get("location","")} {j.get("company","")}'.lower()
        if kw and not any(k in text for k in kw): 
            continue
        if locs and not any(l in text for l in locs): 
            continue
        out.append(j)
    return out

def dedupe(jobs):
    seen=set(); out=[]
    for j in jobs:
        k = uid(j)
        if k in seen: continue
        seen.add(k); out.append(j)
    return out

# ---- email
def build_html(jobs):
    if not jobs:
        return "<p>No new matching roles in the last 24 hours.</p>"
    jobs_sorted = sorted(jobs, key=lambda x: x["posted"], reverse=True)
    items=[]
    for j in jobs_sorted:
        ts = j["posted"].strftime("%Y-%m-%d %H:%M")
        items.append(
            f'<li><b>{j["title"]}</b> — {j["company"]} — {j["location"]} · '
            f'{ts} IST · <a href="{j["url"]}">Apply</a> <i>({j["source"]})</i></li>'
        )
    return f"<h3>{len(jobs_sorted)} new roles in the last 24h</h3><ul>{''.join(items)}</ul>"

def send_email(html):
    sender = os.environ["GMAIL_USERNAME"]
    app_pw = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("TO_EMAIL", sender)
    msg = MIMEText(html, "html")
    msg["Subject"] = f"CRM/Retention Jobs — last 24h — {now_ist().strftime('%a, %b %d')}"
    msg["From"] = sender; msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(sender, app_pw); s.send_message(msg)

def main():
    cfg = load_cfg()
    all_jobs = fetch_all(cfg)
    filtered = filter_recent_and_match(all_jobs, cfg.get("keywords"), cfg.get("locations"))
    unique = dedupe(filtered)
    html = build_html(unique)
    send_email(html)

if __name__ == "__main__":
    main()
