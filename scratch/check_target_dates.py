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

targets = [
    ("Omaxe", "%omaxe%"),
    ("Clean Max", "%clean max%"),
    ("CleanMax", "%cleanmax%"),
    ("Aequs", "%aequs%"),
    ("Signature Global", "%signature%"),
    ("Godrej", "%godrej%"),
    ("Dredging", "%dredging%"),
    ("SAIL", "%sail%"),
    ("Augmont", "%augmont%")
]

for name, pat in targets:
    c.execute("SELECT count(*) FROM news_cache WHERE lower(title) LIKE ? OR lower(summary) LIKE ?", (pat, pat))
    total_db = c.fetchone()[0]
    print(f"=== {name}: {total_db} total in DB ===")
    c.execute("SELECT published_at, title, source FROM news_cache WHERE (lower(title) LIKE ? OR lower(summary) LIKE ?) AND (published_at LIKE '2026-09-28%' OR published_at LIKE '%28 Sep 2026%' OR published_at LIKE '%28-Sep-2026%')", (pat, pat))
    rows_today = c.fetchall()
    print(f"  Rows explicitly dated 28-Sep: {len(rows_today)}")
    for r in rows_today:
        print(f"    [{r[0]}] [{r[2]}] {r[1]}")
    
    # Also check if any are on 27-Sep or 26-Sep
    c.execute("SELECT published_at, title, source FROM news_cache WHERE (lower(title) LIKE ? OR lower(summary) LIKE ?) AND (published_at LIKE '%27 Sep 2026%' OR published_at LIKE '%27-Sep-2026%' OR published_at LIKE '2026-09-27%')", (pat, pat))
    rows_27 = c.fetchall()
    print(f"  Rows explicitly dated 27-Sep: {len(rows_27)}")
    for r in rows_27:
        print(f"    [{r[0]}] [{r[2]}] {r[1]}")
