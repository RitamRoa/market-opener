import sys
import os
from datetime import datetime
import zoneinfo

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.fna_pipeline import (
    get_all_exchange_announcements,
    collect_market_news,
    get_cached_news_by_date,
    split_multi_company_article,
    parse_datetime_ist
)
from engine.run_context import RunContext, set_current_context
from engine.noise_filter import is_material_fundamental_event
from engine.entity_mapper import resolve_entity_from_text, validate_event_entity
from engine.equity_master import resolve_entity
from engine.deduplicator import deduplicate_and_cluster_news
from engine.fna_analyzer import synthesize_fna_item, classify_event_direction_and_type

def run():
    target_date = "2026-09-28"
    cutoff_time = "23:59:59"
    IST = zoneinfo.ZoneInfo("Asia/Kolkata")
    cutoff_dt = datetime.strptime(f"{target_date} {cutoff_time}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    ctx = RunContext("historical", target_date, cutoff_dt, "Asia/Kolkata")
    set_current_context(ctx)

    raw_ann = get_all_exchange_announcements(target_date=target_date)
    raw_news = collect_market_news(target_date=target_date)
    cached = get_cached_news_by_date(target_date)
    if cached:
        raw_news.extend(cached)

    all_raw_events = []
    seen = set()
    for ann in raw_ann:
        dt = parse_datetime_ist(ann.get("published_at", ""))
        if dt and not ctx.is_eligible(dt):
            continue
        t = ann.get("title", "").strip().lower()
        if t not in seen:
            seen.add(t)
            all_raw_events.append({
                "title": ann.get("title", ""),
                "summary": ann.get("summary", ""),
                "source": ann.get("source", "NSE Corporate Announcements"),
                "url": ann.get("url", ""),
                "filing_symbol": ann.get("raw_symbol") or ann.get("symbol"),
                "published_at": ann.get("published_at", ""),
                "is_primary": True
            })

    for news in raw_news:
        dt = parse_datetime_ist(news.get("published_at", ""))
        if dt and not ctx.is_eligible(dt):
            continue
        t = news.get("title", "").strip().lower()
        if t not in seen:
            seen.add(t)
            all_raw_events.append({
                "title": news.get("title", ""),
                "summary": news.get("summary", ""),
                "source": news.get("source", "Financial News"),
                "url": news.get("url", ""),
                "filing_symbol": None,
                "published_at": news.get("published_at", ""),
                "is_primary": any(k in news.get("source", "").lower() for k in ["pib", "sebi", "rbi", "bureau", "regulator", "exchange"])
            })

    expanded = []
    for ev in all_raw_events:
        expanded.extend(split_multi_company_article(ev))
    all_raw_events = expanded

    material_events = []
    for ev in all_raw_events:
        is_m, r = is_material_fundamental_event(ev["title"], ev.get("summary", ""), is_primary_exchange_filing=ev.get("is_primary", False))
        if is_m:
            material_events.append(ev)

    resolved_events = []
    for ev in material_events:
        full_text = f"{ev['title']} {ev.get('summary', '')}"
        meta, r = resolve_entity_from_text(full_text, filing_symbol=ev.get("filing_symbol"))
        if not meta:
            continue
        grounded = resolve_entity(meta["name"], symbol=meta["symbol"])
        if not grounded:
            continue
        is_valid, v_r = validate_event_entity(ev["title"], ev.get("summary", ""), meta["symbol"])
        if not is_valid:
            continue
        ev_copy = dict(ev)
        ev_copy["company_name"] = grounded[1]
        ev_copy["ticker"] = grounded[0]
        ev_copy["symbol"] = meta["symbol"]
        ev_copy["sector"] = meta["sector"]
        resolved_events.append(ev_copy)

    clusters = deduplicate_and_cluster_news(resolved_events, similarity_threshold=0.55)

    print(f"TOTAL CLUSTERS: {len(clusters)}")
    for idx, cl in enumerate(clusters, 1):
        comp = cl.get("company_name", "")
        sym = cl.get("symbol", "")
        title = cl.get("title", "")
        summary = cl.get("summary", "")
        full_text = f"{title} {summary}"
        ev_type, direction, base_mat = classify_event_direction_and_type(full_text)
        item = synthesize_fna_item(cl)
        is_evaluated = bool(item and item.get("fundamental_direction") in ["Positive", "Negative"])
        print(f"{idx:3d}. [{sym}] {comp} | Type: {ev_type} | Dir: {direction} | BaseMat: {base_mat} | Evaluated: {is_evaluated}")
        print(f"     Title: {title[:90]}")
        if not is_evaluated:
            if direction not in ["Positive", "Negative"]:
                print(f"     -> REASON DROPPED: Direction is '{direction}' (not strictly Positive/Negative)")
            elif not item:
                print(f"     -> REASON DROPPED: synthesize_fna_item returned None (e.g. role customer/buyer)")

if __name__ == "__main__":
    run()
