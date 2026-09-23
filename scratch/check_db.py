import sqlite3
import sys

con = sqlite3.connect("data/market_intelligence.db")
cur = con.cursor()
rows = cur.execute("SELECT url_hash, title, source, published_at FROM news_cache WHERE title LIKE '%Petronet%' OR summary LIKE '%Petronet%' OR title LIKE '%Gruner%' OR summary LIKE '%Gruner%'").fetchall()
print(f"Total matching: {len(rows)}")
for r in rows:
    safe_r = [str(x).encode("ascii", errors="replace").decode("ascii") for x in r]
    print(safe_r)
