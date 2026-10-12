import sys
import os
import sqlite3

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.db import DB_PATH

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

print("--- ALL OMAXE ---")
c.execute("SELECT published_at, title FROM news_cache WHERE lower(title) LIKE '%omaxe%' OR lower(summary) LIKE '%omaxe%'")
for r in c.fetchall():
    print(r)

print("--- ALL AEQUS ---")
c.execute("SELECT published_at, title FROM news_cache WHERE lower(title) LIKE '%aequs%' OR lower(summary) LIKE '%aequs%'")
for r in c.fetchall():
    print(r)

print("--- ALL DREDGING ---")
c.execute("SELECT published_at, title FROM news_cache WHERE lower(title) LIKE '%dredging%' OR lower(summary) LIKE '%dredging%'")
for r in c.fetchall():
    print(r)

print("--- ALL BCCL ---")
c.execute("SELECT published_at, title FROM news_cache WHERE lower(title) LIKE '%bccl%' OR lower(summary) LIKE '%bccl%'")
for r in c.fetchall():
    print(r)

print("--- COAL INDIA / GRIDCO ---")
c.execute("SELECT published_at, title, summary FROM news_cache WHERE lower(title) LIKE '%gridco%' OR lower(summary) LIKE '%gridco%'")
for r in c.fetchall():
    print(r)
