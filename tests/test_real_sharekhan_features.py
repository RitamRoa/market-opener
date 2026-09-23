"""
Unit tests for the Sharekhan real-world feature enhancements:
1. Price-fetch gate removal: unlisted / failed price candidate is retained, not omitted.
2. Policy/regulatory event detection and multi-company beneficiary list formatting.
3. Standalone macro market-context trigger detection and one-liner formatting.
4. Specificity scoring: rewarding concrete numbers & hard binary outcomes vs vague qualitative text.
"""

import pytest
from engine.policy_macro_engine import detect_policy_event, detect_macro_item, SECTOR_MEMBERS
from engine.candidate_engine import compute_research_importance_model, is_genuinely_actionable_candidate
from engine.fna_pipeline import format_top_news_report


def test_price_fetch_gate_removal_preserves_candidate():
    """Candidates without closing price must be retained and formatted without error."""
    items = [
        {
            "company_name": "Saatvik Green Energy Ltd",
            "symbol": "SAATVIK.BO",
            "headline": "Secures ₹450 Cr solar module contract",
            "what_happened": "Saatvik Green Energy secured ₹450 Cr module order.",
            "why_it_matters": "Expands order book and revenue visibility.",
            "fundamental_impact": "Positive — order book expansion.",
            "key_financial_implication": "Adds ₹450 Cr to executable backlog.",
            "time_horizon": "Medium Term",
            "sources": "BSE Announcement",
            "fundamental_direction": "Positive",
            "closing_price": None, # Price lookup failed or unlisted
        }
    ]
    report = format_top_news_report("16 September 2026", items)
    assert "SAATVIK" in report
    assert "Positive" in report
    assert "₹450 Cr" in report
    assert "₹None" not in report
    assert "What happened:" not in report
    assert "Why it matters:" not in report
    assert "Sources:" not in report


def test_policy_event_detection_and_formatting():
    """Policy notifications affecting sectors must resolve to multi-company beneficiary entries and be omitted from stock list."""
    policy_ev = {
        "title": "NPCI and RBI mandate 1.1% interchange fee on UPI merchant transactions above Rs 2000",
        "summary": "The Reserve Bank of India and NPCI issued a circular introducing a 1.1% interchange fee on prepaid merchant UPI transactions.",
        "source": "RBI Circular / NPCI Release",
        "published_at": "2026-09-16T10:00:00+05:30",
    }
    detected = detect_policy_event(policy_ev)
    assert detected is not None
    assert detected["candidate_type"] == "POLICY_EVENT"
    assert detected["sector"] == "UPI_PAYMENTS"
    assert len(detected["key_beneficiaries"]) >= 3
    assert any(b["symbol"] == "PAYTM" for b in detected["key_beneficiaries"])

    # Stock list report drops policy items without tickers
    report = format_top_news_report("16 September 2026", [detected])
    assert "[POLICY & REGULATORY]" not in report


def test_macro_item_detection_and_formatting():
    """Standalone macro triggers must be detected and formatted into concise one-liners."""
    # US 10-year yield trigger
    macro_yield_ev = {
        "title": "US 10-year Treasury yield crosses 5%, highest since 2007",
        "summary": "Benchmark US 10-year bond yields surged above 5.02% amid persistent inflationary pressures.",
        "source": "Reuters Global Wire",
        "published_at": "2026-09-16T12:00:00+05:30",
    }
    detected_yield = detect_macro_item(macro_yield_ev)
    assert detected_yield is not None
    assert detected_yield["candidate_type"] == "MACRO_EVENT"
    assert detected_yield["fundamental_direction"] == "Negative"

    # Crude oil spike trigger
    crude_ev = {
        "title": "Brent crude oil crosses $90 per barrel on Middle East supply disruption",
        "summary": "Brent crude futures rallied past $90.50 per barrel, raising raw material cost concerns.",
        "source": "Commodities News",
        "published_at": "2026-09-16T14:00:00+05:30",
    }
    detected_crude = detect_macro_item(crude_ev)
    assert detected_crude is not None
    assert detected_crude["candidate_type"] == "MACRO_EVENT"
    assert "Paints" in detected_crude["affected_sector"] or "Aviation" in detected_crude["affected_sector"]

    # Stock list report drops macro items (they have no ticker)
    report = format_top_news_report("16 September 2026", [detected_yield, detected_crude])
    assert "[MACRO CONTEXT]" not in report


def test_tightened_specificity_scoring():
    """Concrete numbers & hard binary outcomes must score significantly higher than vague qualitative text."""
    concrete_cand = {
        "headline": "Secures ₹1,200 Cr EPC order for 300 MW solar plant in Gujarat",
        "what_happened": "Company bags ₹1,200 crore turnkey solar EPC contract with 300 MW capacity.",
        "event_type": "ORDER_CONTRACT",
        "order_value_cr": 1200.0,
        "revenue_cr": 3000.0,
        "fundamental_direction": "Positive",
        "sources": "NSE Corporate Announcement",
    }
    concrete_scores = compute_research_importance_model(concrete_cand)

    vague_cand = {
        "headline": "Strengthens market position through strategic expansion initiatives",
        "what_happened": "Company continues to demonstrate positive momentum and explores strategic avenues for growth.",
        "event_type": "GENERAL_UPDATE",
        "order_value_cr": None,
        "revenue_cr": 3000.0,
        "fundamental_direction": "Positive",
        "sources": "Press Release",
    }
    vague_scores = compute_research_importance_model(vague_cand)

    assert concrete_scores["quantifiability"] >= 9.0
    assert vague_scores["quantifiability"] <= 3.5
    assert concrete_scores["has_concrete_numbers"] is True
    assert concrete_scores["has_binary_outcome"] is True
    assert vague_scores["is_purely_qualitative"] is True
    assert concrete_scores["total_score"] > vague_scores["total_score"] + 2.0

    # Concrete candidate must be actionable, vague candidate must be rejected
    concrete_cand["research_scores"] = concrete_scores
    concrete_cand["tier"] = "Tier A"
    is_act_conc, _ = is_genuinely_actionable_candidate(concrete_cand)
    assert is_act_conc is True

    vague_cand["research_scores"] = vague_scores
    vague_cand["tier"] = "Tier C"
    is_act_vague, reason = is_genuinely_actionable_candidate(vague_cand)
    assert is_act_vague is False
    assert "purely qualitative" in reason.lower() or "threshold" in reason.lower()


def test_simplified_flowing_prose_output_format():
    """
    Validates Gap 4 fix:
    - 2-5 flowing sentences per item matching Sharekhan's actual style.
    - Zero section headers (What happened, Why it matters, Fundamental impact, etc.).
    - No price shown in the header — just company name and a Positive/Negative tag.
    - Numbers and mechanism folded directly into the narrative.
    """
    items = [
        {
            "company_name": "Mazagon Dock Shipbuilders Ltd",
            "symbol": "MAZDOCK.NS",
            "headline": "Secures ₹1,486 Cr offshore pipeline contract from ONGC",
            "what_happened": "Mazagon Dock Shipbuilders has announced: Mazagon Dock bags Rs 1,486-crore contract from ONGC.",
            "why_it_matters": "Securing this contract valued at ₹1,486.0 Cr from ONGC expands the executable order book and provides firm revenue visibility.",
            "fundamental_impact": "Positive — reinforces executable order book and revenue visibility.",
            "key_financial_implication": "The contract adds ₹1,486.0 Cr to executable order backlog, with revenue recognized across execution milestones over the project period.",
            "time_horizon": "Medium Term",
            "sources": "NSE Announcement",
            "fundamental_direction": "Positive",
            "closing_price": 2236.0,
        },
        {
            "company_name": "Neogen Chemicals Ltd",
            "symbol": "NEOGEN.NS",
            "headline": "Signs JV agreement with MU Ionic Solutions for EV battery electrolytes",
            "what_happened": "Neogen Chemicals has entered into an agreement with MU Ionic Solutions for electrolyte manufacturing technology.",
            "why_it_matters": "Entering into a Joint Venture agreement with MU Ionic Solutions establishes strategic collaboration, combining technical capabilities and market access.",
            "fundamental_impact": "Positive — establishes strategic commercial alignment.",
            "key_financial_implication": "Financial realization will depend on capitalization of the JV entity and subsequent commercial production ramp-up.",
            "time_horizon": "Long Term",
            "sources": "BSE Filing",
            "fundamental_direction": "Positive",
            "closing_price": 1820.0,
        },
    ]

    report = format_top_news_report("16 September 2026", items)

    # 1. Verify ranked ticker output format: 1. TICKER — Positive/Negative — one-line reason
    assert "1. MAZDOCK — Positive —" in report
    assert "2. NEOGEN — Positive —" in report
    assert "₹2,236" not in report
    assert "₹1,820" not in report

    # 2. Verify complete absence of multi-section template headers
    for forbidden_header in [
        "What happened:",
        "Why it matters:",
        "Fundamental impact:",
        "Key financial implication:",
        "Time horizon:",
        "Sources:",
    ]:
        assert forbidden_header not in report, f"Section header '{forbidden_header}' must not appear in report"

    # 3. Verify one-line reasons fold numbers and key figures
    assert "₹1,486" in report
    assert "MU Ionic Solutions" in report

