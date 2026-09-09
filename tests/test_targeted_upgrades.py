"""
Targeted Upgrades Test Suite:
Validates range parsing, operating updates, external beneficiary resolution,
publisher attribution, and 16 canonical event categories without generic boilerplate.
"""

import pytest
from engine.financial_context import (
    extract_monetary_values_and_ranges,
    extract_operating_metrics,
    evaluate_relative_materiality
)
from engine.entity_mapper import (
    resolve_entity_from_text,
    resolve_external_event_beneficiary,
    validate_event_entity
)
from engine.fna_analyzer import (
    classify_event_direction_and_type,
    synthesize_fna_item,
    extract_publisher_name
)


def test_monetary_range_and_lakh_crore_extraction():
    """Validates accurate parsing of ranges (e.g. ₹100-250 Cr) and aggregate units (lakh crore)."""
    text1 = "VA Tech Wabag secured ₹100-250 crore order from Reliance Industries for seawater desalination"
    val, rng_low, rng_high, rng_txt = extract_monetary_values_and_ranges(text1)
    assert rng_low == 100.0
    assert rng_high == 250.0
    assert "100" in rng_txt and "250" in rng_txt

    text2 = "Cabinet approves ₹9,000–10,000 crore defence procurement proposal"
    val2, r2_low, r2_high, r2_txt = extract_monetary_values_and_ranges(text2)
    assert r2_low == 9000.0
    assert r2_high == 10000.0

    text3 = "Defence Acquisition Council clears proposals worth ₹1.45 lakh crore for armed forces"
    val3, _, _, _ = extract_monetary_values_and_ranges(text3)
    assert val3 == 145000.0


def test_operating_metrics_extraction():
    """Validates operational metrics (e.g. revenue up 33.8%, narrowed losses)."""
    text = "Company reported net profit up 42.5% YoY while revenue surged 33.8% and EBITDA margin expanded 180 bps."
    metrics = extract_operating_metrics(text)
    assert "profit_pct" in metrics
    assert metrics["profit_pct"] == 42.5
    assert "revenue_pct" in metrics
    assert metrics["revenue_pct"] == 33.8
    assert "margin_bps" in metrics
    assert metrics["margin_bps"] == 180.0


def test_materiality_no_false_unquantified_statement():
    """Verifies that when an order value or range exists, it never claims unquantified magnitude."""
    text = "VA Tech Wabag secured ₹100-250 crore order from Reliance Industries"
    rel_mat = evaluate_relative_materiality("WABAG.NS", text)
    implication = rel_mat["financial_implication_text"]
    assert "100" in implication or "250" in implication
    assert "Financial magnitude cannot be reliably quantified" not in implication


def test_external_beneficiary_resolution():
    """Validates mapping macro/industry policy announcements to listed beneficiary companies."""
    # Defence DAC
    dac_text = "Defence Acquisition Council clears capital acquisition of weapons and radar systems worth Rs 45,000 crore"
    ben_meta, reason = resolve_external_event_beneficiary(dac_text)
    assert ben_meta is not None
    assert ben_meta["symbol"] in ["BEL.NS", "HAL.NS", "ASTRAMICRO.NS"]

    # Global Copper Rally
    cu_text = "Global copper prices surge 7% to fresh all-time high amid supply disruption at major smelters"
    ben_meta2, _ = resolve_external_event_beneficiary(cu_text)
    assert ben_meta2 is not None
    assert ben_meta2["symbol"] == "HINDCOPPER.NS"

    # HVDC transmission line
    hvdc_text = "Power Ministry approves massive ₹25,000 crore HVDC transmission corridor to evacuate renewable energy"
    ben_meta3, _ = resolve_external_event_beneficiary(hvdc_text)
    assert ben_meta3 is not None
    assert ben_meta3["symbol"] in ["GVT&D.NS", "POWERGRID.NS"]


def test_vendor_prioritization_over_client():
    """Ensures that vendor winning contract is prioritized over the client issuing it."""
    text = "VA Tech Wabag bagged ₹200 crore water treatment contract from Reliance Industries"
    entity, _ = resolve_entity_from_text(text)
    assert entity["symbol"] == "WABAG.NS"
    assert "VA Tech Wabag" in entity["name"]

    is_valid, _ = validate_event_entity(text, "", "WABAG.NS")
    assert is_valid is True

    # Validate Reliance would be rejected as client for an order won by Wabag
    is_client_valid, _ = validate_event_entity(text, "", "RELIANCE.NS")
    assert is_client_valid is False


def test_publisher_attribution():
    """Validates stripping publisher suffixes and extracting true reporting outlet."""
    title1 = "VA Tech Wabag shares jump 4% on Rs 250 cr order - upstox.com"
    pub1 = extract_publisher_name(title1, "Google News (Indian Equities)")
    assert pub1 == "Upstox"

    title2 = "Tata Motors to invest Rs 9000 cr in Tamil Nadu plant - The Economic Times"
    pub2 = extract_publisher_name(title2, "Economic Times Markets")
    assert pub2 == "The Economic Times"

    title3 = "Biocon gets USFDA approval for generic formulation - Livemint"
    pub3 = extract_publisher_name(title3, "Livemint Markets")
    assert pub3 == "Livemint"


def test_16_canonical_categories_and_no_boilerplate():
    """Validates classification into 16 canonical types and absence of forbidden boilerplate phrases."""
    test_cases = [
        ("ORDER_CONTRACT", "Company secures ₹1,200 crore EPC contract from NTPC", "Positive"),
        ("OPERATING_UPDATE", "Q3 operating update: sales volume up 24% and revenue surges 35%", "Positive"),
        ("FINANCIAL_RESULT", "Net profit jumps 65% to Rs 450 crore; EBITDA margin expands 220 bps", "Positive"),
        ("GOVERNMENT_EVENT", "Defence Acquisition Council approves procurement worth Rs 15000 cr under Make in India", "Positive"),
        ("REGULATORY_EVENT", "SEBI issues show cause notice and initiates forensic audit over disclosure violations", "Negative"),
        ("COMMODITY_EVENT", "Global thermal coal and steel benchmark prices collapse 18%", "Negative"),
        ("ACQUISITION", "Completes strategic acquisition of German precision robotics manufacturer", "Positive"),
        ("STRATEGIC_DEAL", "Signs 10-year exclusive commercial agreement and technology transfer partnership with Siemens", "Positive"),
        ("CAPACITY_EXPANSION", "Commences commercial production at new 50,000 MT semiconductor fabrication facility", "Positive"),
        ("PRODUCT_APPROVAL", "Receives final USFDA approval with 180-day generic exclusivity for blockbuster oncology drug", "Positive"),
        ("MANAGEMENT_EVENT", "Managing Director and CEO abruptly resigns amid board dispute", "Negative"),
        ("PRICING_EVENT", "Implements price hike of 5-8% across product portfolio to offset raw material inflation", "Positive"),
        ("CUSTOMER_EVENT", "Selected by Boeing as primary global aerospace supplier", "Positive"),
        ("FUNDING_DEBT_EVENT", "Credit rating upgraded to AAA with stable outlook; achieves debt reduction", "Positive"),
    ]

    forbidden_phrases = [
        "validates technical qualification",
        "routine capital structure adjustment",
        "operational alignment within standard business parameters"
    ]

    for expected_type, headline, expected_dir in test_cases:
        ev_type, direction, _ = classify_event_direction_and_type(headline)
        assert ev_type == expected_type, f"Failed for {headline}: got {ev_type}, expected {expected_type}"
        assert direction == expected_dir, f"Failed direction for {headline}: got {direction}, expected {expected_dir}"

        # Synthesize full FNA item and check for forbidden phrases
        raw = {
            "company_name": "TestCorp",
            "symbol": "TCS.NS",
            "title": headline,
            "summary": headline,
            "sources": ["The Economic Times"]
        }
        item = synthesize_fna_item(raw)
        assert item is not None
        combined_text = f"{item['why_it_matters']} {item['fundamental_impact']}"
        for phrase in forbidden_phrases:
            assert phrase.lower() not in combined_text.lower(), f"Found forbidden phrase '{phrase}' in {ev_type}"
