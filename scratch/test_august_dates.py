import sys, os
sys.path.insert(0, os.path.abspath("."))
from engine.fna_pipeline import run_fna_pipeline

for d in ["2026-08-01", "2026-08-07", "2024-08-01", "2023-08-01"]:
    try:
        items, report = run_fna_pipeline(target_date=d)
        print(f"Date {d}: {len(items)} items")
    except Exception as e:
        print(f"Date {d} error: {e}")
