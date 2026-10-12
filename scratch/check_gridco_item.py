import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.db import DB_PATH

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT title, summary, url, source FROM news_cache WHERE lower(title) LIKE '%gridco%' OR lower(summary) LIKE '%gridco%'")
for row in c.fetchall():
    print("TITLE:", row[0])
    print("SUMMARY:", row[1])
    print("URL:", row[2])
    print("SOURCE:", row[3])
