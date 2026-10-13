import sqlite3

conn = sqlite3.connect("data/market_intelligence.db")
c = conn.cursor()

dates = c.execute("SELECT DISTINCT substr(published_at, 1, 10) FROM news_cache ORDER BY 1").fetchall()
print("Distinct news dates in news_cache:")
for d in dates:
    if d[0] and "202" in d[0]:
        print(d[0])

report_dates = c.execute("SELECT DISTINCT report_date FROM fna_reports ORDER BY 1").fetchall()
print("Report dates in DB:", [r[0] for r in report_dates])
