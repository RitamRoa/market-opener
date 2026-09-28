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

targets = [
    ("Omaxe", "%omaxe%"),
    ("Clean Max", "%clean max%"),
    ("CleanMax", "%cleanmax%"),
    ("Aequs", "%aequs%"),
    ("Signature Global", "%signature%"),
    ("Godrej", "%godrej%"),
    ("Dredging", "%dredging%"),
    ("SAIL", "%sail%"),
    ("BCCL", "%bccl%"),
    ("Augmont", "%augmont%")
]

for name, pat in targets:
    c.execute("SELECT title, summary, published_at, source, is_noise FROM news_cache WHERE lower(title) LIKE ? OR lower(summary) LIKE ?", (pat, pat))
    rows = c.fetchall()
    print(f"\n================ {name} ({len(rows)} rows) ================")
    for r in rows:
        print(f"[{r[2]}] [{r[3]}] is_noise={r[4]}")
        print(f"  Title: {r[0]}")
        if r[1]:
            print(f"  Summary: {r[1][:140]}")
