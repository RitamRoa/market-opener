import pytest
from datetime import datetime
import zoneinfo
from engine.fna_pipeline import parse_datetime_ist, split_multi_company_article, run_fna_pipeline

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

def test_parse_datetime_ist():
    """Verify various datetime string formats parse correctly to IST."""
    # RFC 2822
    dt1 = parse_datetime_ist("Wed, 09 Sep 2026 10:00:00 GMT")
    assert dt1 is not None
    assert dt1.tzinfo is not None
    assert dt1.astimezone(IST).day == 9

    # ISO 8601
    dt2 = parse_datetime_ist("2026-09-08T14:30:00+05:30")
    assert dt2 is not None
    assert dt2.astimezone(IST).day == 8
    assert dt2.astimezone(IST).hour == 14

    # Date only
    dt3 = parse_datetime_ist("2026-09-06")
    assert dt3 is not None
    assert dt3.astimezone(IST).day == 6

def test_split_multi_company_article():
    """Verify that multi-company news roundups are split into individual company events."""
    event = {
        "title": "Stocks in News: NTPC, Tata Power, and Suzlon Energy in focus today",
        "company": "Market Roundup",
        "summary": "NTPC announced commissioning of solar unit. Tata Power signs pact for transmission. Suzlon secures 100MW wind order.",
        "text": "NTPC announced commissioning of 50MW solar unit. Tata Power signs pact for transmission line. Suzlon secures 100MW wind order.",
        "symbol": "",
        "timestamp": "2026-09-09T08:00:00+05:30",
        "source": "Moneycontrol"
    }
    split_events = split_multi_company_article(event)
    assert len(split_events) >= 2
    companies = [e["company"] for e in split_events]
    assert any("NTPC" in c for c in companies)
    assert any("Tata Power" in c for c in companies) or any("Suzlon" in c for c in companies)

def test_historical_mode_never_returns_today_data():
    """Requesting an archived historical date (e.g. 2026-09-06) must return records for that date, not today."""
    top_news, report_text = run_fna_pipeline(max_items=10, debug=False, target_date="2026-09-06")
    assert "06 September 2026" in report_text or "2026-09-06" in report_text
    for item in top_news:
        # Should not contain today's specific live items (like Hindustan Zinc e-trucks)
        assert "hindustan zinc" not in item.get("company_name", "").lower()

def test_historical_mode_empty_on_missing_date():
    """Requesting a historical date with no records must return empty top_news, NOT fall back to live feeds."""
    top_news, report_text = run_fna_pipeline(max_items=10, debug=False, target_date="2020-01-01")
    assert len(top_news) == 0
    assert "No verified corporate disclosures available" in report_text or "TOP NEWS COMPLETE" in report_text
