import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.db import DB_PATH

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

queries = [
    ('Omaxe', "SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%omaxe%' OR lower(summary) LIKE '%omaxe%'"),
    ('Clean Max', "SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%clean max%' OR lower(title) LIKE '%cleanmax%' OR lower(summary) LIKE '%clean max%'"),
    ('Aequs', "SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%aequs%' OR lower(summary) LIKE '%aequs%'"),
    ('Signature Global', "SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%signature%' OR lower(summary) LIKE '%signature%'"),
    ('Godrej Properties', "SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%godrej%' OR lower(summary) LIKE '%godrej%'"),
    ('Dredging', "SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%dredging%' OR lower(summary) LIKE '%dredging%'"),
    ('SAIL BCCL', "SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%bccl%' OR lower(summary) LIKE '%bccl%' OR lower(title) LIKE '%sail%'"),
    ('Augmont', "SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%augmont%' OR lower(summary) LIKE '%augmont%'"),
]

for name, q in queries:
    c.execute(q)
    rows = c.fetchall()
    print(f"=== {name}: {len(rows)} rows ===")
    for r in rows:
        print(f"  [{r[2]}] [{r[3]}] {r[0]}")
        if r[1]:
            print(f"    Summary: {r[1][:120]}")
