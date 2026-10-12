import sys
import os
import sqlite3

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.db import DB_PATH

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 1. Clean Max
c.execute("SELECT symbol, title, summary, source FROM news_cache WHERE lower(title) LIKE '%clean max%' or lower(summary) LIKE '%clean max%'")
print("=== CLEAN MAX ROWS ===")
for r in c.fetchall():
    print(r)

# 2. Check NSE / BSE master for Clean Max
from engine.equity_master import get_all_equities, resolve_entity
all_eq = get_all_equities()

print("\n=== SEARCH ALL EQUITIES FOR CLEAN MAX ===")
for sym, name in all_eq.items():
    if "clean" in name.lower() or "max" in name.lower():
        print(f"  {sym}: {name}")

print("\n=== SEARCH ALL EQUITIES FOR SIGNATURE ===")
for sym, name in all_eq.items():
    if "signature" in name.lower() or "signature" in sym.lower():
        print(f"  {sym}: {name}")

print("\n=== SEARCH ALL EQUITIES FOR DREDGING ===")
for sym, name in all_eq.items():
    if "dredg" in name.lower() or "dredg" in sym.lower():
        print(f"  {sym}: {name}")

print("\n=== SEARCH ALL EQUITIES FOR AUGMONT ===")
for sym, name in all_eq.items():
    if "augmont" in name.lower() or "augmont" in sym.lower():
        print(f"  {sym}: {name}")
