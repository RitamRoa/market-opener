import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.entity_mapper import INDIAN_EQUITIES

targets = ["clean", "max", "signature", "dredg", "augmont", "omaxe", "aequs", "sail", "godrej"]

for eq in INDIAN_EQUITIES:
    name = eq.get("name", "").lower()
    sym = eq.get("symbol", "").lower()
    aliases = [a.lower() for a in eq.get("aliases", [])]
    for t in targets:
        if t in name or t in sym or any(t in a for a in aliases):
            print(f"[{t}] Found in INDIAN_EQUITIES: {eq['name']} ({eq['symbol']}), Aliases: {eq.get('aliases')}")
