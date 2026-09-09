"""
Tests to Prevent Boilerplate Template Leakage.
Ensures synthesized items contain ZERO forbidden template expressions.
"""

import pytest
from engine.fna_analyzer import synthesize_fna_item, FORBIDDEN_PHRASES


def test_no_forbidden_templates_in_order_win():
    event = {
        "company_name": "Rail Vikas Nigam Ltd",
        "symbol": "RVNL.NS",
        "title": "RVNL bags Rs 903 crore EPC contract from South Central Railway",
        "summary": "Project entails track doubling and electrification over 30 months.",
        "sources": ["NSE Announcement"]
    }
    item = synthesize_fna_item(event)

    full_output = f"{item['why_it_matters']} {item['fundamental_impact']}"
    for forbidden in FORBIDDEN_PHRASES:
        assert forbidden.lower() not in full_output.lower(), f"Forbidden template expression '{forbidden}' leaked into output!"


def test_no_forbidden_templates_in_regulatory_action():
    event = {
        "company_name": "Cipla Ltd",
        "symbol": "CIPLA.NS",
        "title": "US FDA issues 4 Form 483 observations for Goa manufacturing unit",
        "summary": "Observations relate to standard operating procedures and documentation.",
        "sources": ["Exchange Filing", "Reuters"]
    }
    item = synthesize_fna_item(event)

    full_output = f"{item['why_it_matters']} {item['fundamental_impact']}"
    for forbidden in FORBIDDEN_PHRASES:
        assert forbidden.lower() not in full_output.lower(), f"Forbidden template expression '{forbidden}' leaked into output!"
