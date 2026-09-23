import pytest
from engine.candidate_engine import compute_research_importance_model, rank_daily_research_candidates

def test_mega_deal_outranks_small_deal():
    mega_deal = {
        "company_name": "Mazagon Dock Shipbuilders Ltd",
        "symbol": "MAZDOCK.NS",
        "event_type": "STRATEGIC_DEAL",
        "company_role": "contractor",
        "order_value_cr": 27000.0,
        "headline": "Mazagon Dock inks Rs 27,000 Cr MoU for construction of advanced vessels",
        "what_happened": "Mazagon Dock signed Rs 27,000 Cr MoU with international partner.",
        "why_it_matters": "Massive revenue visibility spanning multi-year delivery cycles.",
        "fundamental_direction": "Positive",
        "sources": "NSE Corporate Announcement"
    }

    small_deal = {
        "company_name": "Routine Infra Ltd",
        "symbol": "ROUTINE.NS",
        "event_type": "ORDER_CONTRACT",
        "company_role": "contractor",
        "order_value_cr": 63.0,
        "headline": "Routine Infra bags Rs 63 Cr civil construction order",
        "what_happened": "Company received routine domestic order worth Rs 63 Cr.",
        "why_it_matters": "Routine order intake.",
        "fundamental_direction": "Positive",
        "sources": "NSE Corporate Announcement"
    }

    mega_scores = compute_research_importance_model(mega_deal)
    small_scores = compute_research_importance_model(small_deal)

    assert mega_scores["total_score"] > small_scores["total_score"]
    # Check that mega deal receives high financial & strategic significance
    assert mega_scores["financial_significance"] >= 9.5
    assert mega_scores["strategic_significance"] >= 9.0
    # Difference should be decisive (at least 1.5 points higher)
    assert mega_scores["total_score"] - small_scores["total_score"] >= 1.5

    # When both compete for ranking, mega deal must be ranked first
    mega_deal["research_scores"] = mega_scores
    mega_deal["research_importance_score"] = mega_scores["total_score"]
    small_deal["research_scores"] = small_scores
    small_deal["research_importance_score"] = small_scores["total_score"]

    ranked = rank_daily_research_candidates([small_deal, mega_deal], max_items=1)
    assert len(ranked) == 1
    assert ranked[0]["symbol"] == "MAZDOCK.NS"
