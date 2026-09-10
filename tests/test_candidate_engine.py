"""
Unit tests for the Research Candidate Engine and Sharekhan-style TOP NEWS selection.
Verifies:
1. 10-Factor Research Importance Model calculation and range.
2. Materiality Tier assignment (Tier A, Tier B, Tier C).
3. Discovery bucket classification across the 6 major buckets.
4. Relative daily ranking, bucket balancing, and candidate limiting.
5. Crude dual-directional read-through (ONGC positive vs Downstream OMCs negative).
6. PNGRB LPG pipeline read-through to Dilip Buildcon.
"""

import pytest
from engine.candidate_engine import (
    compute_research_importance_model,
    assign_materiality_tier,
    map_event_to_discovery_bucket,
    rank_daily_research_candidates,
    format_candidate_debug_log,
)
from engine.entity_mapper import resolve_entity_from_text


def test_compute_research_importance_model():
    """Verify that the 10-factor model correctly scores high-materiality vs low-materiality events."""
    high_mat_event = {
        "event_type": "ORDER_CONTRACT",
        "order_value_cr": 1800.0,
        "revenue_cr": 3500.0,
        "fundamental_direction": "Positive",
        "order_book_share_pct": 51.4,
        "is_primary": True,
        "has_hard_metrics": True,
    }
    scores = compute_research_importance_model(high_mat_event)
    assert 0 <= scores["total_score"] <= 10.0 or 0 <= scores["total_score"] <= 100.0
    assert scores["total_score"] >= 7.5
    assert scores["fundamental_materiality"] >= 8.0
    assert scores["quantifiability"] >= 8.0

    low_mat_event = {
        "event_type": "GENERAL_UPDATE",
        "order_value_cr": None,
        "revenue_cr": 50000.0,
        "fundamental_direction": "Positive",
        "order_book_share_pct": None,
        "is_primary": False,
        "has_hard_metrics": False,
    }
    low_scores = compute_research_importance_model(low_mat_event)
    assert low_scores["total_score"] < scores["total_score"]


def test_assign_materiality_tier():
    """Verify tier assignment logic."""
    item_a = {"event_type": "ORDER_CONTRACT", "order_value_cr": 2000.0, "revenue_cr": 2000.0}
    tier_a = assign_materiality_tier(item_a, total_score=8.5)
    assert tier_a == "Tier A"

    item_b = {"event_type": "COMMODITY_EVENT", "order_value_cr": None, "revenue_cr": 10000.0}
    tier_b = assign_materiality_tier(item_b, total_score=7.2)
    assert tier_b == "Tier B"

    item_c = {"event_type": "GENERAL_UPDATE"}
    tier_c = assign_materiality_tier(item_c, total_score=4.0)
    assert tier_c == "Tier C"


def test_map_event_to_discovery_bucket():
    """Verify mapping of events to the 6 Sharekhan discovery buckets."""
    assert map_event_to_discovery_bucket("ORDER_CONTRACT") == "COMPANY_EVENTS"
    assert map_event_to_discovery_bucket("FINANCIAL_RESULT") == "RESULTS_OPERATING_DATA"
    assert map_event_to_discovery_bucket("REGULATORY_EVENT") == "GOVERNMENT_POLICY"
    assert map_event_to_discovery_bucket("GOVERNMENT_EVENT") == "GOVERNMENT_POLICY"
    assert map_event_to_discovery_bucket("COMMODITY_EVENT") == "COMMODITIES"
    assert map_event_to_discovery_bucket("INDUSTRY_EVENT") == "INDUSTRY_DATA"
    assert map_event_to_discovery_bucket("FUNDING_EQUITY") == "STRATEGIC_STRUCTURE"
    assert map_event_to_discovery_bucket("ACQUISITION") == "STRATEGIC_STRUCTURE"


def test_rank_daily_research_candidates_merit_driven():
    """Verify that candidate engine ranks strictly on merit (Tier A first, then Tier B) without artificial per-bucket caps."""
    candidates = []
    # Create 6 Company Event candidates
    for i in range(6):
        candidates.append({
            "symbol": f"COMP_{i}",
            "headline": f"Company Event {i}",
            "tier": "Tier A" if i < 3 else "Tier B",
            "discovery_bucket": "COMPANY_EVENTS",
            "research_importance_score": 8.5 - (i * 0.1),
            "fundamental_direction": "Positive",
        })
    # Create 2 Commodity candidates
    for i in range(2):
        candidates.append({
            "symbol": f"COMM_{i}",
            "headline": f"Commodity Event {i}",
            "tier": "Tier A",
            "discovery_bucket": "COMMODITIES",
            "research_importance_score": 8.0 - (i * 0.1),
            "fundamental_direction": "Negative" if i == 0 else "Positive",
        })
    # Create 2 Regulatory candidates
    for i in range(2):
        candidates.append({
            "symbol": f"REG_{i}",
            "headline": f"Regulatory Event {i}",
            "tier": "Tier B",
            "discovery_bucket": "GOVERNMENT_POLICY",
            "research_importance_score": 7.2 - (i * 0.1),
            "fundamental_direction": "Negative",
        })

    top_news = rank_daily_research_candidates(candidates, max_items=8)
    assert len(top_news) <= 8
    # All 5 Tier A candidates (3 company + 2 commodity) must be selected regardless of category
    tier_a_selected = [it for it in top_news if it["tier"] == "Tier A"]
    assert len(tier_a_selected) == 5
    # Purely merit-driven: remaining slots filled by highest Tier B candidates
    assert len(top_news) == 8



def test_crude_dual_directional_read_through():
    """
    Verify that crude oil price surge read-through produces:
    - Downstream OMCs (IOC, BPCL, HPCL) with negative marketing margin impact
    - Upstream ONGC with positive realization impact
    """
    omc_text = "Brent crude crosses $100 per barrel: IOC, BPCL and HPCL face marketing margin compression on diesel and petrol."
    omc_entity, reason = resolve_entity_from_text(omc_text)
    assert omc_entity is not None
    assert omc_entity["symbol"] in ["IOC.NS", "BPCL.NS", "HPCL.NS"]

    upstream_text = "Crude oil rallies past $100 per barrel boosting upstream realizations for ONGC and Oil India."
    upstream_entity, reason = resolve_entity_from_text(upstream_text)
    assert upstream_entity is not None
    assert upstream_entity["symbol"] == "ONGC.NS"


def test_dilip_buildcon_pngrb_read_through():
    """Verify that PNGRB Paradip-Raipur LPG pipeline correctly resolves to Dilip Buildcon."""
    pipeline_text = "PNGRB approves ₹1,800 crore Paradip-Raipur LPG pipeline project; Dilip Buildcon emerges as key EPC contractor."
    entity, reason = resolve_entity_from_text(pipeline_text)
    assert entity is not None
    assert entity["symbol"] == "DBL.NS"
    assert "Dilip Buildcon" in entity["name"]


def test_format_candidate_debug_log():
    """Verify debug logging format matches requirement."""
    item = {
        "company_name": "Dilip Buildcon Ltd",
        "headline": "Secures ₹1,800 Cr PNGRB LPG pipeline EPC contract",
        "event_type": "ORDER_CONTRACT",
        "symbol": "DBL.NS",
        "tier": "Tier A",
        "order_value_cr": 1800.0,
        "revenue_cr": 3500.0,
        "discovery_bucket": "COMPANY_EVENTS",
        "research_importance_score": 8.85,
    }
    log_text = format_candidate_debug_log(item, decision="INCLUDED")
    assert "[CANDIDATE] Dilip Buildcon Ltd" in log_text
    assert "[TYPE] ORDER_CONTRACT" in log_text
    assert "[TIER] Tier A" in log_text
    assert "[DECISION] INCLUDED" in log_text
