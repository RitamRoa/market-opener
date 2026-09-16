"""
Policy & Macro Intelligence Engine for Indian Equities.
Detects and structures:
1. Multi-company Policy/Regulatory events with Sector Beneficiaries/Impacted lists.
2. Standalone Macro/Market-Context items crossing materiality thresholds.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Sector to leading listed equities mapping
SECTOR_MEMBERS: Dict[str, List[Dict[str, str]]] = {
    "UPI_PAYMENTS": [
        {"symbol": "PAYTM", "name": "One97 Communications (Paytm)", "default_impact": "Positive"},
        {"symbol": "YESBANK", "name": "Yes Bank Ltd", "default_impact": "Positive"},
        {"symbol": "AXISBANK", "name": "Axis Bank Ltd", "default_impact": "Positive"},
        {"symbol": "SBIN", "name": "State Bank of India", "default_impact": "Positive"},
        {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd", "default_impact": "Positive"},
        {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd", "default_impact": "Positive"},
    ],
    "DEFENSE": [
        {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd", "default_impact": "Positive"},
        {"symbol": "BEL", "name": "Bharat Electronics Ltd", "default_impact": "Positive"},
        {"symbol": "MAZDOCK", "name": "Mazagon Dock Shipbuilders", "default_impact": "Positive"},
        {"symbol": "BDL", "name": "Bharat Dynamics Ltd", "default_impact": "Positive"},
        {"symbol": "COCHINSHIP", "name": "Cochin Shipyard Ltd", "default_impact": "Positive"},
    ],
    "RENEWABLE_SOLAR": [
        {"symbol": "TATAPOWER", "name": "Tata Power Company Ltd", "default_impact": "Positive"},
        {"symbol": "ADANIGREEN", "name": "Adani Green Energy Ltd", "default_impact": "Positive"},
        {"symbol": "ACMESOLAR", "name": "ACME Solar Holdings Ltd", "default_impact": "Positive"},
        {"symbol": "SUZLON", "name": "Suzlon Energy Ltd", "default_impact": "Positive"},
        {"symbol": "IREDA", "name": "Indian Renewable Energy Development Agency", "default_impact": "Positive"},
    ],
    "OIL_GAS_DOWNSTREAM": [
        {"symbol": "IOC", "name": "Indian Oil Corporation Ltd", "default_impact": "Negative"},
        {"symbol": "BPCL", "name": "Bharat Petroleum Corporation Ltd", "default_impact": "Negative"},
        {"symbol": "HPCL", "name": "Hindustan Petroleum Corporation Ltd", "default_impact": "Negative"},
    ],
    "OIL_GAS_UPSTREAM": [
        {"symbol": "ONGC", "name": "Oil & Natural Gas Corporation Ltd", "default_impact": "Positive"},
        {"symbol": "OIL", "name": "Oil India Ltd", "default_impact": "Positive"},
    ],
    "AUTOMOTIVE_CV": [
        {"symbol": "TATAMOTORS", "name": "Tata Motors Ltd", "default_impact": "Positive"},
        {"symbol": "ASHOKLEY", "name": "Ashok Leyland Ltd", "default_impact": "Positive"},
        {"symbol": "BHARATFORG", "name": "Bharat Forge Ltd", "default_impact": "Positive"},
    ],
    "PHARMA_US_GENERIC": [
        {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries", "default_impact": "Positive"},
        {"symbol": "DRREDDY", "name": "Dr. Reddy's Laboratories", "default_impact": "Positive"},
        {"symbol": "CIPLA", "name": "Cipla Ltd", "default_impact": "Positive"},
        {"symbol": "LUPIN", "name": "Lupin Ltd", "default_impact": "Positive"},
        {"symbol": "AUROPHARMA", "name": "Aurobindo Pharma Ltd", "default_impact": "Positive"},
    ],
    "NBFC_LENDING": [
        {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd", "default_impact": "Negative"},
        {"symbol": "CHOLAFIN", "name": "Cholamandalam Investment & Finance", "default_impact": "Negative"},
        {"symbol": "SHRIRAMFIN", "name": "Shriram Finance Ltd", "default_impact": "Negative"},
        {"symbol": "MUTHOOTFIN", "name": "Muthoot Finance Ltd", "default_impact": "Negative"},
    ],
    "TELECOM": [
        {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd", "default_impact": "Positive"},
        {"symbol": "IDEA", "name": "Vodafone Idea Ltd", "default_impact": "Positive"},
        {"symbol": "TATACOMM", "name": "Tata Communications Ltd", "default_impact": "Positive"},
    ],
    "REALTY_INFRA": [
        {"symbol": "DLF", "name": "DLF Ltd", "default_impact": "Positive"},
        {"symbol": "GODREJPROP", "name": "Godrej Properties Ltd", "default_impact": "Positive"},
        {"symbol": "OBEROIRLTY", "name": "Oberoi Realty Ltd", "default_impact": "Positive"},
        {"symbol": "LT", "name": "Larsen & Toubro Ltd", "default_impact": "Positive"},
        {"symbol": "NBCC", "name": "NBCC (India) Ltd", "default_impact": "Positive"},
    ],
    "AVIATION": [
        {"symbol": "INDIGO", "name": "InterGlobe Aviation Ltd (IndiGo)", "default_impact": "Negative"},
        {"symbol": "SPICEJET", "name": "SpiceJet Ltd", "default_impact": "Negative"},
    ],
    "PAINTS": [
        {"symbol": "ASIANPAINT", "name": "Asian Paints Ltd", "default_impact": "Negative"},
        {"symbol": "BERGEPAINT", "name": "Berger Paints India Ltd", "default_impact": "Negative"},
    ],
    "CAPITAL_MARKETS_BROKING": [
        {"symbol": "ANGELONE", "name": "Angel One Ltd", "default_impact": "Negative"},
        {"symbol": "BSE", "name": "BSE Ltd", "default_impact": "Negative"},
        {"symbol": "MCX", "name": "Multi Commodity Exchange of India", "default_impact": "Negative"},
    ],
}


def detect_policy_event(event_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Identifies policy/regulatory notifications affecting multiple listed companies.
    Returns structured candidate if detected, else None.
    """
    title = str(event_dict.get("title", "")).strip()
    summary = str(event_dict.get("summary", "")).strip()
    full_text = f"{title} {summary}".lower()

    # Must contain regulatory / sovereign policy authority or policy terms
    regulators = [
        "rbi", "reserve bank of india", "sebi", "npci", "pngrb", "trai", "dgca",
        "cci", "fssai", "gst council", "ministry of finance", "cabinet", "ccea",
        "union cabinet", "centre", "government"
    ]
    has_regulator = any(re.search(rf"\b{re.escape(r)}\b", full_text) for r in regulators)

    policy_actions = [
        r"interchange\s+fee", r"merchant\s+fee", r"windfall\s+tax", r"import\s+duty",
        r"export\s+duty", r"customs\s+duty", r"tariff", r"subsid(?:y|ies)", r"pli\s+scheme",
        r"regulatory\s+framework", r"guidelines?", r"circular", r"mandates?", r"norms?",
        r"curbs?", r"tightens?\s+rules?", r"index\s+derivatives?", r"expiry\s+rules?",
        r"anti-?dumping\s+duty", r"safeguard\s+duty", r"fdi\s+limit", r"spectrum\s+auction"
    ]
    has_policy_action = any(re.search(p, full_text) for p in policy_actions)

    if not (has_regulator and has_policy_action):
        return None

    # Identify sector
    sector_key = None
    if any(k in full_text for k in ["upi", "digital payment", "merchant discount", "wallet"]):
        sector_key = "UPI_PAYMENTS"
    elif any(k in full_text for k in ["defence", "defense", "military", "dac approval", "arms procurement"]):
        sector_key = "DEFENSE"
    elif any(k in full_text for k in ["solar", "renewable", "green energy", "bess", "almm"]):
        sector_key = "RENEWABLE_SOLAR"
    elif any(k in full_text for k in ["windfall tax", "crude duty", "fuel export duty"]):
        sector_key = "OIL_GAS_UPSTREAM" if any(w in full_text for w in ["cut", "slashes", "reduces", "cuts"]) else "OIL_GAS_DOWNSTREAM"
    elif any(k in full_text for k in ["fno", "derivative", "options expiry", "index futures", "sebi norm"]):
        sector_key = "CAPITAL_MARKETS_BROKING"
    elif any(k in full_text for k in ["nbfc", "unsecured loan", "risk weight", "microfinance"]):
        sector_key = "NBFC_LENDING"
    elif any(k in full_text for k in ["telecom", "spectrum", "agr dues"]):
        sector_key = "TELECOM"
    elif any(k in full_text for k in ["generic", "usfda", "drug pricing", "pharma pli"]):
        sector_key = "PHARMA_US_GENERIC"
    elif any(k in full_text for k in ["commercial vehicle", "scrappage", "emission norm", "ev subsidy"]):
        sector_key = "AUTOMOTIVE_CV"
    elif any(k in full_text for k in ["aviation", "air turbine fuel", "atf"]):
        sector_key = "AVIATION"

    if not sector_key or sector_key not in SECTOR_MEMBERS:
        return None

    beneficiaries = list(SECTOR_MEMBERS[sector_key])

    # Determine general directionality
    pos_words = ["cuts", "slashes", "reduces", "lowers tax", "subsidy", "incentive", "approves", "hikes duty on import", "anti-dumping", "waiver", "concession"]
    neg_words = ["hikes tax", "imposes duty", "curbs", "tightens", "penalty", "restricts", "higher risk weight", "ban", "scrutiny"]
    
    direction = "Positive"
    if any(w in full_text for w in neg_words):
        direction = "Negative"
    elif any(w in full_text for w in pos_words):
        direction = "Positive"

    # Adjust beneficiary impacts based on direction
    adjusted_beneficiaries = []
    for b in beneficiaries:
        item_copy = dict(b)
        if direction == "Negative" and b.get("default_impact") == "Positive":
            item_copy["impact"] = "Negative"
        elif direction == "Positive" and b.get("default_impact") == "Negative":
            item_copy["impact"] = "Positive"
        else:
            item_copy["impact"] = b.get("default_impact", direction)
        adjusted_beneficiaries.append(item_copy)

    # Score policy event high on research importance (typically 8.0 - 8.8)
    score = 8.5
    if any(w in full_text for w in ["cr", "crore", "%", "lakh"]):
        score += 0.3

    return {
        "candidate_type": "POLICY_EVENT",
        "company_name": f"Policy & Regulatory: {sector_key.replace('_', ' ').title()}",
        "symbol": f"SECTOR:{sector_key}",
        "sector": sector_key,
        "headline": title,
        "what_happened": summary or title,
        "why_it_matters": f"Sector-wide regulatory change issued by regulatory authorities affecting commercial terms and operational parameters across {sector_key.replace('_', ' ').title()}.",
        "key_beneficiaries": adjusted_beneficiaries,
        "sources": event_dict.get("source", "Regulatory Notification / Exchange"),
        "published_at": event_dict.get("published_at", ""),
        "research_importance_score": round(score, 2),
        "research_scores": {"total_score": round(score, 2), "fundamental_materiality": 9.0},
        "tier": "Tier A",
        "fundamental_direction": direction,
        "closing_price": None
    }


def detect_macro_item(event_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Identifies standalone macro/market-context triggers crossing materiality thresholds.
    Returns structured macro entry if detected, else None.
    """
    title = str(event_dict.get("title", "")).strip()
    summary = str(event_dict.get("summary", "")).strip()
    full_text = f"{title} {summary}".lower()

    # 1. US 10-Year Treasury Yield
    if re.search(r"\b(?:us|u\.s\.)?\s*(?:10-?year|ten-?year|10y)\s*(?:treasury|bond)?\s*yield\b", full_text):
        if any(w in full_text for w in ["crosses", "surges", "rallies", "hits", "high", "5%", "4.5%", "4.8%", "jumps"]):
            return {
                "candidate_type": "MACRO_EVENT",
                "company_name": "Macro Trigger: US 10-Year Treasury Yield",
                "symbol": "MACRO:US10Y",
                "sector": "NBFCs & Growth Equities",
                "headline": title,
                "macro_one_liner": f"{title} — Negative for NBFCs & Growth Equities",
                "what_happened": summary or title,
                "why_it_matters": "Elevated US sovereign yields raise global cost of capital and prompt emerging market capital outflows, compressing valuation multiples for rate-sensitive financials.",
                "affected_sector": "NBFCs & Growth Equities",
                "fundamental_direction": "Negative",
                "sources": event_dict.get("source", "Global Macro Wire"),
                "research_importance_score": 8.3,
                "research_scores": {"total_score": 8.3, "fundamental_materiality": 8.5},
                "tier": "Tier A",
                "closing_price": None
            }
        elif any(w in full_text for w in ["falls", "slips", "eases", "drops", "plunges", "cools"]):
            return {
                "candidate_type": "MACRO_EVENT",
                "company_name": "Macro Trigger: US 10-Year Treasury Yield",
                "symbol": "MACRO:US10Y",
                "sector": "Emerging Market Equities",
                "headline": title,
                "macro_one_liner": f"{title} — Positive for Emerging Market Equities & NBFCs",
                "what_happened": summary or title,
                "why_it_matters": "Easing US sovereign yields reduce global borrowing costs and improve equity risk premiums for high-growth sectors.",
                "affected_sector": "Emerging Market Equities & NBFCs",
                "fundamental_direction": "Positive",
                "sources": event_dict.get("source", "Global Macro Wire"),
                "research_importance_score": 8.1,
                "research_scores": {"total_score": 8.1, "fundamental_materiality": 8.2},
                "tier": "Tier A",
                "closing_price": None
            }

    # 2. Crude Oil (Brent / WTI)
    if re.search(r"\b(?:brent(?:\s+crude)?|crude\s+oil|wti\s+crude)\b", full_text):
        if any(w in full_text for w in ["crosses $", "surges past", "rallies above", "spikes to", "highest since", "hits $8", "hits $9", "crosses 8", "crosses 9"]):
            return {
                "candidate_type": "MACRO_EVENT",
                "company_name": "Macro Trigger: Crude Oil Spike",
                "symbol": "MACRO:CRUDE",
                "sector": "Aviation, Paints & OMCs",
                "headline": title,
                "macro_one_liner": f"{title} — Negative for Paints, Aviation & OMCs; Positive for Upstream E&P",
                "what_happened": summary or title,
                "why_it_matters": "Spike in Brent crude inflates petrochemical and aviation turbine fuel input costs, compressing margins for downstream consumers while expanding upstream realizations.",
                "affected_sector": "Paints, Aviation & Downstream OMCs",
                "fundamental_direction": "Negative",
                "sources": event_dict.get("source", "Commodities Wire"),
                "research_importance_score": 8.4,
                "research_scores": {"total_score": 8.4, "fundamental_materiality": 8.6},
                "tier": "Tier A",
                "closing_price": None
            }
        elif any(w in full_text for w in ["falls below $", "drops to", "slumps to", "slides to", "plunges", "lowest since", "sub-$70", "below $75"]):
            return {
                "candidate_type": "MACRO_EVENT",
                "company_name": "Macro Trigger: Crude Oil Slump",
                "symbol": "MACRO:CRUDE",
                "sector": "Aviation, Paints & OMCs",
                "headline": title,
                "macro_one_liner": f"{title} — Positive for Paints, Aviation & OMCs; Negative for Upstream E&P",
                "what_happened": summary or title,
                "why_it_matters": "Slumping crude prices ease raw material costs for paint manufacturers, reduce ATF expenses for airlines, and expand retail fuel marketing margins for downstream OMCs.",
                "affected_sector": "Paints, Aviation & Downstream OMCs",
                "fundamental_direction": "Positive",
                "sources": event_dict.get("source", "Commodities Wire"),
                "research_importance_score": 8.2,
                "research_scores": {"total_score": 8.2, "fundamental_materiality": 8.3},
                "tier": "Tier A",
                "closing_price": None
            }

    # 3. Currency / Forex (USD/INR)
    if re.search(r"\b(?:rupee|usd/?inr|forex reserves)\b", full_text):
        if any(w in full_text for w in ["all-time low", "record low", "depreciates past", "weakens to", "hits 84", "hits 85"]):
            return {
                "candidate_type": "MACRO_EVENT",
                "company_name": "Macro Trigger: Rupee Depreciation",
                "symbol": "MACRO:USDINR",
                "sector": "IT Exporters & Importers",
                "headline": title,
                "macro_one_liner": f"{title} — Positive for IT & Pharma Exporters; Negative for Importers",
                "what_happened": summary or title,
                "why_it_matters": "Rupee depreciation enhances rupee realizations for dollar-earning IT and pharma exporters while inflating landed procurement costs for oil, electronic, and capital goods importers.",
                "affected_sector": "IT & Pharma Exporters",
                "fundamental_direction": "Positive",
                "sources": event_dict.get("source", "Forex Wire"),
                "research_importance_score": 8.1,
                "research_scores": {"total_score": 8.1, "fundamental_materiality": 8.2},
                "tier": "Tier A",
                "closing_price": None
            }

    # 4. Central Bank Rates (RBI / Fed)
    if re.search(r"\b(?:rbi\s+mpc|federal\s+reserve|fomc|repo\s+rate|rate\s+cut|rate\s+hike)\b", full_text):
        if any(w in full_text for w in ["hikes rate", "raises repo", "rate hike", "hawkish"]):
            return {
                "candidate_type": "MACRO_EVENT",
                "company_name": "Macro Trigger: Monetary Tightening",
                "symbol": "MACRO:RATES",
                "sector": "Realty, Auto & NBFCs",
                "headline": title,
                "macro_one_liner": f"{title} — Negative for Rate-Sensitive Sectors (Realty, Auto, NBFCs)",
                "what_happened": summary or title,
                "why_it_matters": "Monetary tightening raises benchmark borrowing rates, increasing consumer EMI burdens and dampening housing and automotive retail credit demand.",
                "affected_sector": "Realty, Auto & NBFCs",
                "fundamental_direction": "Negative",
                "sources": event_dict.get("source", "Central Bank Wire"),
                "research_importance_score": 8.5,
                "research_scores": {"total_score": 8.5, "fundamental_materiality": 8.8},
                "tier": "Tier A",
                "closing_price": None
            }
        elif any(w in full_text for w in ["cuts rate", "slashes repo", "rate cut", "dovish", "eases policy"]):
            return {
                "candidate_type": "MACRO_EVENT",
                "company_name": "Macro Trigger: Monetary Easing",
                "symbol": "MACRO:RATES",
                "sector": "Realty, Auto & NBFCs",
                "headline": title,
                "macro_one_liner": f"{title} — Positive for Rate-Sensitive Sectors (Realty, Auto, NBFCs)",
                "what_happened": summary or title,
                "why_it_matters": "Monetary easing lowers home and auto financing costs, stimulating consumer borrowing and expanding loan origination volumes for banks and NBFCs.",
                "affected_sector": "Realty, Auto & NBFCs",
                "fundamental_direction": "Positive",
                "sources": event_dict.get("source", "Central Bank Wire"),
                "research_importance_score": 8.5,
                "research_scores": {"total_score": 8.5, "fundamental_materiality": 8.8},
                "tier": "Tier A",
                "closing_price": None
            }

    return None
