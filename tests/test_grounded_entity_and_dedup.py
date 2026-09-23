"""
Test Suite for Grounded Entity Resolution, Authoritative Event Deduplication, and Clean Ranked Output.
Verifies:
  1. Entity resolution grounded against official NSE/BSE listed master lists (exact/near-exact only, zero fuzzy, discards unlisted/noise).
  2. Pre-scoring authoritative deduplication clustering articles by entity + event type + key figures, picking richest article without concatenation.
  3. Final output: strictly ranked list ordered by descending materiality score:
     `1. TICKER — Positive/Negative — one-line reason with the key number`
     Dynamic cap, zero confidence tags, zero macro/causal commentary in stock list.
"""

import pytest
import re
from engine.equity_master import resolve_entity, normalize_corporate_name
from engine.deduplicator import deduplicate_and_cluster_news, extract_clustering_features, is_same_canonical_event
from engine.fna_pipeline import format_top_news_report, build_one_line_reason
from engine.candidate_engine import rank_daily_research_candidates


class TestGroundedEntityResolution:
    """Task 1: Ground entity resolution against real listed-company master list."""

    def test_official_nse_listed_companies_resolve_accurately(self):
        """Official listed companies resolve to canonical symbol and official name."""
        cases = [
            ("Tata Motors Ltd", "TATAMOTORS", "Tata Motors Limited"),
            ("Tata Consultancy Services", "TCS", "Tata Consultancy Services Limited"),
            ("Mazdock", "MAZDOCK", "Mazagon Dock Shipbuilders Limited"),
            ("Mazagon Dock Shipbuilders", "MAZDOCK", "Mazagon Dock Shipbuilders Limited"),
            ("MDL has", "MAZDOCK", "Mazagon Dock Shipbuilders Limited"),
            ("Oriana Power", "ORIANA", "Oriana Power Limited"),
            ("TrueRE Oriana Power", "ORIANA", "Oriana Power Limited"),
            ("Welspun Corp", "WELCORP", "Welspun Corp Limited"),
            ("Advait Infratech", "ADVAIT", "Advait Energy Transitions Limited"),
            ("G R Infraprojects", "GRINFRA", "G R Infraprojects Limited"),
        ]
        for query, expected_ticker, expected_name_part in cases:
            res = resolve_entity(query)
            assert res is not None, f"Failed to resolve official listed company '{query}'"
            ticker, official_name = res
            if query == "Tata Motors Ltd":
                assert ticker in ["TATAMOTORS", "TMCV", "TMPV"], f"Expected Tata Motors symbol, got {ticker}"
            else:
                assert ticker == expected_ticker, f"Expected ticker {expected_ticker}, got {ticker}"
            assert expected_name_part.lower() in official_name.lower(), f"Expected '{expected_name_part}' in '{official_name}'"

    def test_unlisted_and_invented_tickers_are_strictly_rejected(self):
        """
        Unlisted companies, media header prefixes, and temporal tokens MUST be rejected
        (return None) rather than fabricating tickers like BINANCE.NS, GENROBOTICS.NS.
        """
        disallowed = [
            "FY27",
            "Binance",
            "Binance exchange",
            "Today India Genrobotics",
            "Genrobotics",
            "Genrobotics Innovations",
            "Today",
            "Yesterday",
            "India",
            "Unknown Private Startup Ltd",
            "Global Crypto Platform",
        ]
        for item in disallowed:
            res = resolve_entity(item)
            assert res is None, f"Expected None for unlisted/noise entity '{item}', but got {res}"

    def test_zero_fuzzy_matching(self):
        """Zero fuzzy / approximate matching: heavily misspelled strings return None."""
        typos = [
            "Tata Motarrrs",
            "Bynance",
            "Kisht",
            "Mazgon Dook",
            "Relianzz",
        ]
        for typo in typos:
            res = resolve_entity(typo)
            assert res is None, f"Fuzzy match improperly matched typo '{typo}' to {res}"


class TestAuthoritativeEventDeduplication:
    """Task 2: Merge duplicate-source coverage into one canonical event before scoring/synthesis."""

    def test_oriana_bess_multiple_sources_merge_into_single_richest_article(self):
        """
        Multiple articles reporting the same 900 MW BESS contract for Oriana Power / TrueRE
        must cluster into ONE canonical event, picking the single most detailed article
        without concatenation.
        """
        articles = [
            {
                "title": "TrueRE Oriana Power wins 900 Mw18 GWh BESS contracts in India - ESS News",
                "summary": "TrueRE Oriana Power has secured contracts to build 900 MW / 1.8 GWh battery energy storage systems.",
                "symbol": "ORIANA.NS",
                "company_name": "Oriana Power Limited",
                "source": "ESS News",
                "url": "https://essnews.com/oriana-bess"
            },
            {
                "title": "TrueRE Oriana Power wins 900 Mw1800 MWh BESS projects in Maharashtra - PV magazine India",
                "summary": "TrueRE Oriana Power has been awarded 900 MW / 1800 MWh BESS projects in Maharashtra state.",
                "symbol": "ORIANA.NS",
                "company_name": "Oriana Power Limited",
                "source": "PV Magazine India",
                "url": "https://pv-magazine-india.com/oriana-bess"
            },
            {
                "title": "Oriana Power secures 900 MW battery storage orders worth Rs 3,870 crore from MSEDCL - Business Upturn",
                "summary": "Oriana Power secured major 900 MW standalone battery energy storage orders valued at Rs 3,870 crore from MSEDCL across two project sites in Maharashtra.",
                "symbol": "ORIANA.NS",
                "company_name": "Oriana Power Limited",
                "source": "Business Upturn",
                "url": "https://businessupturn.com/oriana-bess-msedcl"
            }
        ]

        clusters = deduplicate_and_cluster_news(articles)
        assert len(clusters) == 1, f"Expected exactly 1 canonical cluster, but got {len(clusters)}"
        canonical = clusters[0]

        # Verified aggregation of sources
        assert canonical["articles_count"] == 3
        assert "ESS News" in canonical["sources"]
        assert "PV Magazine India" in canonical["sources"]
        assert "Business Upturn" in canonical["sources"]

        # Richest article (with Rs 3,870 crore and MSEDCL) must be the basis of summary
        assert "3,870" in canonical["summary"] or "3,870" in canonical["title"]
        assert "msedcl" in canonical["summary"].lower()

        # Zero concatenation check: "Separately, X announced" must NOT exist
        assert "separately" not in canonical["summary"].lower()
        assert "separately" not in canonical["title"].lower()

    def test_distinct_events_for_different_companies_remain_separate(self):
        """Distinct events for different companies must not be merged."""
        articles = [
            {
                "title": "Mazagon Dock signs ₹27,000 Cr MoU with MoD",
                "summary": "Mazagon Dock Shipbuilders signed a mega MoU worth ₹27,000 Cr for next-gen vessels.",
                "symbol": "MAZDOCK.NS",
                "company_name": "Mazagon Dock Shipbuilders Limited",
                "source": "Exchange Filing"
            },
            {
                "title": "Welspun Corp associate East Pipes wins ₹3,670 Cr order",
                "summary": "East Pipes secured contracts worth ₹3,670 Cr from Saudi Aramco.",
                "symbol": "WELCORP.NS",
                "company_name": "Welspun Corp Limited",
                "source": "Press Release"
            }
        ]
        clusters = deduplicate_and_cluster_news(articles)
        assert len(clusters) == 2


class TestRankedListOutput:
    """Task 3: Final output is strictly a ranked list ordered by descending materiality score."""

    def test_ranked_list_format_and_omissions(self):
        """
        Output must match:
        1. TICKER — Positive/Negative — one-line reason with the key number
        2. TICKER — ...
        With zero confidence tags, zero extra fields, and macro/causal items dropped.
        """
        items = [
            # Macro Commentary (MUST BE DROPPED)
            {
                "candidate_type": "MACRO_COMMENTARY",
                "headline": "Hormuz Strait restrictions elevate Brent crude towards $105/bbl",
                "flowing_prose": "Geopolitical escalation continues to threaten crude supplies.",
                "research_importance_score": 9.9
            },
            # Sector Causal Chain (MUST BE DROPPED)
            {
                "candidate_type": "SECTOR_CAUSAL_COMMENTARY",
                "headline": "Crude inflation compresses retail fuel margins",
                "flowing_prose": "Upstream oil producers benefit while fuel retailers face margin compression.",
                "research_importance_score": 9.0
            },
            # Stock 1 (Score: 8.5)
            {
                "candidate_type": "COMPANY_EVENT",
                "symbol": "WELCORP.NS",
                "company_name": "Welspun Corp Limited",
                "headline": "Associate East Pipes bags ₹3,670 Cr order from Saudi Aramco",
                "order_value_cr": 3670.0,
                "fundamental_direction": "Positive",
                "research_importance_score": 8.5
            },
            # Stock 2 (Score: 9.8 - Higher materiality, must be ranked #1)
            {
                "candidate_type": "COMPANY_EVENT",
                "symbol": "MAZDOCK.NS",
                "company_name": "Mazagon Dock Shipbuilders Limited",
                "headline": "Secures ₹27,000 Cr MoU for next-generation offshore patrol vessels",
                "order_value_cr": 27000.0,
                "fundamental_direction": "Positive",
                "research_importance_score": 9.8
            },
            # Stock 3 (Score: 8.8)
            {
                "candidate_type": "COMPANY_EVENT",
                "symbol": "ORIANA.NS",
                "company_name": "Oriana Power Limited",
                "headline": "Secures 900 MW battery storage orders worth ₹3,870 Cr from MSEDCL",
                "order_value_cr": 3870.0,
                "fundamental_direction": "Positive",
                "research_importance_score": 8.8
            }
        ]

        report = format_top_news_report("23 September 2026", items)
        lines = [line.strip() for line in report.strip().split("\n") if line.strip()]

        # Exactly 3 stock lines, macro and sector causal chains completely dropped
        assert len(lines) == 3, f"Expected 3 lines, got {len(lines)}:\n{report}"

        # Ranked #1 must be MAZDOCK (score 9.8)
        assert lines[0].startswith("1. MAZDOCK — Positive —")
        assert "₹27,000" in lines[0] or "27,000" in lines[0]

        # Ranked #2 must be ORIANA (score 8.8)
        assert lines[1].startswith("2. ORIANA — Positive —")
        assert "₹3,870" in lines[1] or "3,870" in lines[1]

        # Ranked #3 must be WELCORP (score 8.5)
        assert lines[2].startswith("3. WELCORP — Positive —")
        assert "₹3,670" in lines[2] or "3,670" in lines[2]

        # Zero confidence tags, zero extra fields, zero headers
        assert "[High Confidence]" not in report
        assert "Tier A" not in report
        assert "What happened:" not in report
        assert "Why it matters:" not in report
        assert "TOP NEWS COMPLETE" not in report
        assert "Hormuz Strait" not in report
        assert "Sector Causal" not in report

    def test_dynamic_cap_retains_all_actionable_candidates(self):
        """Dynamic cap does not arbitrarily truncate valid Tier A/B candidates."""
        candidates = [
            {
                "company_name": f"Company {i}",
                "symbol": f"SYM{i}.NS",
                "event_type": "ORDER_CONTRACT",
                "fundamental_direction": "Positive",
                "order_value_cr": 500.0 + i * 100,
                "tier": "Tier A",
                "research_scores": {"total_score": 8.0 + (i * 0.1), "fundamental_materiality": 8.5, "financial_significance": 8.0}
            }
            for i in range(12)
        ]

        # When max_items is None, dynamic cap retains all 12 actionable items
        ranked = rank_daily_research_candidates(candidates, max_items=None)
        assert len(ranked) == 12, f"Dynamic cap failed: expected 12 candidates, got {len(ranked)}"
