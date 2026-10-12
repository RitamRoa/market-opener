import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.db import DB_PATH

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Check fna_events table for any historical occurrences of these
c.execute("SELECT event_date, company_name, symbol, headline, event_type, materiality_score FROM fna_events WHERE lower(company_name) LIKE '%omaxe%' OR lower(company_name) LIKE '%aequs%' OR lower(company_name) LIKE '%dredging%' OR lower(company_name) LIKE '%sail%' OR lower(company_name) LIKE '%clean max%' OR lower(company_name) LIKE '%cleanmax%' OR lower(company_name) LIKE '%augmont%' OR lower(company_name) LIKE '%signature%' OR lower(company_name) LIKE '%godrej%'")
rows = c.fetchall()
print(f"=== fna_events matches: {len(rows)} ===")
for r in rows:
    print(r)

# Check fna_reports table
c.execute("SELECT report_date, report_id FROM fna_reports")
print("\n=== fna_reports dates ===")
for r in c.fetchall():
    print(r)
