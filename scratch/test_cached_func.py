import sqlite3
from datetime import datetime

def get_cached_news_by_date(target_date: str, db_path: str = "data/market_intelligence.db"):
    items = []
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        day_str = dt.strftime("%d %b %Y")
        day_dash = dt.strftime("%d-%b-%Y")
    except Exception:
        day_str = target_date
        day_dash = target_date

    patterns = [f"{target_date}%", f"%{day_str}%", f"%{day_dash}%"]
    seen_hashes = set()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    for p in patterns:
        cursor.execute("""
            SELECT url_hash, url, title, summary, source, published_at, symbol 
            FROM news_cache 
            WHERE published_at LIKE ?
        """, (p,))
        for row in cursor.fetchall():
            h = row["url_hash"]
            if h not in seen_hashes:
                seen_hashes.add(h)
                items.append({
                    "url": row["url"],
                    "title": row["title"],
                    "summary": row["summary"],
                    "source": row["source"],
                    "published_at": row["published_at"],
                    "symbol": row["symbol"]
                })
    return items

items = get_cached_news_by_date("2026-09-18")
print(f"Total retrieved from cache: {len(items)}")
petronet_items = [it for it in items if "petronet" in (it["title"] + it["summary"]).lower()]
print(f"Petronet items: {len(petronet_items)}")
for p in petronet_items:
    safe_t = p["title"].encode("ascii", errors="replace").decode("ascii")
    print(" -", safe_t)
