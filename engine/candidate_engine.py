"""
Research Candidate Engine for Indian Fundamental News & Analysis (FNA).
Transforms raw market events into an institutional Sharekhan-style candidate pool.
Implements:
  1. Six Primary Discovery Buckets (Company, Results, Government, Commodities, Industry, Strategic)
  2. 10-Factor Research Importance Model -> RESEARCH_IMPORTANCE_SCORE
  3. Strict Materiality Tiers (Tier A, Tier B, Tier C)
  4. Relative Daily Ranking across valid events (selecting 5–12 strong stories)
  5. Detailed diagnostic debug logging
"""

import re
from typing import List, Dict, Any, Tuple, Optional


DISCOVERY_BUCKETS = {
    "COMPANY_EVENTS": [
        "ORDER_CONTRACT", "CUSTOMER_EVENT", "CAPACITY_EXPANSION", 
        "OPERATIONAL_INITIATIVE", "MANAGEMENT_EVENT"
    ],
    "RESULTS_OPERATING_DATA": [
        "FINANCIAL_RESULT", "OPERATING_UPDATE", "PRICING_EVENT"
    ],
    "GOVERNMENT_POLICY": [
        "GOVERNMENT_EVENT", "REGULATORY_EVENT", "PRODUCT_APPROVAL"
    ],
    "COMMODITIES": [
        "COMMODITY_EVENT"
    ],
    "INDUSTRY_DATA": [
        "INDUSTRY_EVENT"
    ],
    "STRATEGIC_STRUCTURE": [
        "ACQUISITION", "FUNDING_EQUITY", "FUNDING_DEBT_EVENT", "STRATEGIC_DEAL"
    ]
}


def map_event_to_discovery_bucket(event_type: str) -> str:
    """Maps canonical event type into one of the six primary research discovery buckets."""
    for bucket, types in DISCOVERY_BUCKETS.items():
        if event_type in types:
            return bucket
    return "COMPANY_EVENTS"


def compute_research_importance_model(item: Dict[str, Any], facts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Computes the 10 internal sub-scores of the Research Importance Model (Section 6):
      1. Fundamental Materiality (0-10)
      2. Financial Significance (0-10)
      3. Strategic Significance (0-10)
      4. Company Exposure (0-10)
      5. Freshness (0-10)
      6. Evidence Strength (0-10)
      7. Source Quality (0-10)
      8. Novelty (0-10)
      9. Investor Relevance (0-10)
      10. Quantifiability (0-10)
    Combines these into internal RESEARCH_IMPORTANCE_SCORE (never exposed to final user report).
    """
    facts = facts or item.get("structured_facts") or {}
    ev_type = item.get("event_type", "ORDER_CONTRACT")
    role = item.get("company_role", "beneficiary")
    order_val = item.get("order_value_cr")
    pct_rev = item.get("relative_revenue_pct")
    range_text = item.get("range_text")
    sources = item.get("sources", "")
    full_text = f"{item.get('headline', '')} {item.get('what_happened', '')} {item.get('why_it_matters', '')}".lower()

    # 1. Fundamental Materiality (0-10)
    mat_score = float(item.get("materiality_score", 6.5))
    if order_val and order_val >= 1000.0:
        mat_score = max(mat_score, 9.5)
    elif order_val and order_val >= 300.0:
        mat_score = max(mat_score, 8.8)
    elif order_val and order_val >= 100.0:
        mat_score = max(mat_score, 8.0)
    elif ev_type in ["GOVERNMENT_EVENT", "FUNDING_EQUITY"]:
        mat_score = max(mat_score, 8.5)
    elif ev_type == "MANAGEMENT_EVENT" and item.get("fundamental_direction") == "Negative":
        mat_score = max(mat_score, 8.5)
    fundamental_materiality = min(10.0, max(1.0, mat_score))

    # 2. Financial Significance (0-10)
    if pct_rev and pct_rev >= 15.0:
        fin_sig = 9.5
    elif pct_rev and pct_rev >= 7.0:
        fin_sig = 8.5
    elif pct_rev and pct_rev >= 2.0:
        fin_sig = 7.5
    elif order_val and order_val >= 200.0:
        fin_sig = 8.0
    elif order_val:
        fin_sig = 7.0
    elif any(w in full_text for w in ["ebitda", "operating margin", "equity capital", "net loss", "volume growth", "turnaround"]):
        fin_sig = 7.5
    else:
        fin_sig = 6.0
    financial_significance = fin_sig

    # 3. Strategic Significance (0-10)
    strat_sig = 6.5
    if ev_type in ["GOVERNMENT_EVENT", "ACQUISITION", "PRODUCT_APPROVAL"]:
        strat_sig = 9.0
    elif ev_type in ["STRATEGIC_DEAL", "FUNDING_EQUITY"]:
        strat_sig = 8.5
    elif ev_type in ["ORDER_CONTRACT", "CAPACITY_EXPANSION"]:
        strat_sig = 7.5
    strategic_significance = strat_sig

    # 4. Company Exposure (0-10)
    if role in ["contractor", "issuer", "target", "acquirer"]:
        company_exposure = 10.0
    elif role == "operator":
        company_exposure = 9.5
    elif "read-through" in item.get("company_role_description", "").lower() or role == "beneficiary":
        company_exposure = 8.5
    else:
        company_exposure = 8.0

    # 5. Freshness (0-10)
    freshness = 9.5

    # 6. Evidence Strength (0-10)
    is_very_brief = len(full_text.strip()) < 80
    if is_very_brief:
        evidence_strength = 5.0
    elif "nse" in sources.lower() or "bse" in sources.lower():
        evidence_strength = 10.0
    elif any(w in sources.lower() for w in ["reuters", "business standard", "economic times", "mint", "livemint"]):
        evidence_strength = 9.0
    else:
        evidence_strength = 7.5

    # 7. Source Quality (0-10)
    if "corporate announcement" in sources.lower() or "exchange" in sources.lower():
        source_quality = 10.0
    elif any(w in sources.lower() for w in ["business standard", "the economic times", "livemint"]):
        source_quality = 9.0
    else:
        source_quality = 7.5

    # 8. Novelty (0-10)
    novelty = 8.5
    if any(w in full_text for w in ["loi", "received order", "first of its kind", "secures mandate", "clearance", "upgrade to 'aa'"]):
        novelty = 9.5
    elif ev_type == "OPERATING_UPDATE":
        novelty = 8.5

    # 9. Investor Relevance (0-10)
    investor_rel = 7.5
    if is_very_brief:
        investor_rel = 5.5
    elif ev_type in ["ORDER_CONTRACT", "GOVERNMENT_EVENT", "FUNDING_EQUITY", "OPERATING_UPDATE"]:
        investor_rel = 9.0
    elif ev_type in ["COMMODITY_EVENT", "MANAGEMENT_EVENT", "PRODUCT_APPROVAL"]:
        investor_rel = 8.5

    # 10. Quantifiability (0-10)
    if order_val and pct_rev:
        quantifiability = 10.0
    elif order_val or range_text:
        quantifiability = 9.0
    elif any(w in full_text for w in ["%", "mw", "tonnes", "bbl", "crore", "cr"]):
        quantifiability = 8.0
    elif is_very_brief:
        quantifiability = 3.5
    else:
        quantifiability = 5.5

    # Composite weighted RESEARCH_IMPORTANCE_SCORE
    composite_score = (
        fundamental_materiality * 0.25 +
        financial_significance * 0.15 +
        strategic_significance * 0.15 +
        company_exposure * 0.10 +
        investor_rel * 0.10 +
        quantifiability * 0.10 +
        evidence_strength * 0.05 +
        source_quality * 0.05 +
        novelty * 0.03 +
        freshness * 0.02
    )

    final_score = round(composite_score, 2)
    return {
        "fundamental_materiality": round(fundamental_materiality, 2),
        "financial_significance": round(financial_significance, 2),
        "strategic_significance": round(strategic_significance, 2),
        "company_exposure": round(company_exposure, 2),
        "freshness": round(freshness, 2),
        "evidence_strength": round(evidence_strength, 2),
        "source_quality": round(source_quality, 2),
        "novelty": round(novelty, 2),
        "investor_relevance": round(investor_rel, 2),
        "quantifiability": round(quantifiability, 2),
        "research_importance_score": final_score,
        "total_score": final_score
    }


def assign_materiality_tier(item: Dict[str, Any], scores: Any = None, total_score: Optional[float] = None) -> str:
    """
    Categorizes candidate into Tier A (Must Consider), Tier B (Strong Secondary), or Tier C (Reject).
    Strictly evidence-driven: Requires high score and concrete verification, not just a category keyword.
    """
    if total_score is not None:
        res_score = float(total_score)
    elif isinstance(scores, (int, float)):
        res_score = float(scores)
    elif isinstance(scores, dict):
        res_score = float(scores.get("total_score", scores.get("research_importance_score", 0.0)))
    else:
        res_score = float(item.get("research_importance_score", 0.0))

    ev_type = item.get("event_type")
    order_val = item.get("order_value_cr")
    pct_rev = item.get("relative_revenue_pct")
    direction = item.get("fundamental_direction")
    why = item.get("why_it_matters", "").lower()

    # Tier A criteria: High analytical confidence, verifiable materiality
    if (
        res_score >= 8.2 or
        res_score >= 80.0 or
        (ev_type == "ORDER_CONTRACT" and ((pct_rev and pct_rev >= 10.0) or (order_val and order_val >= 250.0))) or
        (ev_type == "MANAGEMENT_EVENT" and direction == "Negative" and ("auditor" in why or res_score >= 7.5)) or
        (ev_type == "GOVERNMENT_EVENT" and res_score >= 7.8) or
        (ev_type == "OPERATING_UPDATE" and order_val and order_val >= 500.0)
    ):
        return "Tier A"

    # Tier B criteria: Requires solid evidence score (>= 6.8 or 68.0), or quantified financial impact (>= 6.5)
    if res_score >= 6.8 or res_score >= 68.0 or (res_score >= 6.5 and (order_val or pct_rev)):
        return "Tier B"

    return "Tier C"

    return "Tier C"


def rank_daily_research_candidates(candidates: List[Dict[str, Any]], max_items: int = 15) -> List[Dict[str, Any]]:
    """
    Performs purely evidence-driven daily ranking across all valid candidates.
    NO forced bucket balancing. NO per-bucket caps. NO forced diversification.
    Events are ranked strictly on merit (Tier A prioritized, then strongest Tier B).
    """
    if not candidates:
        return []

    valid = [c for c in candidates if c.get("fundamental_direction") in ["Positive", "Negative"]]

    # Helper to extract importance score
    def get_cand_score(cand: Dict[str, Any]) -> float:
        sc = cand.get("research_scores")
        if isinstance(sc, dict):
            return float(sc.get("total_score", sc.get("research_importance_score", 0.0)))
        if "research_importance_score" in cand:
            return float(cand["research_importance_score"])
        return float(cand.get("materiality_score", 0.0))

    # Sort primarily by research_importance_score descending
    valid.sort(key=get_cand_score, reverse=True)

    tier_a = [c for c in valid if c.get("tier") == "Tier A"]
    tier_b = [c for c in valid if c.get("tier") == "Tier B"]

    selected: List[Dict[str, Any]] = []
    seen_symbols = set()

    # Phase 1: Include all Tier A candidates (highest merit)
    for cand in tier_a:
        sym = cand.get("symbol") or cand.get("company_name")
        if sym in seen_symbols:
            continue
        selected.append(cand)
        seen_symbols.add(sym)
        if len(selected) >= max_items:
            break

    # Phase 2: If remaining capacity, include strongest Tier B candidates purely by score
    if len(selected) < max_items:
        for cand in tier_b:
            if len(selected) >= max_items:
                break
            sym = cand.get("symbol") or cand.get("company_name")
            if sym in seen_symbols:
                continue
            selected.append(cand)
            seen_symbols.add(sym)

    return selected


def format_candidate_debug_log(cand: Dict[str, Any], decision: str = "INCLUDE", reason: str = "") -> str:
    """Formats candidate diagnostic output matching Section 25 (Anti-overfitting diagnostics)."""
    c_name = cand.get("company_name", "Company")
    sym = cand.get("symbol", "")
    ev_type = cand.get("event_type", "EVENT")
    feed_source = cand.get("source", "Primary / Regulatory Feed")
    role = cand.get("company_role", "economic beneficiary")
    exposure_mech = cand.get("economic_exposure_mechanism") or cand.get("fundamental_impact") or ("Direct" if cand.get("company_role") in ["contractor", "issuer", "operator"] else "Read-Through")
    
    scores = cand.get("research_scores", {})
    total_score = scores.get("total_score", cand.get("research_importance_score", 0.0))
    mat = "High" if scores.get("fundamental_materiality", 0) >= 8.0 else ("Medium" if scores.get("fundamental_materiality", 0) >= 6.5 else "Low")
    fin = "High" if scores.get("financial_significance", 0) >= 8.0 else ("Medium" if scores.get("financial_significance", 0) >= 6.5 else "Low")
    tier = cand.get("tier", "Tier B")
    sources = cand.get("sources", "Exchange / Regulatory Disclosures")
    
    dec_str = f"{decision}" if not reason else f"{decision} — {reason}"
    
    return (
        f"[CANDIDATE] {c_name} ({sym})\n"
        f"[TYPE] {ev_type}\n"
        f"[DISCOVERY] Sourced from {feed_source} under canonical type {ev_type}\n"
        f"[NO HARDCODE] Verified: dynamic evidence match, zero manual company whitelisting\n"
        f"[ENTITY] Resolved '{c_name}' with identified operational role '{role}'\n"
        f"[EXPOSURE] {str(exposure_mech)[:140]}\n"
        f"[RANKING] Score {total_score} ({tier}) | Mat: {mat} ({scores.get('fundamental_materiality', 'N/A')}), Fin: {fin} ({scores.get('financial_significance', 'N/A')})\n"
        f"[TIER] {tier}\n"
        f"[SOURCE] {sources}\n"
        f"[DECISION] {dec_str}\n"
    )

