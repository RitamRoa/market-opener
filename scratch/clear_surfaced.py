import sqlite3

conn = sqlite3.connect("data/market_intelligence.db")
cur = conn.cursor()
cur.execute("DELETE FROM fna_surfaced_events WHERE surfaced_date = '2026-09-18'")
conn.commit()
print("Cleared surfaced events for 2026-09-18.")
