import sqlite3
import os

for db_name in ['data/fna.db', 'data/fna_database.db', 'data/market_intelligence.db']:
    if os.path.exists(db_name):
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in c.fetchall()]
        print(f"{db_name}: tables={tables}")
        for t in tables:
            try:
                c.execute(f"SELECT count(*) FROM {t}")
                cnt = c.fetchone()[0]
                print(f"  {t}: {cnt} rows")
            except Exception as e:
                print(f"  {t}: error {e}")
