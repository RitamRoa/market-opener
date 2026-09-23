import sqlite3

conn = sqlite3.connect("data/market_intelligence.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
rows = cur.execute("SELECT url_hash, title, source, published_at FROM news_cache WHERE title LIKE '%Mazagon%' OR title LIKE '%MDL%' OR summary LIKE '%Mazagon%' OR summary LIKE '%Dighi%'").fetchall()
print(f"Total Mazagon items: {len(rows)}")
for r in rows:
    safe_t = r["title"].encode("ascii", errors="replace").decode("ascii")
    print(f"[{r['published_at']}] [{r['source']}] {safe_t}")
