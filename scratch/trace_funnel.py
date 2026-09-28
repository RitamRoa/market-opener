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
from engine.fna_analyzer import synthesize_fna_item
from engine.candidate_engine import (
    compute_research_importance_model,
    assign_materiality_tier,
    map_event_to_discovery_bucket,
    normalize_company_key
)

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

    print(f"Candidates Retrieved: {len(all_raw_events)}")

    material_events = []
    for ev in all_raw_events:
        is_m, r = is_material_fundamental_event(ev["title"], ev.get("summary", ""), is_primary_exchange_filing=ev.get("is_primary", False))
        if is_m:
            material_events.append(ev)
        ev["noise_reason"] = r

    print(f"Surviving Initial Materiality: {len(material_events)}")

    resolved_events = []
    for ev in material_events:
        full_text = f"{ev['title']} {ev.get('summary', '')}"
        meta, r = resolve_entity_from_text(full_text, filing_symbol=ev.get("filing_symbol"))
        if not meta:
            ev["drop_reason"] = f"Entity unresolved: {r}"
            continue
        grounded = resolve_entity(meta["name"], symbol=meta["symbol"])
        if not grounded:
            ev["drop_reason"] = f"Entity unlisted: {meta['name']} ({meta['symbol']})"
            continue
        is_valid, v_r = validate_event_entity(ev["title"], ev.get("summary", ""), meta["symbol"])
        if not is_valid:
            ev["drop_reason"] = f"Entity validation failed: {v_r}"
            continue
        ev_copy = dict(ev)
        ev_copy["company_name"] = grounded[1]
        ev_copy["ticker"] = grounded[0]
        ev_copy["symbol"] = meta["symbol"]
        ev_copy["sector"] = meta["sector"]
        resolved_events.append(ev_copy)

    print(f"Validated Entities: {len(resolved_events)}")

    clusters = deduplicate_and_cluster_news(resolved_events, similarity_threshold=0.55)
    print(f"Canonical Events (Clusters): {len(clusters)}")

    evaluated = []
    dropped_clusters = []
    for idx, cl in enumerate(clusters, 1):
        item = synthesize_fna_item(cl)
        if not item:
            dropped_clusters.append((cl, "synthesize_fna_item returned None (direction AMBIGUOUS or role rejected)"))
            continue
        direction = item.get("fundamental_direction")
        if direction not in ["Positive", "Negative"]:
            dropped_clusters.append((cl, f"Direction not Positive/Negative: {direction}"))
            continue
        score_dict = compute_research_importance_model(item)
        item["research_scores"] = score_dict
        item["research_importance_score"] = score_dict["total_score"]
        evaluated.append(item)

    print(f"Fundamental Candidates Evaluated: {len(evaluated)}")
    print(f"Dropped Canonical Events: {len(dropped_clusters)}")

    # Let's inspect dropped clusters and specifically our targets
    targets = [
        "omaxe", "clean max", "cleanmax", "aequs", "signature global",
        "godrej prop", "godrej", "dredging", "sail", "augmont"
    ]

    print("\n--- TARGET INVESTIGATION ACROSS ALL RAW EVENTS ---")
    for t in targets:
        matches = [ev for ev in all_raw_events if t in (ev['title'] + " " + ev.get('summary', '')).lower()]
        print(f"\nTarget '{t}': {len(matches)} raw occurrences")
        for m in matches:
            print(f"  Title: {m['title'][:80]}")
            print(f"  Noise Survives: {m in material_events} (Noise reason: {m.get('noise_reason')})")
            if m in material_events:
                print(f"  Resolved: {m in resolved_events} (Drop reason: {m.get('drop_reason')})")

    print("\n--- SAMPLE OF DROPPED CANONICAL CLUSTERS ---")
    for cl, reason in dropped_clusters[:20]:
        print(f"Cluster '{cl.get('title', '')[:70]}' -> {reason}")

if __name__ == "__main__":
    run()
