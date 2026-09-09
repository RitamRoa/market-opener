"""
Tests for Entity Resolution & Verification Gates.
Explicitly verifies failure cases:
  1. ICICI Prudential Life is NEVER assigned to ICICI Bank.
  2. Jio Financial Services is NEVER assigned to Reliance Industries.
  3. Tata Technologies is NEVER assigned to Tata Motors or TCS.
"""

import pytest
from engine.entity_mapper import resolve_entity_from_text, validate_event_entity


def test_icici_pru_life_not_icici_bank():
    text = "ICICI Prudential Life Insurance to focus on growing absolute VNB amid slump in FY24"
    meta, reason = resolve_entity_from_text(text)
    assert meta is not None, "Failed to resolve entity"
    assert meta["symbol"] == "ICICIPRULI.NS", f"Expected ICICIPRULI.NS but got {meta['symbol']}"
    assert meta["symbol"] != "ICICIBANK.NS", "CRITICAL ERROR: ICICI Prudential Life was misassigned to ICICI Bank!"


def test_jio_fin_not_reliance():
    text = "Jio Financial Services enters mutual fund business in partnership with BlackRock"
    meta, reason = resolve_entity_from_text(text)
    assert meta is not None, "Failed to resolve entity"
    assert meta["symbol"] == "JIOFIN.NS", f"Expected JIOFIN.NS but got {meta['symbol']}"
    assert meta["symbol"] != "RELIANCE.NS", "CRITICAL ERROR: Jio Financial Services was misassigned to Reliance Industries!"


def test_reliance_industries_direct():
    text = "Reliance Industries approves new green energy giga-complex capex in Jamnagar"
    meta, reason = resolve_entity_from_text(text)
    assert meta is not None
    assert meta["symbol"] == "RELIANCE.NS"


def test_tata_technologies_not_tcs_or_motors():
    text = "Tata Technologies secures new automotive software engineering deal"
    meta, reason = resolve_entity_from_text(text)
    assert meta is not None
    assert meta["symbol"] == "TATATECH.NS"
    assert meta["symbol"] != "TATAMOTORS.NS"
    assert meta["symbol"] != "TCS.NS"


def test_entity_validation_gate_rejection():
    # If text is about Jio Financial Services but assigned symbol is RELIANCE.NS, must be rejected
    is_valid, reason = validate_event_entity(
        event_title="Jio Financial Services shares surge 5% on regulatory license",
        event_summary="Jio Financial receives payment aggregator nod from RBI",
        assigned_symbol="RELIANCE.NS"
    )
    assert is_valid is False, "Validation gate should have rejected Reliance Industries for Jio Financial news"
    assert "Entity mismatch" in reason or "exclusion" in reason


def test_icici_bank_direct():
    text = "ICICI Bank reports net profit of Rs 10,260 crore, advances up 16%"
    meta, reason = resolve_entity_from_text(text)
    assert meta is not None
    assert meta["symbol"] == "ICICIBANK.NS"
