import sys, os
sys.path.insert(0, os.path.abspath("."))
from engine.news_collector import collect_market_news
from engine.noise_filter import is_material_fundamental_event
from engine.entity_mapper import resolve_entity_from_text
from engine.fna_analyzer import classify_event_direction_and_type
from engine.candidate_engine import compute_research_importance_model, is_genuinely_actionable_candidate

target_date = "2026-09-18"
articles = collect_market_news(target_date=target_date)
print(f"Total articles retrieved for {target_date}: {len(articles)}")

for art in articles:
    title = art.get("title", "")
    summary = art.get("summary", "")
    text = f"{title} {summary}".strip()
    if any(k in text.lower() for k in ["petronet", "gruner", "mazagon", "mdl", "dighi", "pakistan"]):
        is_mat, mat_reason = is_material_fundamental_event(title, summary, False, art.get("published_at", ""))
        entity, conf_ent = resolve_entity_from_text(text, art.get("symbol"))
        ev_dir, ev_type, conf = classify_event_direction_and_type(text)
        
        cand = {
            "title": title,
            "headline": title,
            "summary": summary,
            "source": art.get("source"),
            "published_at": art.get("published_at"),
            "symbol": entity.get("symbol") if entity else "UNKNOWN.NS",
            "company_name": entity.get("name") if entity else "Unknown",
            "event_type": ev_type,
            "direction": ev_dir,
            "event_date": target_date
        }
        res = compute_research_importance_model(cand)
        cand.update(res)
        is_act, act_reason = is_genuinely_actionable_candidate(cand)
        
        print("\n-------------------------")
        safe_title = title.encode("ascii", errors="replace").decode("ascii")
        print(f"TITLE: {safe_title}")
        print(f"SOURCE: {art.get('source')}")
        print(f"MATERIAL: {is_mat} (Reason: {mat_reason})")
        print(f"ENTITY: {entity.get('name') if entity else None} ({entity.get('symbol') if entity else None})")
        print(f"EVENT: {ev_type}, {ev_dir}, conf: {conf}")
        print(f"SCORE: {cand.get('final_score')}, TIER: {cand.get('materiality_tier')}, ACTIONABLE: {is_act} ({act_reason})")
