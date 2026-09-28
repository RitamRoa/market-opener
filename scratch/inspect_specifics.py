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

# Search for Omaxe
print("--- OMAXE ---")
c.execute("SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%omaxe%' OR lower(summary) LIKE '%omaxe%'")
for r in c.fetchall():
    print(r)

# Search for Aequs
print("--- AEQUS ---")
c.execute("SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%aequs%' OR lower(summary) LIKE '%aequs%'")
for r in c.fetchall():
    print(r)

# Search for BCCL
print("--- BCCL ---")
c.execute("SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%bccl%' OR lower(summary) LIKE '%bccl%'")
for r in c.fetchall():
    print(r)

# Search for Dredging Corporation on 28 Sep or anywhere
print("--- DREDGING ---")
c.execute("SELECT title, summary, published_at, source FROM news_cache WHERE lower(title) LIKE '%dredging%' OR lower(summary) LIKE '%dredging%'")
for r in c.fetchall():
    print(r)
