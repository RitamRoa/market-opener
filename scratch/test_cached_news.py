import sqlite3
from datetime import datetime

conn = sqlite3.connect("data/market_intelligence.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check ISO or RFC patterns
patterns = ['2026-09-18%', '%18 Sep 2026%', '%18-Sep-2026%']
results = []
for p in patterns:
    rows = cur.execute("SELECT url_hash, url, title, summary, source, published_at, symbol FROM news_cache WHERE published_at LIKE ?", (p,)).fetchall()
    results.extend(rows)

print(f"Total matching items for 2026-09-18: {len(results)}")
for r in results:
    t = r["title"]
    if any(k in t.lower() for k in ["petronet", "gruner", "mazagon", "indigo", "beml"]):
        print(f"[{r['source']}] {t[:80]}")
