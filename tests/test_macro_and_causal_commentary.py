import pytest
from engine.macro_commentary import generate_macro_commentary, extract_macro_signals
from engine.sector_causal_engine import evaluate_sector_causal_chains
from engine.fna_pipeline import format_top_news_report

def test_macro_commentary_generation():
    raw_articles = [
        {"title": "Crude oil slips below $73 per barrel as Middle East tensions ease", "summary": "Brent crude fell 1.5% to $72.8 on supply glut concerns.", "source": "Reuters"},
        {"title": "US Fed begins two-day FOMC policy meeting, market prices 25 bps rate cut", "summary": "Federal Reserve officials gather to debate interest rate trajectories.", "source": "Bloomberg"},
        {"title": "GIFT Nifty signals flat to positive opening for domestic equities", "summary": "SGX / GIFT Nifty indicates modest uptick for benchmark indices.", "source": "Moneycontrol"}
    ]

    macro = generate_macro_commentary(raw_articles, "2026-09-17")
    assert macro is not None
    assert macro["candidate_type"] == "MACRO_COMMENTARY"
    assert "flowing_prose" in macro
    # Macro commentary must NOT have a stock ticker
    assert macro.get("symbol") in [None, ""]
    # Check that it contains flowing prose
    assert len(macro["flowing_prose"]) > 50

def test_sector_causal_chains():
    material_events = [
        {
            "title": "Government slashes windfall tax on crude petroleum to zero",
            "summary": "Special additional excise duty on crude cuts to nil boosting domestic upstream producers and downstream refiners.",
            "source": "PIB"
        }
    ]

    chains = evaluate_sector_causal_chains(material_events, "2026-09-17")
    assert len(chains) >= 1
    chain_item = chains[0]
    assert chain_item["candidate_type"] == "SECTOR_CAUSAL_COMMENTARY"
    assert "Oil & Gas" in chain_item["affected_sector"]
    assert "human_review_flag" in chain_item

def test_bulletin_formatting_no_tickers_no_sentiment_for_commentary():
    items = [
        {
            "candidate_type": "MACRO_COMMENTARY",
            "headline": "Global Market & Macro Context",
            "flowing_prose": "Global crude benchmarks softened as Brent hovered near $73 per barrel amid subdued demand cues. Meanwhile, anticipation of the US Federal Reserve's rate verdict kept currency markets rangebound."
        },
        {
            "candidate_type": "SECTOR_CAUSAL_COMMENTARY",
            "headline": "Windfall Tax Cut Transmission",
            "flowing_prose": "The reduction in domestic windfall taxes directly bolsters realized margins for refiners and upstream producers by eliminating export levy friction.",
            "causal_chain": "Windfall tax reduction -> Higher net realization per barrel -> Margin expansion for refiners",
            "human_review_flag": "Requires Review: Sector impact"
        },
        {
            "candidate_type": "COMPANY_EVENT",
            "company_name": "Mazagon Dock Shipbuilders Ltd",
            "symbol": "MAZDOCK.NS",
            "fundamental_direction": "Positive",
            "flowing_prose": "Mazagon Dock Shipbuilders signed a landmark Rs 27,000 Cr memorandum of understanding with a European defence shipbuilder."
        }
    ]

    report = format_top_news_report("17 September 2026", items)

    # 1. Macro commentary and sector causal chains are completely dropped from stock list (they have no ticker)
    assert "[GLOBAL & DOMESTIC MACRO]" not in report
    assert "[SECTOR CAUSAL CHAIN]" not in report

    # 2. Company stock is formatted as ranked list with official ticker
    assert "MAZDOCK — Positive" in report

