import sqlite3
import glob
import os

conn = sqlite3.connect("data/market_intelligence.db")
c = conn.cursor()

tables = [row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

for t in ["fna_reports", "news_cache", "event_cache"]:
    if t in tables:
        count = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"{t} count: {count}")

reports = glob.glob("reports/fna_*.json")
dates = sorted([os.path.basename(r).replace("fna_", "").replace(".json", "") for r in reports])
print("Report dates:", dates[:10], "...", dates[-10:])
