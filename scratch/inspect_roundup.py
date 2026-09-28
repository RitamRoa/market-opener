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

c.execute("SELECT title, summary FROM news_cache WHERE lower(title) LIKE '%top stocks in focus today%' OR lower(title) LIKE '%stocks to watch sept 28%'")
for r in c.fetchall():
    print("=" * 60)
    print("TITLE:", r[0])
    print("SUMMARY:", r[1])
