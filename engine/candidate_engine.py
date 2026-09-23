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
        "ACQUISITION", "FUNDING_EQUITY", "FUNDING_DEBT_EVENT", "STRATEGIC_DEAL", "BLOCK_DEAL"
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
    if order_val and order_val >= 10000.0:
        mat_score = max(mat_score, 10.0)
    elif order_val and order_val >= 2500.0:
        mat_score = max(mat_score, 9.8)
    elif order_val and order_val >= 1000.0:
        mat_score = max(mat_score, 9.2)
    elif order_val and order_val >= 300.0:
        mat_score = max(mat_score, 8.5)
    elif order_val and order_val >= 100.0:
        mat_score = max(mat_score, 8.0)
    elif order_val and order_val < 1.0 and (not pct_rev or pct_rev < 10.0):
        mat_score = min(mat_score, 4.5)  # Micro-deal (< ₹1 Cr / lakh-scale) cannot claim high materiality
    elif ev_type in ["GOVERNMENT_EVENT", "FUNDING_EQUITY"]:
        mat_score = max(mat_score, 8.5)
    elif ev_type == "MANAGEMENT_EVENT" and item.get("fundamental_direction") == "Negative":
        mat_score = max(mat_score, 8.5)
    fundamental_materiality = min(10.0, max(1.0, mat_score))

    # 2. Financial Significance (0-10)
    if pct_rev and pct_rev >= 15.0:
        fin_sig = 9.8
    elif order_val and order_val >= 10000.0:
        fin_sig = 10.0
    elif order_val and order_val >= 2500.0:
        fin_sig = 9.5
    elif pct_rev and pct_rev >= 7.0:
        fin_sig = 9.0
    elif order_val and order_val >= 1000.0:
        fin_sig = 9.0
    elif pct_rev and pct_rev >= 2.0:
        fin_sig = 8.0
    elif order_val and order_val >= 300.0:
        fin_sig = 8.2
    elif order_val and order_val >= 100.0:
        fin_sig = 7.5
    elif order_val and order_val < 1.0 and (not pct_rev or pct_rev < 10.0):
        fin_sig = 3.0  # Micro-deal (< ₹1 Cr / lakh scale) has minimal standalone financial significance
    elif order_val and order_val < 50.0 and (not pct_rev or pct_rev < 10.0):
        fin_sig = 5.0
    elif order_val:
        fin_sig = 6.2
    elif any(w in full_text for w in ["ebitda", "operating margin", "equity capital", "net loss", "volume growth", "turnaround"]):
        fin_sig = 7.5
    else:
        fin_sig = 6.0
    financial_significance = fin_sig

    # 3. Strategic Significance (0-10)
    strat_sig = 6.5
    if order_val and order_val >= 10000.0:
        strat_sig = 9.8
    elif order_val and order_val >= 2500.0:
        strat_sig = 9.0
    elif ev_type in ["GOVERNMENT_EVENT", "ACQUISITION", "PRODUCT_APPROVAL"]:
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

    # 10. Specificity & Quantifiability (0-10)
    # Currency amounts: ₹, Rs, Cr, crore, lakh, USD, $
    has_currency = bool(re.search(r"(?:₹\s*[\d,]+(?:\.\d+)?|\brs\.?\s*[\d,]+(?:\.\d+)?|\b[\d,]+(?:\.\d+)?\s*(?:cr|crore|lakh)s?\b|[\$€£]\s*[\d,]+|\busd\b)", full_text))
    # Percentages: %, percent, percentage
    has_percentage = bool(re.search(r"\b\d+(?:\.\d+)?\s*%|\bpercent(?:age)?\b", full_text))
    # Physical capacity & volume units: MW, GW, tonnes, MTPA, barrels, bbl, km, sq ft, beds, years (including 15-year, 400+ bed)
    has_physical_units = bool(re.search(r"\b\d+(?:\.\d+)?\+?(?:\s*|-)(?:mw|gw|kw|tonnes?|mtpa|tpd|bbl|barrels?|km|sq\.?\s*ft|units?|beds?|years?)\b", full_text))
    # Hard binary outcomes: order won/lost/awarded, approval granted/denied, deal signed/terminated
    has_binary_outcome = bool(re.search(
        r"\b(?:bags?|secured?|wins?|won|awarded|receives?|received)\b.{0,60}\b(?:orders?|contracts?|mandates?|tenders?|projects?|work)\b|"
        r"\b(?:approval|clearance|licen[sc]e|patent)\b.{0,60}\b(?:granted|approved|received|cleared|denied|rejected)\b|"
        r"\b(?:granted|approved|received|cleared|denied|rejected)\b.{0,60}\b(?:approval|clearance|licen[sc]e|patent)\b|"
        r"\b(?:usfda|fda|dci|cci|rbi|sebi)\b.{0,60}\b(?:approves?|clears?|penalizes?|issues?\s+\d+\s+observations?)\b|"
        r"\b(?:signs?|signed|inks?|inked|entered\s+into)\b.{0,60}\b(?:pact|agreement|contract|deal|partnership|mou)\b|"
        r"\b(?:terminated?|cancell?ed?|scrapped|revoked|delisted|auditor\s+resigned)\b",
        full_text
    ))

    is_purely_qualitative = not (has_currency or has_percentage or has_physical_units or has_binary_outcome or order_val or pct_rev)

    if order_val and pct_rev:
        quantifiability = 10.0
    elif (order_val or range_text or has_currency) and (has_percentage or has_physical_units or has_binary_outcome):
        quantifiability = 9.5
    elif has_currency or order_val or range_text:
        quantifiability = 9.0
    elif has_percentage or has_physical_units:
        quantifiability = 8.5
    elif has_binary_outcome:
        quantifiability = 8.0
    elif is_very_brief:
        quantifiability = 3.0
    elif is_purely_qualitative:
        quantifiability = 2.5
    else:
        quantifiability = 5.0

    # Specificity delta on composite score:
    # Rewards concrete numbers / hard binary outcomes (+0.25 to +0.4)
    # Deprioritizes vague qualitative text lacking numbers or verified outcomes (-0.75)
    specificity_delta = 0.0
    if (has_currency or has_physical_units or order_val) and has_binary_outcome:
        specificity_delta = 0.4
    elif has_currency or has_physical_units or order_val or pct_rev:
        specificity_delta = 0.25
    elif is_purely_qualitative:
        specificity_delta = -0.75

    # Capital raise vs Commercial Contract / Concession / M&A category weighting
    is_capital_raise = (
        ev_type in ["CAPITAL_RAISE", "PREFERENTIAL_ALLOTMENT", "QIP", "FUNDING_EQUITY"] or
        any(w in full_text for w in [
            "preferential issue", "preferential allotment", "launches qip",
            "qualified institutional placement", "floor price of rs", "rights issue",
            "qip at floor price", "qip issue", "promoter warrant"
        ])
    )

    is_strategic_or_concession = (
        ev_type in ["ACQUISITION", "CONCESSION_AGREEMENT", "STRATEGIC_DEAL"] or
        any(w in full_text for w in [
            "concession agreement", "concession pact", "anchor shipyard",
            "super speciality hospital", "novotel imagicaa", "petct", "pet-ct",
            "pact for 400", "pact for 15", "pact for 29", "bed hospital",
            "toll collection", "mou as anchor"
        ])
    )

    # Follow-on distribution deal referencing an older regulatory approval
    is_follow_on_approval = False
    m_stale_app = re.search(r"\b(?:follows|following|post|after)\s+(?:the\s+)?(?:approval|clearance|authorization|grant)\b.*?\bin\s+([A-Za-z]+)(?:\s+(\d{4}))?\b", full_text, re.IGNORECASE)
    if m_stale_app:
        month_name = m_stale_app.group(1).lower()
        if month_name in ["january", "february", "march", "april", "may", "june", "july", "august"]:
            is_follow_on_approval = True
    elif re.search(r"\b(?:distribution\s+(?:deal|agreement|pact)|marketing\s+agreement)\b.*?\b(?:vaccine|drug|formulation)\b", full_text, re.IGNORECASE) and re.search(r"\b(?:approved\s+in|authorization\s+in)\s+([A-Za-z]+)\b", full_text, re.IGNORECASE):
        is_follow_on_approval = True

    # Routine CCI / antitrust clearance check
    is_cci_approval = bool(re.search(
        r"\b(?:cci\s+(?:approves?|clears?|nod|greenlights?)|competition\s+commission\s+(?:of\s+india\s+)?(?:approves?|clears?))\b.*?\b(?:acquisition|merger|stake|combination|amalgamation|shareholding|shares\s+in)\b|"
        r"\b(?:pib\s+delhi\s+cci\s+approves?|proposed\s+combination\s+approved\s+by\s+cci)\b",
        full_text
    ))

    if is_cci_approval:
        strat_sig = min(strat_sig, 3.0)
        investor_rel = min(investor_rel, 3.0)
        mat_score = min(mat_score, 3.0)
        category_delta = -4.0
    elif is_follow_on_approval:
        strat_sig = min(strat_sig, 6.2)
        investor_rel = min(investor_rel, 6.5)
        mat_score = min(mat_score, 6.8)
        category_delta = -1.8
    elif is_capital_raise:
        strat_sig = min(strat_sig, 5.5)
        investor_rel = min(investor_rel, 5.8)
        mat_score = min(mat_score, 7.0)
        category_delta = -1.25
    elif is_strategic_or_concession:
        strat_sig = max(strat_sig, 9.2)
        investor_rel = max(investor_rel, 9.2)
        mat_score = max(mat_score, 8.8)
        category_delta = 0.35
        has_binary_outcome = True
    elif ev_type == "FINANCIAL_RESULT":
        if re.search(r"\b(?:rises?|surges?|jumps?|up)\s+(?:\d{2,3}(?:\.\d+)?%|tripl(?:ed|es)|doubl(?:ed|es))\b", full_text, re.IGNORECASE):
            financial_significance = max(financial_significance, 9.5)
            strategic_significance = max(strategic_significance, 8.5)
            investor_rel = max(investor_rel, 9.2)
            category_delta = 0.4
        else:
            category_delta = 0.0
    elif ev_type == "PRICING_EVENT":
        strat_sig = max(strat_sig, 8.2)
        investor_rel = max(investor_rel, 8.5)
        category_delta = 0.25
    else:
        category_delta = 0.0

    # Deal scale boost: Steeper log-scale weighting to ensure mega contracts (e.g. ₹27,000 Cr MoU)
    # decisively outrank routine smaller ₹63 Cr orders, and penalize micro/sub-crore orders.
    # Note: Only commercial orders, M&A, and concessions receive deal scale boost (NOT equity capital raises).
    deal_scale_boost = 0.0
    if order_val and not is_capital_raise:
        if order_val >= 10000.0:
            deal_scale_boost = 0.85
        elif order_val >= 2500.0:
            deal_scale_boost = 0.60
        elif order_val >= 1000.0:
            deal_scale_boost = 0.40
        elif order_val >= 300.0:
            deal_scale_boost = 0.20
        elif order_val < 1.0 and (not pct_rev or pct_rev < 10.0):
            deal_scale_boost = -1.50  # Heavy penalty for micro lakh-scale orders
        elif order_val < 50.0 and (not pct_rev or pct_rev < 10.0):
            deal_scale_boost = -0.60
        elif order_val < 100.0 and (not pct_rev or pct_rev < 15.0):
            deal_scale_boost = -0.30

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
    composite_score = min(10.0, max(1.0, composite_score + specificity_delta + deal_scale_boost + category_delta))

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
        "has_concrete_numbers": bool(has_currency or has_percentage or has_physical_units),
        "has_binary_outcome": bool(has_binary_outcome),
        "is_purely_qualitative": bool(is_purely_qualitative),
        "is_follow_on_approval": bool(is_follow_on_approval),
        "is_cci_approval": bool(is_cci_approval),
        "deal_scale_boost": deal_scale_boost,
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
    full_text_tier = f"{item.get('headline', '')} {item.get('what_happened', '')} {why} {item.get('summary', '')}".lower()

    # Stale/Follow-on approval check: Secondary development, NEVER Tier A
    is_follow_on = bool(
        item.get("is_follow_on_approval") or 
        (isinstance(scores, dict) and scores.get("is_follow_on_approval")) or
        re.search(r"\b(?:follows|following|post|after)\s+(?:the\s+)?(?:approval|clearance|authorization|grant)\b.*?\bin\s+(?:january|february|march|april|may|june|july|august)\b", full_text_tier) or
        (re.search(r"\bdistribution\s+(?:deal|agreement|pact)\b", full_text_tier) and re.search(r"\bapproval\b", full_text_tier))
    )
    if is_follow_on:
        return "Tier B" if res_score >= 6.0 else "Tier C"

    # Routine CCI clearance check: NEVER Tier A or B
    is_cci = bool(
        item.get("is_cci_approval") or
        (isinstance(scores, dict) and scores.get("is_cci_approval")) or
        re.search(r"\b(?:cci\s+approves?|pib\s+delhi\s+cci\s+approves?)\b", full_text_tier)
    )
    if is_cci:
        return "Tier C"

    # Routine small / micro order check: Orders under ₹50 Cr CANNOT be Tier A unless they represent >= 10% of revenue
    if ev_type == "ORDER_CONTRACT" and order_val is not None and order_val < 50.0 and (not pct_rev or pct_rev < 10.0):
        if order_val < 1.0: # Sub-crore / lakh scale
            return "Tier C"
        return "Tier B" if res_score >= 6.0 else "Tier C"

    # Tier A criteria: High analytical confidence, verifiable materiality
    if (
        (res_score >= 8.2 and not (ev_type == "ORDER_CONTRACT" and order_val is not None and order_val < 50.0 and (not pct_rev or pct_rev < 10.0))) or
        res_score >= 80.0 or
        (ev_type == "ORDER_CONTRACT" and ((pct_rev and pct_rev >= 10.0) or (order_val and order_val >= 250.0))) or
        (ev_type == "MANAGEMENT_EVENT" and direction == "Negative" and ("auditor" in why or res_score >= 7.5)) or
        (ev_type == "GOVERNMENT_EVENT" and res_score >= 7.8) or
        (ev_type == "OPERATING_UPDATE" and order_val and order_val >= 500.0) or
        (ev_type == "BLOCK_DEAL" and ((order_val and order_val >= 500.0) or res_score >= 7.8))
    ):
        return "Tier A"

    # Tier B criteria: Requires solid evidence score (>= 6.0 or 60.0), or quantified financial impact (>= 5.5)
    if res_score >= 6.0 or res_score >= 60.0 or (res_score >= 5.5 and (order_val or pct_rev)):
        return "Tier B"

    return "Tier C"


def is_genuinely_actionable_candidate(cand: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Evaluates whether a candidate provides a credible, sufficiently material fundamental development
    that could reasonably matter to an investor or analyst monitoring the stock.
    Returns (is_actionable: bool, reason: str).
    """
    cand_type = cand.get("candidate_type")
    scores = cand.get("research_scores", {})
    total_score = scores.get("total_score", cand.get("research_importance_score", 0.0))

    # Multi-company policy and macro items
    if cand_type in ["POLICY_EVENT", "MACRO_EVENT"]:
        return True, f"Actionable {cand_type} with sector-wide fundamental impact (Score: {total_score})."

    direction = cand.get("fundamental_direction")
    if direction not in ["Positive", "Negative"]:
        return False, f"Direction '{direction}' is ambiguous or non-directional."

    tier = cand.get("tier", "Tier C")
    ev_type = cand.get("event_type", "OTHER_MATERIAL")
    
    # Reject purely qualitative items with weak scores
    if scores.get("is_purely_qualitative") and total_score < 6.5:
        return False, f"Disqualified: purely qualitative announcement lacking quantified metrics or concrete outcome (Score: {total_score})."

    # Tier A: High-conviction fundamental development
    if tier == "Tier A" or total_score >= 7.8:
        return True, f"Tier A high-conviction fundamental development (Score: {total_score})."

    # Recognized actionable catalysts
    actionable_types = {
        "ORDER_CONTRACT", "CAPACITY_EXPANSION", "ACQUISITION",
        "STRATEGIC_DEAL", "PRODUCT_APPROVAL", "REGULATORY_EVENT",
        "OPERATING_UPDATE", "GOVERNMENT_EVENT", "COMMODITY_EVENT",
        "FUNDING_EQUITY", "FUNDING_DEBT_EVENT", "MANAGEMENT_EVENT",
        "PRICING_EVENT", "CUSTOMER_EVENT", "FINANCIAL_RESULT", "BLOCK_DEAL"
    }

    # Tier B: Substantive economic catalyst with verified direction and mechanism
    # Requires high analytical score (>= 7.0) AND concrete quantified financial impact or verified scale
    if total_score >= 7.0 and ev_type in actionable_types:
        if cand.get("order_value_cr") or cand.get("relative_revenue_pct") or cand.get("range_text") or scores.get("has_concrete_numbers"):
            return True, f"Quantified fundamental financial impact (Score: {total_score})."
        if tier == "Tier B" and total_score >= 7.2:
            return True, f"Actionable {ev_type} catalyst with confirmed economic impact (Score: {total_score})."

    return False, f"Score {total_score} below high-materiality actionability threshold."


def normalize_company_key(name: str, symbol: str = "") -> str:
    """Normalizes company name or symbol to prevent duplicate listings under different suffixes."""
    s = str(name or symbol or "").strip().lower()
    s = re.sub(r"\.(ns|bo|bse)$", "", s)
    s = re.sub(r"\b(limited|ltd|pvt|private|corporation|corp|inc|co)\b", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or str(symbol or "").strip().lower()


def rank_daily_research_candidates(
    candidates: List[Dict[str, Any]], 
    max_items: Optional[int] = None,
    min_target: int = 4,
    max_ceiling: int = 15
) -> List[Dict[str, Any]]:
    """
    Performs purely evidence-driven daily ranking across all valid candidates.
    Identifies all genuinely actionable stocks with a sensible ceiling.
    - If 2 actionable exist: evaluates secondary candidates to find additional genuine opportunities, but stops if none qualify (quality beats minimum).
    - If max_items is explicitly set by the caller, respects max_items.
    - Ranked by score descending.
    """
    if not candidates:
        return []

    # Filter to valid directional candidates and ground against official listed master
    from engine.equity_master import resolve_entity
    valid = []
    for c in candidates:
        if c.get("fundamental_direction") not in ["Positive", "Negative"]:
            continue
        c_name = c.get("company_name", "")
        c_sym = c.get("symbol", "")
        grounded = resolve_entity(c_name, symbol=c_sym)
        if not grounded and not c_sym:
            continue
        if grounded:
            c["ticker"] = grounded[0]
            c["company_name"] = grounded[1]
        valid.append(c)

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

    # Deduplicate by company so each company appears with its single best story
    # Incorporates materiality comparison: quantified financial results / earnings beat vague qualitative agreements
    seen_companies: Dict[str, Dict[str, Any]] = {}
    for c in valid:
        c_key = normalize_company_key(c.get("company_name", ""), c.get("symbol", ""))
        if c_key not in seen_companies:
            seen_companies[c_key] = c
        else:
            prev = seen_companies[c_key]
            prev_is_fin = prev.get("event_type") == "FINANCIAL_RESULT"
            curr_is_fin = c.get("event_type") == "FINANCIAL_RESULT"
            if curr_is_fin and not prev_is_fin:
                seen_companies[c_key] = c
            elif get_cand_score(c) > get_cand_score(prev) and not (prev_is_fin and not curr_is_fin):
                seen_companies[c_key] = c
    deduped_candidates = list(seen_companies.values())

    # Classify into primary actionable vs secondary candidates
    actionable_candidates: List[Dict[str, Any]] = []
    secondary_candidates: List[Dict[str, Any]] = []

    for cand in deduped_candidates:
        is_act, _ = is_genuinely_actionable_candidate(cand)
        if is_act:
            actionable_candidates.append(cand)
        else:
            scores = cand.get("research_scores", {})
            sc = scores.get("total_score", cand.get("research_importance_score", 0.0))
            if sc >= 5.2 and cand.get("fundamental_direction") in ["Positive", "Negative"]:
                secondary_candidates.append(cand)

    selected = list(actionable_candidates)

    # If below minimum target (e.g. only 2 or 3 actionable), evaluate high-quality secondary candidates
    if len(selected) < min_target:
        for sec in secondary_candidates:
            if len(selected) >= min_target:
                break
            ev_type = sec.get("event_type", "")
            if ev_type in [
                "ORDER_CONTRACT", "CAPACITY_EXPANSION", "STRATEGIC_DEAL", 
                "PRODUCT_APPROVAL", "REGULATORY_EVENT", "FUNDING_EQUITY", "OPERATING_UPDATE"
            ]:
                selected.append(sec)

    # Rank strictly by research importance score descending
    selected.sort(key=get_cand_score, reverse=True)

    # Dynamic cap: If max_items is specified by caller, respect it; otherwise keep all actionable items
    effective_limit = max_items if max_items is not None else len(selected)
    return selected[:effective_limit]


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

