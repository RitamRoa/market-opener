import json
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

log_file = r"C:\Users\Ritham\.gemini\antigravity-ide\brain\1c90d4df-cfa9-4395-a28b-753d6916f88e\.system_generated\logs\transcript.jsonl"
with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
    for idx, line in enumerate(f):
        if any(w in line for w in ["Omaxe", "Aequs", "Clean Max", "CleanMax", "Dredging", "Signature Global", "BCCL"]):
            try:
                data = json.loads(line)
                typ = data.get("type", "")
                content = str(data.get("content", ""))
                # print snippet
                print(f"Line {idx} ({typ}):")
                for sub in ["Omaxe", "Aequs", "Clean Max", "CleanMax", "Dredging", "Signature Global", "BCCL"]:
                    if sub in content:
                        pos = content.find(sub)
                        start = max(0, pos - 100)
                        end = min(len(content), pos + 200)
                        print(f"  [{sub}] ...{content[start:end]}...")
            except Exception as e:
                pass
