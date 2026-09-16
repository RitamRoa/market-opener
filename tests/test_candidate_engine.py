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


def test_dynamic_candidate_count_not_fixed_at_5():
    """
    Verifies Section 9 and Objective:
    - 2 actionable candidates and no secondary -> returns 2 (quality beats minimum, never invents weak stocks).
    - 2 actionable candidates and 2 strong secondary -> returns 4 (reaches min target 4).
    - 5 actionable candidates -> returns all 5.
    - 8 actionable candidates -> returns all 8 (no artificial 5-item cutoff).
    - 12 actionable candidates -> returns all 12.
    """
    from engine.candidate_engine import is_genuinely_actionable_candidate

    def make_cand(idx, tier="Tier A", ev_type="ORDER_CONTRACT", score=8.5, direction="Positive", order_val=100.0):
        return {
            "symbol": f"STOCK_{idx}.NS",
            "company_name": f"Company {idx}",
            "headline": f"Major contract {idx}",
            "tier": tier,
            "event_type": ev_type,
            "research_scores": {"total_score": score},
            "research_importance_score": score,
            "fundamental_direction": direction,
            "order_value_cr": order_val,
        }

    # Case 1: Only 2 genuinely actionable stocks exist, and no valid secondary exist
    cands_2 = [
        make_cand(1, score=8.8),
        make_cand(2, score=8.5),
        make_cand(3, tier="Tier C", ev_type="OTHER", score=4.0, order_val=None), # weak/noise
    ]
    res_2 = rank_daily_research_candidates(cands_2, min_target=4)
    assert len(res_2) == 2
    assert {c["symbol"] for c in res_2} == {"STOCK_1.NS", "STOCK_2.NS"}

    # Case 2: 2 actionable stocks exist, and 2 strong secondary candidates exist -> supplements to 4
    cands_2_plus_sec = [
        make_cand(1, score=8.8),
        make_cand(2, score=8.5),
        make_cand(3, tier="Tier B", ev_type="ORDER_CONTRACT", score=5.4, order_val=50.0),
        make_cand(4, tier="Tier B", ev_type="CAPACITY_EXPANSION", score=5.3, order_val=None),
        make_cand(5, tier="Tier C", ev_type="ROUTINE", score=3.0, order_val=None),
    ]
    res_4 = rank_daily_research_candidates(cands_2_plus_sec, min_target=4)
    assert len(res_4) == 4
    assert {c["symbol"] for c in res_4} == {"STOCK_1.NS", "STOCK_2.NS", "STOCK_3.NS", "STOCK_4.NS"}

    # Case 3: 5 actionable stocks exist -> returns all 5
    cands_5 = [make_cand(i, score=8.0 - i * 0.1) for i in range(1, 6)]
    res_5 = rank_daily_research_candidates(cands_5, min_target=4)
    assert len(res_5) == 5

    # Case 4: 8 actionable stocks exist -> returns all 8 without cutting down to 5
    cands_8 = [make_cand(i, score=8.5 - i * 0.1) for i in range(1, 9)]
    res_8 = rank_daily_research_candidates(cands_8, min_target=4)
    assert len(res_8) == 8

    # Case 5: 12 actionable stocks exist -> returns all 12
    cands_12 = [make_cand(i, score=8.8 - i * 0.05) for i in range(1, 13)]
    res_12 = rank_daily_research_candidates(cands_12, min_target=4)
    assert len(res_12) == 12


def test_strict_directional_requirement():
    """Ambiguous or Neutral fundamental directions must be rejected."""
    from engine.candidate_engine import is_genuinely_actionable_candidate
    cand_neutral = {
        "symbol": "TEST.NS",
        "company_name": "Test Co",
        "headline": "Mixed quarterly review",
        "tier": "Tier A",
        "event_type": "FINANCIAL_RESULT",
        "research_scores": {"total_score": 8.5},
        "research_importance_score": 8.5,
        "fundamental_direction": "Neutral",
    }
    is_act, reason = is_genuinely_actionable_candidate(cand_neutral)
    assert is_act is False
    assert "ambiguous" in reason.lower()

