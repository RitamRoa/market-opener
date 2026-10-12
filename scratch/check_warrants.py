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

print("--- WARRANTS / PREFERENTIAL ---")
c.execute("SELECT published_at, title, summary FROM news_cache WHERE lower(title) LIKE '%warrant%' OR lower(summary) LIKE '%warrant%' OR lower(title) LIKE '%preferential%' OR lower(summary) LIKE '%preferential%'")
for r in c.fetchall():
    print(f"[{r[0]}] {r[1]}")
    if r[2]:
        print(f"    {r[2][:120]}")
