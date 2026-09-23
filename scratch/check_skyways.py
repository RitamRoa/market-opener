import sqlite3

con = sqlite3.connect("data/market_intelligence.db")
cur = con.cursor()
rows = cur.execute("SELECT surfaced_date, company_name, headline FROM fna_surfaced_events WHERE company_name LIKE '%Skyways%'").fetchall()
print("Surfaced events for Skyways:", rows)

rows2 = cur.execute("SELECT title, published_at, source FROM news_cache WHERE title LIKE '%Skyways%' OR summary LIKE '%Skyways%'").fetchall()
print(f"Total Skyways in news_cache: {len(rows2)}")
for r in rows2:
    print(r)
