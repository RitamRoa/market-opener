import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.db import DB_PATH

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT title, summary FROM news_cache WHERE lower(title) LIKE '%sail%' or lower(summary) LIKE '%sail%'")
for r in c.fetchall():
    t, s = r[0], r[1]
    if 'bccl' in t.lower() or 'bccl' in s.lower() or 'mou' in s.lower() or 'coal' in s.lower():
        print("TITLE:", t)
        print("SUMMARY:", s)
        print("-" * 50)
