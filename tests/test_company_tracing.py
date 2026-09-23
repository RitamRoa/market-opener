import pytest
import io
import sys
from engine.fna_pipeline import run_company_trace

def test_company_tracing_output():
    # Construct mock pipeline stages
    all_raw = [
        {"title": "Mazagon Dock inks Rs 27,000 Cr MoU with European shipbuilder", "summary": "Defence PSU signed massive agreement", "source": "Reuters", "published_at": "2026-09-17T09:00:00+05:30"}
    ]
    material = [
        {"title": "Mazagon Dock inks Rs 27,000 Cr MoU with European shipbuilder", "summary": "Defence PSU signed massive agreement", "source": "Reuters", "published_at": "2026-09-17T09:00:00+05:30"}
    ]
    resolved = [
        {"company_name": "Mazagon Dock Shipbuilders Ltd", "symbol": "MAZDOCK.NS", "sector": "Defence", "title": "Mazagon Dock inks Rs 27,000 Cr MoU", "summary": "Defence agreement"}
    ]
    clusters = [
        {"company_name": "Mazagon Dock Shipbuilders Ltd", "symbol": "MAZDOCK.NS", "title": "Mazagon Dock inks Rs 27,000 Cr MoU", "sources": ["Reuters"]}
    ]
    evaluated = [
        {
            "company_name": "Mazagon Dock Shipbuilders Ltd",
            "symbol": "MAZDOCK.NS",
            "event_type": "STRATEGIC_DEAL",
            "headline": "Mazagon Dock inks Rs 27,000 Cr MoU with European shipbuilder",
            "what_happened": "Company signed Rs 27,000 Cr MoU",
            "order_value_cr": 27000.0,
            "research_importance_score": 9.8,
            "tier": "Tier A",
            "actionable_reason": "Tier A high-conviction fundamental development (Score: 9.8).",
            "fundamental_direction": "Positive"
        }
    ]
    actionable = evaluated
    top_news = evaluated

    captured_out = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = captured_out
        run_company_trace(
            "Mazagaon Dock",
            all_raw,
            material,
            resolved,
            clusters,
            evaluated,
            actionable,
            top_news
        )
    finally:
        sys.stdout = old_stdout

    trace_log = captured_out.getvalue()
    assert "COMPANY TRACE REPORT: 'Mazagaon Dock'" in trace_log
    assert "[STAGE 1: INGESTION] Found 1 matching raw items." in trace_log
    assert "[STAGE 2: NOISE FILTER] 1 / 1 survived noise filter." in trace_log
    assert "[STAGE 3: ENTITY RESOLUTION] 1 items resolved." in trace_log
    assert "[STAGE 4: CLUSTERING] Present in 1 canonical clusters." in trace_log
    assert "[STAGE 5: EVALUATION & ACTIONABILITY] 1 candidates evaluated." in trace_log
    assert "[STAGE 6: FINAL TOP NEWS SELECTION] 1 included in final TOP NEWS." in trace_log
    assert "SELECTED: Mazagon Dock Shipbuilders Ltd (MAZDOCK.NS) — Direction: Positive" in trace_log
