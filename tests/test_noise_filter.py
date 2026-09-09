"""
Tests for Noise Filter & Quality Gating.
Ensures routine compliance filings, record dates, and duplicate shares are discarded,
while material order wins, FDA approvals, and capex announcements are preserved.
"""

import pytest
from engine.noise_filter import is_material_fundamental_event


def test_routine_filings_rejected():
    routine_cases = [
        ("Closure of Trading Window under SEBI (PIT) Regulations, 2015", "Trading window will remain closed from end of quarter."),
        ("Intimation under Regulation 39(3) regarding Loss of Share Certificate", "Company has received request for issue of duplicate share certificate."),
        ("Compliance Certificate under Regulation 74(5) of SEBI (DP) Regulations", "For the quarter ended June 30, 2026."),
        ("Board Meeting Intimation to consider unaudited financial results", "A meeting of the Board of Directors will be held on Thursday."),
        ("Voting Results of Postal Ballot along with Scrutinizer Report", "Postal ballot results declared."),
        ("Top 5 multibagger stocks to buy today for 30% gain", "Expert trading ideas for short term investors.")
    ]

    for title, summary in routine_cases:
        is_mat, reason = is_material_fundamental_event(title, summary)
        assert is_mat is False, f"Failed to filter routine filing: '{title}'. Reason given: {reason}"


def test_material_catalysts_accepted():
    material_cases = [
        ("RVNL bags Rs 903 crore order from South Central Railway", "Order for track doubling and electrification project over 30 months."),
        ("Dr. Reddy's receives US FDA final approval for oncology drug", "Commercial launch planned for Q3."),
        ("Tata Power commissions 300 MW solar plant in Gujarat", "Commercial operations begun under long-term PPA."),
        ("Cipla gets 4 Form 483 observations from US FDA for Goa facility", "Inspection concluded with 4 procedural observations."),
        ("Larsen & Toubro secures ultra-mega contract worth over Rs 15,000 crore", "Hydrocarbon business awarded major Middle East EPC contract.")
    ]

    for title, summary in material_cases:
        is_mat, reason = is_material_fundamental_event(title, summary)
        assert is_mat is True, f"Failed to accept material development: '{title}'. Reason given: {reason}"
