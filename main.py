"""
Main Entry Point for the Indian Stock Market Fundamental News Analysis (FNA) CLI.
Inspired by Sharekhan's daily FNA format.
Runs entirely in the terminal: ZERO API keys, ZERO web server, ZERO dashboard.
"""

import sys
import os
import argparse
import logging

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from engine.fna_pipeline import run_fna_pipeline
from engine.db import get_fna_report_by_date


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Indian Stock Market Fundamental News & Analysis (FNA) Engine — Sharekhan Style"
    )
    parser.add_argument(
        "--date", 
        type=str, 
        help="Date to inspect in YYYY-MM-DD format (default: today)"
    )
    parser.add_argument(
        "--hours", 
        type=int, 
        default=24, 
        help="Time window in hours to scan for developments (default: 24)"
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable verbose diagnostic debug logging"
    )
    parser.add_argument(
        "--no-llm", 
        action="store_true", 
        help="Force deterministic Python intelligence without querying local LLM"
    )
    parser.add_argument(
        "--export", 
        action="store_true", 
        help="Export report explicitly to reports/ directory (saved by default)"
    )
    parser.add_argument(
        "--max-items", 
        type=int, 
        default=12, 
        help="Maximum number of TOP NEWS developments to feature (default: 12)"
    )

    args = parser.parse_args()
    setup_logging(args.debug)

    # Check if a past date report was requested from cache
    if args.date:
        cached_report = get_fna_report_by_date(args.date)
        if cached_report and not args.debug and cached_report.get("item_count", 0) >= 5:
            print(cached_report["report_text"])
            return
        elif cached_report and not args.debug:
            # Stale single-item report in cache; run fresh scan to provide comprehensive daily coverage
            pass
        elif not cached_report:
            print(f"[!] No archived report found for date {args.date}. Running fresh scan...")

    # Run the FNA pipeline
    try:
        items, report_text = run_fna_pipeline(max_items=args.max_items, debug=args.debug)
        print("\n" + report_text)
    except KeyboardInterrupt:
        print("\n[!] Scan interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] FNA pipeline encountered an error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
