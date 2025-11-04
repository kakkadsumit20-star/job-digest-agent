import os, re, hashlib, requests, yaml
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
import smtplib

# ---- timezone helpers (IST)
IST = timezone(timedelta(hours=5, minutes=30))
def now_ist(): return datetime.now(IST)
def cutoff_24h(): return now_ist() - timedelta(hours=24)

def to_ist(dt):
    if isinstance(dt, datetime): return dt.astimezone(IST)
    if isinstance(dt, str):
        try: return datetime.fromisoformat(dt.replace("Z","+00:00")).astimezone(IST)
        except: pass
    try: return datetime.fromtimestamp(int(dt)/1000, tz=IST)
    except: return now_ist()

# ---- parse "6 hours ago" etc.
_rel_re = re.compile(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", re.I)
def from_relative(s: str):
    s = (s or "").lower().strip()
    if s == "yesterday": return now_ist() - timedelta(days=1)
    m = _rel_re.search(s)
    if not m: return now_ist()
    n, unit = int(m.group(1)), m.group(2)
    if unit.startswith("minute"): delta = timedelta(minutes=n)
    elif unit.startswith("hour"): delta = timedelta(hours=n)
    elif unit.startswith("day"): delta = timedelta(days=n)
    elif unit.startswith("week"): delta = timedelta(weeks=n)
    elif unit.startswith("month"): delta = timedelta(days=30*n)
    else: delta = timedelta(days=365)
    return now_ist() - delta

# ---- load config
def load_cfg(path="sources.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

# ---- ATS sources
def fetch_greenhouse(board):
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    try:
        data = requests.get(url, timeout=25).json().get("jobs", [])
    except Exception:
        return []
    out=[]
    for j in data:
        out.append({
            "title": j
