"""
Comprehensive Upgraded Tests for Indian Fundamental News & Analysis (FNA) CLI.

Validates:
1. Strict POSITIVE or NEGATIVE binary classification (zero 'Mixed' / 'Neutral').
2. Stale quarterly news rejection (e.g. FY24/FY23 articles resurfacing).
3. Broker target price / recommendation rejection.
4. Semantic financial parsing (PAT is never tagged as an order inflow).
5. Primary beneficiary / winning bidder resolution over awarding clients.
6. Zero forbidden boilerplate templates.
"""

import pytest
from engine.noise_filter import is_material_fundamental_event
from engine.entity_mapper import resolve_entity_from_text
from engine.financial_context import parse_semantic_financial_metrics, evaluate_relative_materiality
from engine.fna_analyzer import synthesize_fna_item, FORBIDDEN_PHRASES


def test_stale_news_rejection():
    stale_headlines = [
        ("ICICI Prudential Life Q4 FY24 net profit falls 26% to Rs 174 crore", "Earnings report for the quarter ended March 31, 2024."),
        ("Tata Motors FY24 net profit surges threefold to Rs 31,807 crore", "Annual report for financial year 2023-24."),
        ("Wipro Q3 FY23 results: Net profit up 2.8% to Rs 3,053 crore", "Quarterly numbers from FY23.")
    ]
    for title, summary in stale_headlines:
        is_mat, reason = is_material_fundamental_event(title, summary)
        assert is_mat is False, f"Stale headline should have been filtered: '{title}'. Reason: {reason}"
        assert "stale" in reason.lower() or "historical" in reason.lower()


def test_broker_target_rejection():
    broker_headlines = [
        ("Jefferies maintains Buy on Tata Motors, sets target price of Rs 1,150", "Brokerage sees 20% upside on CV recovery."),
        ("CLSA initiates coverage on Reliance Industries with Outperform rating", "Target price pegged at Rs 3,400."),
        ("Morgan Stanley overweight on ICICI Bank with target price of Rs 1,400", "Top sector pick for next 12 months.")
    ]
    for title, summary in broker_headlines:
        is_mat, reason = is_material_fundamental_event(title, summary)
        assert is_mat is False, f"Broker target should have been filtered: '{title}'. Reason: {reason}"
        assert "broker" in reason.lower() or "target" in reason.lower()


def test_primary_beneficiary_winning_bidder():
    # When GE Vernova / GE T&D wins a contract from Power Grid, it should resolve to GE Vernova
    text = "GE Vernova T&D India bags Rs 420 crore contract from Power Grid Corporation for 765kV substation"
    entity_meta, reason = resolve_entity_from_text(text)
    assert entity_meta is not None
    assert entity_meta["symbol"] == "GVT&D.NS", f"Expected GVT&D.NS but got {entity_meta['symbol']}"

    # Hindustan Copper resolution
    hc_text = "Hindustan Copper declared preferred bidder for Jharkhand commercial coal block"
    hc_meta, _ = resolve_entity_from_text(hc_text)
    assert hc_meta is not None
    assert hc_meta["symbol"] == "HINDCOPPER.NS"


def test_semantic_financial_parsing_pat_vs_order():
    # PAT headline should be parsed as PAT, not ORDER_VALUE
    pat_text = "ICICI Prudential Life PAT falls 26% to Rs 174 crore"
    metrics = parse_semantic_financial_metrics(pat_text)
    assert metrics["metric_type"] == "PAT"
    assert metrics["amount_cr"] == 174.0

    # Materiality analysis should reflect earnings, not order inflows
    mat_eval = evaluate_relative_materiality("ICICIPRULI.NS", pat_text)
    fin_text = mat_eval["financial_implication_text"]
    assert "inflow" not in fin_text.lower()
    assert "order" not in fin_text.lower()
    assert "pat" in fin_text.lower() or "profit" in fin_text.lower() or "earnings" in fin_text.lower()

    # Order win headline should be parsed as ORDER_VALUE
    order_text = "RVNL secures major EPC order worth Rs 903 crore from South Central Railway"
    order_metrics = parse_semantic_financial_metrics(order_text)
    assert order_metrics["metric_type"] == "ORDER_VALUE"
    assert order_metrics["amount_cr"] == 903.0


def test_strict_binary_classification():
    # Positive event
    pos_event = {
        "company_name": "Bharat Electronics",
        "symbol": "BEL.NS",
        "title": "DAC approves Rs 1.45 lakh crore defence acquisition proposals including EW systems",
        "summary": "Defence Ministry accords Acceptance of Necessity (AoN) for indigenous military hardware.",
        "sources": ["Press Information Bureau"]
    }
    pos_item = synthesize_fna_item(pos_event)
    assert pos_item is not None
    assert pos_item["fundamental_direction"] == "Positive"
    assert pos_item["fundamental_direction"] in ["Positive", "Negative"]
    assert pos_item["fundamental_direction"] not in ["Mixed", "Neutral"]

    # Negative event
    neg_event = {
        "company_name": "Cipla",
        "symbol": "CIPLA.NS",
        "title": "Cipla receives 4 Form 483 inspection observations from US FDA for Goa facility",
        "summary": "Procedural compliance observations issued at close of inspection.",
        "sources": ["Exchange Filing"]
    }
    neg_item = synthesize_fna_item(neg_event)
    assert neg_item is not None
    assert neg_item["fundamental_direction"] == "Negative"
    assert neg_item["fundamental_direction"] in ["Positive", "Negative"]

    # Ambiguous routine corporate event should be rejected (returns None)
    ambiguous_event = {
        "company_name": "Infosys",
        "symbol": "INFY.NS",
        "title": "Infosys holds annual analyst meet to discuss technological strategy",
        "summary": "Management hosted discussions on enterprise AI adoption without giving revised financial guidance.",
        "sources": ["Corporate Intimation"]
    }
    amb_item = synthesize_fna_item(ambiguous_event)
    assert amb_item is None, "Ambiguous event must return None and be rejected from FNA bulletin"


def test_zero_forbidden_boilerplate_templates():
    events_to_test = [
        {
            "company_name": "Larsen & Toubro",
            "symbol": "LT.NS",
            "title": "L&T Construction secures mega order worth Rs 4,500 crore for water treatment plant",
            "summary": "EPC contract entails engineering and execution over 36 months.",
            "sources": ["BSE Filing"]
        },
        {
            "company_name": "Dr. Reddy's Laboratories",
            "symbol": "DRREDDY.NS",
            "title": "Dr. Reddy's receives US FDA approval for generic oncology injectable",
            "summary": "Final approval granted for commercial sale in the US market.",
            "sources": ["US FDA"]
        }
    ]

    for ev in events_to_test:
        item = synthesize_fna_item(ev)
        assert item is not None
        why_text = item["why_it_matters"].lower()
        impact_text = item["fundamental_impact"].lower()
        full_text = f"{why_text} {impact_text}"

        for forbidden in FORBIDDEN_PHRASES:
            assert forbidden.lower() not in full_text, (
                f"Forbidden template phrase '{forbidden}' found in synthesized commentary!"
            )
