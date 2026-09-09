"""
Test suite for Indian Stock Market Intelligence Engine components.
Validates zero-API-key modules, entity mapping, event detection, priced-in check, and scoring.
"""

import pytest
from engine.entity_mapper import match_company_in_text, get_company_meta
from engine.event_detector import detect_event_type_and_sentiment
from engine.priced_in import evaluate_priced_in
from engine.deduplicator import is_noise_article, deduplicate_and_cluster_news
from engine.scorer import score_deep_stock


def test_entity_mapper():
    matches = match_company_in_text("Reliance Industries bags multi-crore green energy project")
    assert len(matches) > 0
    assert matches[0]["symbol"] == "RELIANCE.NS"

    matches_tatamotors = match_company_in_text("Tata Motors reports strong JLR wholesale deliveries")
    assert any(m["symbol"] == "TATAMOTORS.NS" for m in matches_tatamotors)

    meta = get_company_meta("HAL.NS")
    assert "Hindustan Aeronautics" in meta["name"]


def test_event_detector():
    ev_type, sentiment, mat = detect_event_type_and_sentiment("HAL secures Rs 26,000 crore defense contract from MoD")
    assert ev_type == "Contract / Order Win"
    assert sentiment == "POSITIVE"
    assert mat >= 0.80

    ev_type_neg, sent_neg, mat_neg = detect_event_type_and_sentiment("SEBI imposes penalty on company for disclosure lapses")
    assert ev_type_neg == "Regulatory & Legal Action"
    assert sent_neg == "NEGATIVE"
    assert mat_neg >= 0.90


def test_noise_filter():
    assert is_noise_article("Top 5 stocks to buy today for 20% return") == True
    assert is_noise_article("Hot stocks: Wealth creators to buy this week") == True
    assert is_noise_article("Larsen & Toubro wins major hydrocarbon contract in Middle East") == False


def test_priced_in_check():
    # Stock with huge 1M run-up before positive news should have high priced-in score
    stock_runup = {"ret_5d": 12.0, "ret_1m": 25.0, "volume_ratio": 3.0, "pe_ratio": 70.0}
    event_pos = {"sentiment": "POSITIVE"}
    score, rationale, _ = evaluate_priced_in(stock_runup, event_pos)
    assert score >= 7.0
    assert "Extremely priced in" in rationale

    # Fresh unpriced event on beaten-down stock
    stock_lagging = {"ret_5d": -1.0, "ret_1m": -8.0, "volume_ratio": 1.1, "pe_ratio": 15.0}
    score_fresh, rationale_fresh, _ = evaluate_priced_in(stock_lagging, event_pos)
    assert score_fresh <= 4.0
    assert "Not priced in" in rationale_fresh


def test_opportunity_scorer():
    analyzed_stock = {
        "symbol": "HAL.NS",
        "company": "Hindustan Aeronautics Ltd",
        "sector": "Aerospace & Defense",
        "event_type": "Contract / Order Win",
        "sentiment": "POSITIVE",
        "materiality": 0.85,
        "main_event": "HAL secures new fighter jet avionics order",
        "ret_1d": 1.8,
        "ret_1m": 4.5,
        "volume_ratio": 2.2,
        "priced_in_score": 3.5,
        "deep_financials": {"pe_ratio": 32.0},
        "fundamental_impact": {"overall_impact": 8.5},
        "historical_comparison": "Historical comparison: Insufficient data",
        "sources": ["NSE Announcement", "Economic Times"],
        "is_primary": True,
        "valid_price": True
    }
    market_context = {"regime": "Bullish"}

    scored = score_deep_stock(analyzed_stock, market_context)
    assert 0.0 <= scored["opportunity_score"] <= 100.0
    assert 0.0 <= scored["confidence_score"] <= 100.0
    assert "bull_case" in scored
    assert "bear_case" in scored
    assert "[FACT]" in scored["bull_case"]
