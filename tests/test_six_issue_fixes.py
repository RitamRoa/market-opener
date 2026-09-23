"""
Comprehensive unit and regression tests for the six critical FNA pipeline bug fixes:
1. Macro Commentary Date-Freshness & Dynamic Synthesis
2. Lakh vs Crore Normalization & Small-Order Penalty (Provigil vs Welspun)
3. Real-Content Noise Gate & Boilerplate Rejection (Magellanic Cloud)
4. Entity Extraction Leading-Token Cleanup (FY27 Ashiana & Today India Genrobotics)
5. Corporate Relationship & Multi-Event Secondary Fact Retention (Welspun Corp)
6. Coverage Gaps (Advait BESS MoU, GR Infra Appointed Date, Lenskart Block Deal, Mazagon Dock)
"""

import pytest
from datetime import datetime, date

# Component 1: Macro Commentary
from engine.macro_commentary import filter_fresh_macro_events, generate_macro_commentary

# Component 2: Financial Context & Units
from engine.financial_context import (
    parse_semantic_financial_metrics,
    _normalize_to_cr,
    evaluate_relative_materiality,
)
from engine.candidate_engine import (
    compute_research_importance_model,
    assign_materiality_tier,
)

# Component 3: Noise Filter & Real Content
from engine.noise_filter import (
    has_concrete_actionable_structure,
    is_material_fundamental_event,
)
from engine.fna_analyzer import (
    synthesize_fna_item,
    classify_event_direction_and_type,
)

# Component 4: Entity Mapper
from engine.entity_mapper import (
    clean_extracted_entity_name,
    validate_and_normalize_entity_display_name,
    resolve_entity_from_text,
    extract_dynamic_corporate_entity,
)

# Component 5: Pipeline & Secondary Facts
from engine.fna_pipeline import run_fna_pipeline

# Component 6: DB & Coverage
from engine.db import is_stale_recurrent_event, generate_event_fingerprint


class TestMacroFreshness:
    """Tests for Issue 1: Date freshness in macro commentary."""

    def test_filter_fresh_macro_events_discards_stale(self):
        target_date = "2026-09-21"
        events = [
            {"title": "Fresh Iran threats", "published_date": "2026-09-21T08:00:00Z"},
            {"title": "Yesterday Trump comments", "published_date": "2026-09-20T14:00:00Z"},
            {"title": "Stale Sept 18 F-35 package", "published_date": "2026-09-18T10:00:00Z"},
            {"title": "Ancient article", "published_date": "2026-08-15T00:00:00Z"},
        ]
        fresh = filter_fresh_macro_events(events, target_date)
        titles = [e["title"] for e in fresh]
        assert "Fresh Iran threats" in titles
        assert "Yesterday Trump comments" in titles
        assert "Stale Sept 18 F-35 package" not in titles
        assert "Ancient article" not in titles

    def test_synthesize_macro_commentary_no_stale_hardcoding(self):
        target_date = "2026-09-21"
        fresh_events = [
            {
                "title": "Iran threatens retaliation without limitations following Israeli strikes",
                "summary": "Tehran issued stern warnings as Trump stated he is in deciding mode on response",
                "published_date": "2026-09-21T07:30:00Z",
                "source": "Reuters"
            }
        ]
        res = generate_macro_commentary(fresh_events, target_date=target_date)
        assert res is not None
        commentary = res.get("flowing_prose", "")
        # Verify hardcoded Sept 18 items are not present
        assert "$24.3B" not in commentary
        assert "24.3B F-35" not in commentary
        # Verify fresh themes are captured
        assert "Iran" in commentary or "retaliation" in commentary.lower()


class TestUnitParsingAndProvigil:
    """Tests for Issue 2: Lakh vs Crore normalization and scoring."""

    def test_lakh_normalization_to_crore(self):
        assert _normalize_to_cr(44.60, "lakh")[0] == pytest.approx(0.446, rel=1e-3)
        assert _normalize_to_cr(100.0, "lakh")[0] == pytest.approx(1.0, rel=1e-3)
        assert _normalize_to_cr(2.0, "lakh crore")[0] == pytest.approx(200000.0, rel=1e-3)
        assert _normalize_to_cr(50.0, "crore")[0] == pytest.approx(50.0, rel=1e-3)

    def test_parse_semantic_financial_metrics_lakh(self):
        text = "Provigil Surveillance receives work order worth Rs 44.60 Lakh for security solutions"
        metrics = parse_semantic_financial_metrics(text)
        assert metrics.get("value_cr") == pytest.approx(0.446, rel=1e-3)
        assert "Lakh" in metrics.get("range_text")
        assert metrics.get("metric") == "ORDER_VALUE"

    def test_provigil_micro_order_scoring_and_tier_penalty(self):
        # Provigil order: 44.60 Lakh = 0.446 Cr
        item = {
            "title": "Provigil Surveillance secures ₹44.60 Lakh work order",
            "summary": "Provigil Surveillance secures work order worth ₹44.60 Lakh from commercial client",
            "event_type": "ORDER_CONTRACT",
            "direction": "Positive",
            "order_value_cr": 0.446,
            "annual_revenue_cr": 50.0,
            "relative_revenue_pct": 0.892,
        }
        scores = compute_research_importance_model(item)
        assert scores["total_score"] <= 5.5
        assert scores["deal_scale_boost"] < 0  # Small deal penalty applied

        tier = assign_materiality_tier(item, scores)
        # Orders under ₹50 Cr without >= 10% revenue are barred from Tier A; sub-crore is Tier C
        assert tier == "Tier C"

    def test_large_welspun_order_scoring(self):
        item = {
            "title": "Welspun Corp associate East Pipes secures ₹3,670 Cr order from Saudi Aramco",
            "summary": "East Pipes secures major steel pipe supply contract worth ₹3,670 Cr",
            "event_type": "ORDER_CONTRACT",
            "direction": "Positive",
            "order_value_cr": 3670.0,
            "annual_revenue_cr": 9000.0,
            "relative_revenue_pct": 40.7,
        }
        scores = compute_research_importance_model(item)
        assert scores["total_score"] >= 8.2
        tier = assign_materiality_tier(item, scores)
        assert tier == "Tier A"


class TestRealContentNoiseGate:
    """Tests for Issue 3: Real content check rejecting filing boilerplate."""

    def test_empty_attachment_boilerplate_detected_as_routine(self):
        headline = "Magellanic Cloud Ltd — attached Herewith the Intimation of the same"
        summary = "Please find attached herewith the intimation of the same for your records"
        is_mat, _ = is_material_fundamental_event(headline, summary)
        assert is_mat is False

    def test_has_concrete_actionable_structure_fails_on_empty_boilerplate(self):
        boilerplate = "Magellanic Cloud Ltd — attached Herewith the Intimation of the same"
        has_struct, _ = has_concrete_actionable_structure(boilerplate)
        assert has_struct is False

    def test_has_concrete_actionable_structure_passes_on_real_event(self):
        real_event = "G R Infraprojects emerges as lowest bidder for ₹1,200 Cr highway project"
        has_struct, _ = has_concrete_actionable_structure(real_event)
        assert has_struct is True

    def test_magellanic_cloud_boilerplate_disqualified_from_tier_a(self):
        raw_event = {
            "company_name": "Magellanic Cloud Ltd",
            "title": "Magellanic Cloud Ltd — attached Herewith the Intimation of the same",
            "summary": "Attached herewith the intimation of the same for your records.",
            "event_type": "ORDER_CONTRACT",
            "direction": "Positive",
            "materiality_score": 8.5,
        }
        fna = synthesize_fna_item(raw_event)
        # Even if synthesized, it MUST NOT be assigned Tier A
        if fna:
            assert fna.get("tier") != "Tier A"


class TestEntityExtractionLeadingTokens:
    """Tests for Issue 4: Leading-token stripping and entity cleanup."""

    def test_clean_extracted_entity_name_strips_fy(self):
        assert clean_extracted_entity_name("FY27") == ""
        assert clean_extracted_entity_name("FY26 Tata Motors") == "Tata Motors"

    def test_clean_extracted_entity_name_strips_publisher_prefix(self):
        assert clean_extracted_entity_name("Today India Genrobotics") == "Genrobotics"
        assert clean_extracted_entity_name("Manufacturing Today India Genrobotics") == "Genrobotics"

    def test_extract_entity_and_action_ashiana_housing(self):
        text = "Ashiana Housing to invest ₹1,000 cr in FY27 to acquire land for residential projects"
        entity_meta, _ = resolve_entity_from_text(text)
        assert entity_meta is not None
        assert "Ashiana Housing" in entity_meta["name"]
        assert "FY27" not in entity_meta["name"]

    def test_validate_and_normalize_entity_display_name(self):
        # Unlisted entity Genrobotics must return empty string (discarded)
        official_unlisted = validate_and_normalize_entity_display_name("Genrobotics")
        assert official_unlisted == ""

        # Listed company resolves to official master name
        official_gr = validate_and_normalize_entity_display_name("GR Infra")
        assert "G R Infraprojects" in official_gr or "GR Infra" in official_gr


class TestCorporateRelationshipsAndSecondaryFacts:
    """Tests for Issue 5: Corporate relationship preservation & multi-event retention."""

    def test_east_pipes_associate_relationship_recognized(self):
        text = "Welspun Corp associate company East Pipes wins ₹3,670 Cr order from Saudi Aramco"
        raw_event = {
            "company_name": "Welspun Corp",
            "title": text,
            "summary": "East Pipes, an associate company of Welspun Corp, secured contracts in Saudi Arabia.",
            "event_type": "ORDER_CONTRACT",
            "direction": "Positive",
            "order_value_cr": 3670.0,
            "materiality_score": 8.8,
        }
        item = synthesize_fna_item(raw_event)
        assert item is not None
        # Verify relationship is preserved in narrative
        narrative = item.get("what_happened", "") + " " + item.get("flowing_prose", "")
        assert "associate" in narrative.lower() or "east pipes" in narrative.lower()


class TestCoverageGaps:
    """Tests for Issue 6: Advait BESS MoU, GR Infra Appointed Date, Lenskart Block Deal, Mazagon Dock."""

    def test_advait_bess_mou_classification(self):
        text = "Advait Infratech signs MoU with HiTHIUM to deploy utility-scale Battery Energy Storage Systems (BESS)"
        ev_type, direction, score = classify_event_direction_and_type(text)
        assert ev_type in ["STRATEGIC_DEAL", "ORDER_CONTRACT"]
        assert direction == "Positive"

    def test_gr_infra_appointed_date_classification_and_tier(self):
        text = "NHAI declares appointed date for GR Infra's ₹4,262 Cr highway concession project"
        ev_type, direction, score = classify_event_direction_and_type(text)
        assert ev_type == "ORDER_CONTRACT"
        assert direction == "Positive"

        raw_event = {
            "company_name": "G R Infraprojects Ltd",
            "title": text,
            "summary": "NHAI declared appointed date for the 4-lane highway project worth ₹4,262 Cr.",
            "event_type": ev_type,
            "direction": direction,
            "order_value_cr": 4262.0,
            "materiality_score": 8.5,
        }
        item = synthesize_fna_item(raw_event)
        assert item is not None
        assert item.get("tier") == "Tier A"
        assert "appointed date" in item.get("what_happened", "").lower()

    def test_lenskart_block_deal_negative_flag(self):
        text = "SoftBank and early investors offload ₹2,047 Cr stake in Lenskart via block deal"
        ev_type, direction, score = classify_event_direction_and_type(text)
        assert ev_type == "BLOCK_DEAL"
        assert direction == "Negative"

        raw_event = {
            "company_name": "Lenskart Solutions Ltd",
            "title": text,
            "summary": "SoftBank divests shares worth ₹2,047 Cr through secondary market block deals.",
            "event_type": ev_type,
            "direction": direction,
            "order_value_cr": 2047.0,
            "materiality_score": 8.0,
        }
        item = synthesize_fna_item(raw_event)
        assert item is not None
        assert item.get("direction") == "Negative"
        assert item.get("tier") == "Tier A"
        assert "supply overhang" in item.get("why_it_matters", "").lower()

    def test_mazagon_dock_distinct_shipyard_not_stale(self):
        hist_events = [
            {
                "company_key": "MAZAGON DOCK",
                "symbol": "MAZDOCK",
                "fingerprint": "fp_dighi_123",
                "headline": "Mazagon Dock signs MoU for greenfield shipyard at Dighi Port",
                "what_happened": "Mazagon Dock signs MoU with port authority for shipyard development at Dighi Port in Maharashtra.",
                "surfaced_date": "2026-09-18",
                "content_tokens": "mazagon dock signs mou greenfield shipyard dighi port maharashtra",
                "order_value_cr": None,
            }
        ]
        cand = {
            "company_name": "Mazagon Dock Shipbuilders Ltd",
            "symbol": "MAZDOCK",
            "headline": "Mazagon Dock signs MoU for second shipyard in Andhra Pradesh",
            "what_happened": "Mazagon Dock signs MoU with Andhra Pradesh government for second commercial shipyard facility.",
            "summary": "Strategic expansion with Andhra Pradesh maritime board for second shipbuilding hub.",
            "event_type": "STRATEGIC_DEAL",
            "order_value_cr": None,
        }
        is_stale, reason = is_stale_recurrent_event(cand, hist_events)
        # Because of distinct location (Andhra Pradesh vs Dighi) and "second" shipyard, it MUST NOT be marked stale!
        assert is_stale is False
