import sys, os
sys.path.insert(0, os.path.abspath("."))
from engine.fna_analyzer import synthesize_fna_item
from engine.candidate_engine import compute_research_importance_model, assign_materiality_tier, is_genuinely_actionable_candidate

cluster = {
    "title": "Petronet LNG, Gruner Renewable to set up 10 CBG plants for Rs 1,200 crore - The Economic Times",
    "summary": "Petronet LNG Ltd and Gruner Renewable Energy have announced a 50:50 joint venture to invest Rs 1,200 crore to set up 10 compressed biogas (CBG) plants in India.",
    "source": "The Economic Times",
    "published_at": "Fri, 18 Sep 2026 06:30:00 GMT",
    "url": "https://economictimes.indiatimes.com/articleshow/123456.cms",
    "symbol": "PETRONET.NS",
    "company_name": "Petronet LNG Ltd",
    "sector": "Oil & Gas / LNG Infrastructure",
    "is_primary": False,
    "event_date": "2026-09-18"
}

item = synthesize_fna_item(cluster)
print("Synthesized item successfully created.")
if item:
    print("Direction:", item.get("fundamental_direction"))
    print("Event Type:", item.get("event_type"))
    scores = compute_research_importance_model(item)
    item["research_scores"] = scores
    item["research_importance_score"] = scores["total_score"]
    item["tier"] = assign_materiality_tier(item, scores["total_score"])
    print("Score:", item["research_importance_score"], "Tier:", item["tier"])
    act, reason = is_genuinely_actionable_candidate(item)
    print("Actionable:", act, reason)
