import sqlite3

conn = sqlite3.connect("data/market_intelligence.db")
cur = conn.cursor()
rows = cur.execute("SELECT published_at FROM news_cache LIMIT 30").fetchall()
for r in rows:
    print(r[0])
