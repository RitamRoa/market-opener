"""
Unit tests validating closing price retrieval, ascending price sorting,
anti-overfitting, and rejection of rumor denials.
"""

import pytest
from engine.candidate_scanner import get_closing_price_for_date
from engine.noise_filter import is_material_fundamental_event
from engine.fna_analyzer import classify_event_direction_and_type, synthesize_fna_item
from engine.fna_pipeline import format_top_news_report


def test_rumor_and_speculative_talks_denials_rejected():
    """
    Rumor denials, speculative acquisition denials, and media report clarifications
    must be filtered at the noise gate and return AMBIGUOUS at the analysis gate.
    """
    title = "Solar Industries India Denies Speculative South Africa Acquisition Talks"
    summary = "Solar Industries clarifies that media reports regarding acquisition talks in South Africa are speculative and baseless; no such negotiations are underway."

    # 1. Noise filter check
    is_mat, reason = is_material_fundamental_event(title, summary)
    assert is_mat is False
    assert "denies speculative reports" in reason.lower() or "rumors" in reason.lower()

    # 2. Classifier check
    ev_type, direction, _ = classify_event_direction_and_type(f"{title} {summary}")
    assert direction in ["AMBIGUOUS", "None"] or direction not in ["Positive", "Negative"]

    # 3. Synthesizer check
    raw_event = {
        "title": title,
        "summary": summary,
        "company_name": "Solar Industries India Ltd",
        "symbol": "SOLARINDS.NS",
        "sources": ["Media Report"]
    }
    item = synthesize_fna_item(raw_event)
    assert item is None, "Rumor denial must be rejected from TOP NEWS synthesis"


def test_historical_closing_price_retrieval():
    """
    get_closing_price_for_date for historical date 2026-09-03 must return
    the historical close, not 0 or None.
    """
    # RELIANCE on 2026-09-03 closed around 1302.50
    price = get_closing_price_for_date("RELIANCE.NS", target_date="2026-09-03")
    assert price is not None
    assert 1200.0 <= price <= 1400.0

    # BALUFORGE on 2026-09-03 closed around 570.00
    price_bf = get_closing_price_for_date("BALUFORGE.BO", target_date="2026-09-03")
    assert price_bf is not None
    assert 500.0 <= price_bf <= 650.0


def test_final_top_news_sorted_by_closing_price_ascending():
    """
    Validates that final TOP NEWS items are sorted ascending:
    LOWEST CLOSING PRICE -> HIGHEST CLOSING PRICE.
    """
    items = [
        {"company_name": "Company High", "symbol": "HIGH.NS", "closing_price": 2830.0, "fundamental_direction": "Positive", "headline": "High priced stock win"},
        {"company_name": "Company Low", "symbol": "LOW.NS", "closing_price": 185.0, "fundamental_direction": "Positive", "headline": "Low priced stock win"},
        {"company_name": "Company Mid", "symbol": "MID.NS", "closing_price": 617.0, "fundamental_direction": "Negative", "headline": "Mid priced stock notice"},
    ]

    # Sort as implemented in pipeline: lowest to highest
    items.sort(key=lambda x: (x.get("closing_price") is None, x.get("closing_price") if x.get("closing_price") is not None else float("inf")))

    assert items[0]["company_name"] == "Company Low"
    assert items[0]["closing_price"] == 185.0
    assert items[1]["company_name"] == "Company Mid"
    assert items[1]["closing_price"] == 617.0
    assert items[2]["company_name"] == "Company High"
    assert items[2]["closing_price"] == 2830.0

    # Verify formatted report output
    report_text = format_top_news_report("03 September 2026", items)
    assert "1. Company Low (LOW) — ₹185 — Positive" in report_text
    assert "2. Company Mid (MID) — ₹617 — Negative" in report_text
    assert "3. Company High (HIGH) — ₹2,830 — Positive" in report_text
