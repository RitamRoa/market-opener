import pytest
import sqlite3
from engine.db import (
    save_surfaced_events,
    get_surfaced_events_in_window,
    is_stale_recurrent_event,
    generate_event_fingerprint,
    get_connection
)

def test_cross_day_dedup_detects_repeat():
    # Setup test item
    item_day1 = {
        "company_name": "Solar Industries India Ltd",
        "symbol": "SOLARINDS.NS",
        "event_type": "ACQUISITION",
        "headline": "Solar Industries acquisition of Omnia causes sharp selloff",
        "what_happened": "Solar Industries completed the acquisition of Omnia Group for strategic expansion in explosives.",
        "order_value_cr": 0.0,
        "fundamental_direction": "Negative"
    }

    # Save for day 1
    save_surfaced_events([item_day1], "2026-09-16")

    # On day 2, query window of 2 days
    prior = get_surfaced_events_in_window("2026-09-17", lookback_days=2)
    assert len(prior) >= 1

    # Candidate with same story on day 2
    item_day2_repeat = {
        "company_name": "Solar Industries",
        "symbol": "SOLARINDS.NS",
        "event_type": "ACQUISITION",
        "headline": "Solar Industries shares slide on Omnia acquisition concerns",
        "what_happened": "Solar Industries completed the acquisition of Omnia Group.",
        "order_value_cr": 0.0,
        "fundamental_direction": "Negative"
    }

    is_stale, reason = is_stale_recurrent_event(item_day2_repeat, prior)
    assert is_stale is True
    assert "2026-09-16" in reason

    # Candidate with a NEW material development on day 2 (e.g. big order win instead of old acquisition)
    item_day2_new = {
        "company_name": "Solar Industries",
        "symbol": "SOLARINDS.NS",
        "event_type": "ORDER_CONTRACT",
        "headline": "Solar Industries secures fresh Rs 1,450 Cr defence contract from Ministry of Defence",
        "what_happened": "Solar Industries announced receipt of Rs 1,450 Cr order for high-energy explosives.",
        "order_value_cr": 1450.0,
        "fundamental_direction": "Positive"
    }

    is_stale_new, reason_new = is_stale_recurrent_event(item_day2_new, prior)
    assert is_stale_new is False
