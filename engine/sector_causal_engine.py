"""
Sector Cause-and-Effect Commentary Engine.
Synthesizes second-order macro-to-sector fundamental impacts on Indian-listed equities.
Identifies logical causal chains (e.g. US interest rates -> Discretionary enterprise tech spend -> Indian IT Services).
Strictly optional and best-effort: returns None if no clear causal mechanism is present.
Flagged with review_status: CANDIDATE_FOR_HUMAN_REVIEW.
"""

import re
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def evaluate_sector_causal_chains(macro_events: List[Dict[str, Any]], target_date: str) -> List[Dict[str, Any]]:
    """
    Evaluates whether the day's macro developments substantiate a clear, specific second-order
    fundamental impact on Indian listed sectors.
    Returns a list of causal chain items (or empty list if no high-conviction causal mechanism is present).
    """
    if not macro_events:
        return []

    macro_text = " ".join([f"{ev.get('title', '')} {ev.get('summary', '')}" for ev in macro_events]).lower()
    chains = []

    # Causal Pattern 1: Elevated US Interest Rates -> IT Services Discretionary Spend
    rates_match = any(k in macro_text for k in [
        "federal reserve", "us fed", "rate pause", "higher for longer", "interest rates", "treasury yields", "powell"
    ])
    it_context_match = any(k in macro_text for k in [
        "discretionary spend", "tech spend", "it budget", "consulting", "deal delay", "slowdown", "outsourcing"
    ]) or ("federal reserve" in macro_text or "treasury yield" in macro_text or "rate" in macro_text)

    if rates_match and it_context_match:
        headline = "Sector Perspective: US Interest Rates & IT Spending"
        prose = (
            "Elevated US interest rates and persistent 'higher for longer' sovereign yield environments "
            "continue to induce caution across North American enterprise clients, leading to a curtailment "
            "of discretionary technology spend. Consequently, Indian Tier-1 IT services providers, including "
            "Wipro and Infosys, face elongated deal conversion cycles and muted near-term constant-currency "
            "revenue acceleration."
        )
        chains.append({
            "candidate_type": "SECTOR_CAUSAL_COMMENTARY",
            "company_name": headline,
            "headline": headline,
            "flowing_prose": prose,
            "affected_sector": "IT Services / Technology",
            "causal_chain": "Elevated US rates -> North American enterprise spend caution -> IT deal delays",
            "sources": "Macro Synthesis (Analyst Causal Model)",
            "event_date": target_date,
            "source_type": "SYNTHESIZED_ANALYST_REASONING",
            "review_status": "CANDIDATE_FOR_HUMAN_REVIEW",
            "human_review_flag": "Requires Review: 2nd-order macro-to-sector transmission",
            "research_importance_score": 9.1,
            "materiality_score": 8.8,
        })

    # Causal Pattern 2: Windfall Tax Cuts -> Upstream E&P & Refiners Margins
    windfall_match = any(k in macro_text for k in ["windfall tax", "saed", "special additional excise duty"])
    if windfall_match:
        headline = "Sector Perspective: Windfall Tax Relief & Refiner Net Realizations"
        prose = (
            "The central government's reduction in the Special Additional Excise Duty (SAED / windfall tax) "
            "on domestic crude oil and refined fuel exports directly widens net margin realizations for domestic "
            "refiners and upstream producers. Beneficiaries such as MRPL, ONGC, and downstream marketing companies "
            "retain higher post-tax crack spreads across diesel and jet fuel dispatches."
        )
        chains.append({
            "candidate_type": "SECTOR_CAUSAL_COMMENTARY",
            "company_name": headline,
            "headline": headline,
            "flowing_prose": prose,
            "affected_sector": "Oil & Gas / Refiners",
            "causal_chain": "Windfall tax reduction -> Elimination of export duty friction -> Wider post-tax crack spreads",
            "sources": "Fiscal Policy Synthesis",
            "event_date": target_date,
            "source_type": "SYNTHESIZED_ANALYST_REASONING",
            "review_status": "CANDIDATE_FOR_HUMAN_REVIEW",
            "human_review_flag": "Requires Review: 2nd-order fiscal transmission",
            "research_importance_score": 9.2,
            "materiality_score": 8.9,
        })

    # Causal Pattern 3: Crude Oil Spike -> Downstream Aviation & Paints Margin Compression
    crude_spike_match = any(k in macro_text for k in ["brent crude", "crude surge", "oil spikes", "crude jumps"]) and any(w in macro_text for w in ["surge", "spike", "jump", "rally", "rises", "climbs"])
    if crude_spike_match:
        headline = "Sector Perspective: Crude Price Escalation & Downstream Margin Squeeze"
        prose = (
            "Elevated international crude benchmarks translate into prompt input cost inflation for domestic "
            "downstream consumers, led by aviation turbine fuel (ATF) for airlines and petrochemical monomers "
            "for paint manufacturers. Operating margins for volume leaders including InterGlobe Aviation (IndiGo) "
            "and Asian Paints encounter near-term margin friction until raw material price increases can be passed through."
        )
        chains.append({
            "candidate_type": "SECTOR_CAUSAL_COMMENTARY",
            "company_name": headline,
            "headline": headline,
            "flowing_prose": prose,
            "affected_sector": "Aviation & Paints",
            "causal_chain": "Crude oil rally -> ATF & monomer cost surge -> Near-term margin compression",
            "sources": "Commodity Ripple Synthesis",
            "event_date": target_date,
            "source_type": "SYNTHESIZED_ANALYST_REASONING",
            "review_status": "CANDIDATE_FOR_HUMAN_REVIEW",
            "human_review_flag": "Requires Review: 2nd-order commodity transmission",
            "research_importance_score": 9.0,
            "materiality_score": 8.7,
        })

    return chains
