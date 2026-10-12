import glob
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

files = glob.glob(r"C:\Users\Ritham\.gemini\antigravity-ide\brain\*\.system_generated\logs\transcript*.jsonl")
print(f"Checking {len(files)} transcript files...")
for f in files:
    try:
        with open(f, "r", encoding="utf-8", errors="ignore") as fp:
            for line in fp:
                if "Omaxe (SEBI order)" in line or "Clean Max Enviro (block deal)" in line or "Aequs (promoter" in line:
                    print(f"MATCH in {f}")
                    # print snippet
                    idx = line.find("Omaxe")
                    print(line[max(0, idx-50):min(len(line), idx+200)])
                    break
    except Exception:
        pass
