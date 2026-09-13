"""
Tests for Historical Date Reconstruction, Hard Cutoffs, and Anti-Leakage Pipeline.
Enforces:
1. No look-ahead leakage
2. Article published after target date is rejected
3. Article published on target date is accepted
4. Event date vs publication date handling
5. Current-day database entries cannot contaminate historical mode
6. Historical mode falls back across public sources
7. No fabricated historical data when evidence is unavailable
"""

import pytest
from datetime import datetime
import zoneinfo
from unittest.mock import patch, MagicMock

from engine.run_context import RunContext, set_current_context, get_current_context
from engine.fna_pipeline import parse_datetime_ist, run_fna_pipeline
from engine.nse_bse_client import get_historical_exchange_announcements
from engine.news_collector import build_historical_feed_registry, collect_historical_market_news

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


def test_article_published_on_target_date_accepted():
    """Article published on target date prior to cutoff must be accepted."""
    cutoff_dt = datetime.strptime("2026-09-01 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    ctx = RunContext(
        mode="historical",
        target_date="2026-09-01",
        cutoff_datetime=cutoff_dt,
        timezone="Asia/Kolkata"
    )

    # Published on target date at 14:30 IST
    pub_dt = datetime.strptime("2026-09-01 14:30:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    assert ctx.is_eligible(pub_dt) is True

    # Date-only on target date
    pub_date_only = datetime.strptime("2026-09-01", "%Y-%m-%d").replace(tzinfo=IST)
    assert ctx.is_eligible(pub_date_only) is True


def test_article_published_after_target_date_rejected():
    """Article published after target date (e.g. next day or today) must be rejected."""
    cutoff_dt = datetime.strptime("2026-09-01 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    ctx = RunContext(
        mode="historical",
        target_date="2026-09-01",
        cutoff_datetime=cutoff_dt,
        timezone="Asia/Kolkata"
    )

    # Next day
    next_day_dt = datetime.strptime("2026-09-02 09:15:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    assert ctx.is_eligible(next_day_dt) is False

    # Current day / Future
    future_dt = datetime.strptime("2026-09-10 12:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    assert ctx.is_eligible(future_dt) is False


def test_no_look_ahead_leakage_cutoff_time():
    """If exact cutoff time is specified (e.g. 15:30:00 IST), items published at 16:00:00 must be rejected."""
    cutoff_dt = datetime.strptime("2026-09-01 15:30:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    ctx = RunContext(
        mode="historical",
        target_date="2026-09-01",
        cutoff_datetime=cutoff_dt,
        timezone="Asia/Kolkata"
    )

    # Before cutoff
    before_dt = datetime.strptime("2026-09-01 15:29:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    assert ctx.is_eligible(before_dt) is True

    # After cutoff on same day
    after_dt = datetime.strptime("2026-09-01 15:30:01", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    assert ctx.is_eligible(after_dt) is False


def test_event_date_vs_publication_date_handling():
    """
    Prefer publication timestamp reflecting when info became publicly available.
    Retrospective articles published after target date must be rejected even if event happened earlier.
    """
    cutoff_dt = datetime.strptime("2026-09-01 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    ctx = RunContext(
        mode="historical",
        target_date="2026-09-01",
        cutoff_datetime=cutoff_dt,
        timezone="Asia/Kolkata"
    )

    # Retrospective article published on Sep 5 reporting an event from Sep 1
    pub_dt = datetime.strptime("2026-09-05 10:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    event_dt = datetime.strptime("2026-09-01 09:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)

    # Publication date is after target date -> must be rejected (not publicly available on Sep 1)
    assert ctx.is_eligible(pub_dt=pub_dt, event_dt=event_dt) is False

    # Event announced on Sep 1 (pub_dt Sep 1) for a contract taking effect Sep 15
    valid_pub_dt = datetime.strptime("2026-09-01 11:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    future_event_dt = datetime.strptime("2026-09-15 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    assert ctx.is_eligible(pub_dt=valid_pub_dt, event_dt=future_event_dt) is True


def test_current_day_database_entries_cannot_contaminate_historical_mode():
    """
    Current-day entries in news_cache or fna_events must be filtered out
    and never leak into a historical date reconstruction.
    """
    cutoff_dt = datetime.strptime("2026-09-01 23:59:59", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    ctx = RunContext(
        mode="historical",
        target_date="2026-09-01",
        cutoff_datetime=cutoff_dt,
        timezone="Asia/Kolkata"
    )

    # Simulated DB rows with mixed dates
    db_items = [
        {"title": "Today's Live News Item", "published_at": "2026-09-10 14:00:00"},
        {"title": "Yesterday's Event", "published_at": "2026-09-09 10:00:00"},
        {"title": "Historical Valid Sep 1 Event", "published_at": "2026-09-01 11:30:00"},
        {"title": "Historical Sep 2 Post-Cutoff Event", "published_at": "2026-09-02 08:00:00"},
    ]

    eligible_items = []
    for it in db_items:
        dt = parse_datetime_ist(it["published_at"])
        if dt and ctx.is_eligible(dt):
            eligible_items.append(it)

    assert len(eligible_items) == 1
    assert eligible_items[0]["title"] == "Historical Valid Sep 1 Event"


def test_historical_mode_falls_back_across_public_sources():
    """
    If NSE returns 0 or fails, BSE announcements are still queried and retrieved.
    """
    with patch("engine.nse_bse_client.fetch_nse_announcements_for_date", return_value=[]):
        with patch("engine.nse_bse_client.fetch_bse_announcements_for_date", return_value=[
            {
                "source": "BSE Announcements",
                "symbol": None,
                "raw_symbol": "500123",
                "company_name": "Test Engineering Ltd",
                "title": "Test Engineering Ltd: Secures Rs 500 crore project",
                "summary": "Secures EPC contract worth Rs 500 crore",
                "published_at": "2026-09-01T10:00:00",
                "is_primary": True
            }
        ]):
            items, counts = get_historical_exchange_announcements("2026-09-01")
            assert counts["NSE Corporate Announcements"] == 0
            assert counts["BSE Announcements"] == 1
            assert len(items) == 1
            assert items[0]["company_name"] == "Test Engineering Ltd"


def test_no_fabricated_historical_data_when_evidence_unavailable():
    """
    When no public evidence is available (e.g. ancient date 1970-01-01),
    the pipeline reports data unavailable rather than fabricating events.
    """
    with patch("engine.fna_pipeline.get_all_exchange_announcements", return_value=[]), \
         patch("engine.fna_pipeline.collect_market_news", return_value=[]):

        top_news, report_text = run_fna_pipeline(max_items=10, debug=False, target_date="1970-01-01")
        assert len(top_news) == 0
        assert "No verified corporate disclosures available" in report_text

