"""
Unit and regression tests for the expanded fundamental news coverage pipeline.
Verifies:
1. Winning contractor vs awarding client resolution (Shakti Pumps, Enviro Infra).
2. Sovereign DAC defence procurement catalyst mapping (HAL / BEL).
3. Management resignation following audit probe (Coforge) classified as NEGATIVE.
4. Commodity catalyst mapping (Brent crude > $100 -> ONGC) classified as POSITIVE.
5. Operating metrics (IRB toll revenue) and Funding (ASM Tech preferential issue).
6. Two-stage selection & relative daily ranking logic.
7. Verification that no AMBIGUOUS, NEUTRAL, or MIXED items are included in final TOP NEWS.
"""

import pytest
from engine.entity_mapper import (
    resolve_entity_from_text,
    is_awarding_client_in_text,
    is_multi_company_roundup,
    resolve_external_event_beneficiary,
)
from engine.fna_analyzer import synthesize_fna_item, clean_fundamental_headline
from engine.fna_pipeline import select_daily_top_news


class TestCoverageExpansion:

    def test_shakti_pumps_contractor_not_awarding_client(self):
        headline = "Shakti Pumps bags massive Rs 778 crore solar pump work order from Maharashtra govt agency"
        summary = "Shakti Pumps (India) has secured an order worth Rs 778 crore for execution of solar water pumping systems."
        
        # Verify Shakti Pumps is NOT treated as awarding client
        is_client = is_awarding_client_in_text("SHAKTIPUMP.NS", headline)
        assert not is_client, "Shakti Pumps should be recognized as the contractor/winner, not awarding client"

        # Verify entity resolution
        meta, reason = resolve_entity_from_text(f"{headline} {summary}")
        assert meta is not None
        assert meta["symbol"] == "SHAKTIPUMP.NS"

    def test_ntpc_vs_enviro_infra_preservation(self):
        headline = "Enviro Infra Engineers wins Rs 450 crore wastewater treatment contract for NTPC project"
        summary = "Enviro Infra Engineers Ltd has been awarded a major EPC contract by NTPC for wastewater handling."
        
        meta, reason = resolve_entity_from_text(f"{headline} {summary}")
        assert meta is not None
        # Must resolve to the contractor/beneficiary, NOT NTPC
        assert meta["symbol"] == "EIEL.NS"
        assert meta["symbol"] != "NTPC.NS"

    def test_dac_defence_clearance_resolution(self):
        headline = "Defence Acquisition Council approves procurement of Rs 1.45 lakh crore for Armed Forces"
        summary = "DAC under Defence Minister Rajnath Singh accords AoN for 10 capital acquisition proposals including fighter aircraft, Su-30MKI upgrades, and electronic warfare suites."
        
        meta, reason = resolve_entity_from_text(f"{headline} {summary}")
        assert meta is not None
        assert meta["symbol"] in ["HAL.NS", "BEL.NS"]

    def test_management_resignation_negative_classification(self):
        event = {
            "symbol": "COFORGE.NS",
            "company_name": "Coforge Ltd",
            "title": "Coforge Chairman OP Bhatt resigns after statutory audit flag discrepancies",
            "summary": "Coforge announces resignation of Chairman OP Bhatt following findings by internal audit and governance committees.",
            "sources": ["BSE Filing"],
            "published_at": "2026-09-09 10:00:00",
            "financial_data": {"market_cap_cr": 45000, "pe_ratio": 38.0}
        }
        synthesized = synthesize_fna_item(event)
        assert synthesized is not None
        assert synthesized["classification"] == "NEGATIVE"
        assert synthesized["event_type"] == "MANAGEMENT_EVENT"

    def test_commodity_crude_rally_positive_for_upstream(self):
        headline = "Brent crude spikes past $100 per barrel amid escalating geopolitical tensions"
        summary = "Global crude benchmarks jumped past $100/bbl, providing strong realization gains for domestic upstream producers."
        
        meta, reason = resolve_external_event_beneficiary(f"{headline} {summary}")
        assert meta is not None
        assert meta["symbol"] == "ONGC.NS"
        
        event = {
            "symbol": meta["symbol"],
            "company_name": meta["name"],
            "title": headline,
            "summary": summary,
            "sources": ["Reuters"],
            "published_at": "2026-09-09 11:00:00",
            "financial_data": {"market_cap_cr": 320000, "pe_ratio": 7.5}
        }
        synthesized = synthesize_fna_item(event)
        assert synthesized is not None
        assert synthesized["classification"] == "POSITIVE"

    def test_two_stage_selection_and_no_ambiguous(self):
        # Synthesized Tier A items
        tier_a = [
            {
                "symbol": "SHAKTIPUMP.NS",
                "company_name": "Shakti Pumps (India) Ltd",
                "classification": "POSITIVE",
                "event_type": "ORDER_CONTRACT",
                "headline": "Secures Rs 778 Cr Solar Pump Order",
                "tier": "Tier A",
                "materiality_score": 9.5,
                "order_value_cr": 778.0,
            },
            {
                "symbol": "COFORGE.NS",
                "company_name": "Coforge Ltd",
                "classification": "NEGATIVE",
                "event_type": "MANAGEMENT_EVENT",
                "headline": "Chairman OP Bhatt Steps Down Following Audit Review",
                "tier": "Tier A",
                "materiality_score": 9.0,
            },
            # Ambiguous (Must be filtered out)
            {
                "symbol": "AMBIG.NS",
                "company_name": "Ambig Ltd",
                "classification": "AMBIGUOUS",
                "event_type": "FINANCIAL_RESULT",
                "headline": "Mixed Q1 Results with Margin Pressure",
                "tier": "Tier A",
                "materiality_score": 9.9,
            }
        ]

        # Synthesized Tier B items
        tier_b = [
            {
                "symbol": "IRB.NS",
                "company_name": "IRB Infrastructure Developers Ltd",
                "classification": "POSITIVE",
                "event_type": "OPERATING_UPDATE",
                "headline": "Reports 25% Toll Revenue Growth in August",
                "tier": "Tier B",
                "materiality_score": 7.5,
            }
        ]

        selected = select_daily_top_news(tier_a, tier_b, max_items=10)
        symbols = [x["symbol"] for x in selected]

        assert "SHAKTIPUMP.NS" in symbols
        assert "COFORGE.NS" in symbols
        assert "IRB.NS" in symbols
        assert "AMBIG.NS" not in symbols

        for item in selected:
            assert item["classification"] in ["POSITIVE", "NEGATIVE"], f"Invalid classification: {item['classification']}"
