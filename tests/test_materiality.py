"""
Tests for Financial Context & Relative Materiality.
Verifies monetary value extraction and scaling calculations against annual revenue.
"""

import pytest
from engine.financial_context import extract_monetary_value_cr, evaluate_relative_materiality


def test_extract_monetary_values():
    assert extract_monetary_value_cr("RVNL bags Rs 903 crore order from railways") == 903.0
    assert extract_monetary_value_cr("Company secures contract worth Rs. 26,000 cr from MoD") == 26000.0
    assert extract_monetary_value_cr("Contract valued at ₹1,500 crore") == 1500.0
    assert extract_monetary_value_cr("Secures $50 million export deal") == round(50.0 * 8.35, 1)
    assert extract_monetary_value_cr("Company announces management transition") is None


def test_relative_materiality_undisclosed():
    res = evaluate_relative_materiality("TCS.NS", "TCS partners with global bank for cloud transformation")
    assert res["disclosed_value_cr"] is None
    assert "Financial magnitude cannot be reliably quantified" in res["financial_implication_text"]


def test_relative_materiality_disclosed():
    # If order value is disclosed
    res = evaluate_relative_materiality("RVNL.NS", "RVNL wins Rs 903 crore railway project")
    assert res["disclosed_value_cr"] == 903.0
    assert "903" in res["financial_implication_text"]
