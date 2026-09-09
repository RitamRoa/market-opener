"""
Second-Order Effects Engine for Indian Equities.
Analyzes economic ripple effects, supply chain beneficiaries, competitive disruptions,
and cross-sector implications of major events and macro triggers.
"""

from typing import Dict, Any, List

# Macro and sector ripple rules
SECTOR_RIPPLE_MAP = {
    "Crude Oil Surge": {
        "beneficiaries": [
            {"sector": "Oil Exploration & Production", "stocks": ["ONGC.NS", "OIL.NS"], "impact": "POSITIVE", "reason": "Higher realized crude prices expand upstream margins"},
            {"sector": "Renewable Energy", "stocks": ["IREDA.NS", "SUZLON.NS", "TATAPOWER.NS"], "impact": "POSITIVE", "reason": "Cost parity shifts capital allocation toward alternative energy"}
        ],
        "detriments": [
            {"sector": "Aviation", "stocks": ["INDIGO.NS", "SPICEJET.NS"], "impact": "NEGATIVE", "reason": "Aviation Turbine Fuel (ATF) constitutes ~40% of airline operational expense"},
            {"sector": "Paints & Coatings", "stocks": ["ASIANPAINT.NS", "BERGEPAINT.NS"], "impact": "NEGATIVE", "reason": "Crude derivatives (titanium dioxide, solvents) inflate raw material costs"},
            {"sector": "Tyres & Elastomers", "stocks": ["MRF.NS", "APOLLOTYRE.NS"], "impact": "MIXED", "reason": "Synthetic rubber costs rise, squeezing gross margins"}
        ]
    },
    "Defense / Infrastructure Capex Boost": {
        "beneficiaries": [
            {"sector": "Aerospace & Defense", "stocks": ["HAL.NS", "BEL.NS", "MAZDOCK.NS"], "impact": "POSITIVE", "reason": "Direct domestic order book expansion under Atmanirbhar Bharat"},
            {"sector": "Capital Goods & Cables", "stocks": ["LT.NS", "BHEL.NS", "POLYCAB.NS"], "impact": "POSITIVE", "reason": "Execution subcontracting and electrification demand surge"},
            {"sector": "Specialty Steel & Metals", "stocks": ["TATASTEEL.NS", "JINDALSTEL.NS"], "impact": "POSITIVE", "reason": "Raw structural metal procurement acceleration"}
        ],
        "detriments": [
            {"sector": "Fiscal Deficit Sensitive Bonds", "stocks": [], "impact": "MIXED", "reason": "High borrowing pressures short-term sovereign bond yields"}
        ]
    },
    "Power & Data Center Electrification Surge": {
        "beneficiaries": [
            {"sector": "Power Generation & Grid", "stocks": ["NTPC.NS", "POWERGRID.NS", "TATAPOWER.NS"], "impact": "POSITIVE", "reason": "Baseload and transmission capacity demand surges to support AI compute"},
            {"sector": "Electrical Infrastructure", "stocks": ["SIEMENS.NS", "ABB.NS", "CGPOWER.NS"], "impact": "POSITIVE", "reason": "High-voltage switchgears and transformers order inflow"}
        ],
        "detriments": [
            {"sector": "Energy Intensive Smelters", "stocks": [], "impact": "MIXED", "reason": "Peak industrial power tariff hikes squeeze operating margins"}
        ]
    },
    "Automobile Commercial Vehicle Demand": {
        "beneficiaries": [
            {"sector": "Auto Ancillaries & Castings", "stocks": ["BHARATFORG.NS", "MOTHERSON.NS"], "impact": "POSITIVE", "reason": "Higher component production runs improve plant utilization"}
        ],
        "detriments": [
            {"sector": "Rail Freight Substitution", "stocks": ["CONCOR.NS"], "impact": "MIXED", "reason": "Intensified road transport freight competition"}
        ]
    }
}

# Company-to-Competitor / Supply chain mapping
COMPETITOR_MAP = {
    "TCS.NS": {"competitors": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS"], "sector": "IT"},
    "INFY.NS": {"competitors": ["TCS.NS", "HCLTECH.NS", "WIPRO.NS"], "sector": "IT"},
    "HDFCBANK.NS": {"competitors": ["ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS"], "sector": "Banking"},
    "ICICIBANK.NS": {"competitors": ["HDFCBANK.NS", "AXISBANK.NS", "SBIN.NS"], "sector": "Banking"},
    "TATAMOTORS.NS": {"competitors": ["MARUTI.NS", "M&M.NS", "ASHOKLEY.NS"], "sector": "Auto"},
    "MARUTI.NS": {"competitors": ["TATAMOTORS.NS", "M&M.NS", "HYUNDAI.NS"], "sector": "Auto"},
    "HAL.NS": {"competitors": ["BEL.NS", "BEML.NS"], "sector": "Defense"},
    "INDIGO.NS": {"competitors": ["SPICEJET.NS", "AIRINDIA"], "sector": "Aviation"},
    "ASIANPAINT.NS": {"competitors": ["BERGEPAINT.NS", "KANSAINER.NS", "PIDILITIND.NS"], "sector": "Paints/Chemicals"},
    "ZOMATO.NS": {"competitors": ["SWIGGY.NS"], "sector": "Quick Commerce"},
    "POLYCAB.NS": {"competitors": ["KEI.NS", "HAVANCELL.NS"], "sector": "Cables & Electricals"}
}


def analyze_second_order_effects(symbol: str, event_title: str, event_type: str, sector: str) -> Dict[str, Any]:
    """
    Evaluates second-order ramifications of an event:
    1. Who benefits?
    2. Who loses?
    3. Competitor implications
    4. Cross-sector ripple
    """
    beneficiaries = []
    detriments = []
    competitor_implication = ""
    ripple_notes = []

    text = f"{event_title} {sector}".lower()

    # Check macro ripples
    if "oil" in text or "crude" in text:
        rule = SECTOR_RIPPLE_MAP["Crude Oil Surge"]
        beneficiaries.extend(rule["beneficiaries"])
        detriments.extend(rule["detriments"])
        ripple_notes.append("Crude volatility directly bifurcates upstream producers from downstream margin-takers.")

    if "defense" in text or "order" in text or "contract" in text or "infrastructure" in text or "railway" in text:
        rule = SECTOR_RIPPLE_MAP["Defense / Infrastructure Capex Boost"]
        for b in rule["beneficiaries"]:
            if b not in beneficiaries:
                beneficiaries.append(b)

    # Competitor ripple
    clean_sym = symbol.replace(".NS", "").replace(".BO", "") + ".NS"
    if clean_sym in COMPETITOR_MAP:
        comp_info = COMPETITOR_MAP[clean_sym]
        competitors = comp_info["competitors"]
        if event_type == "Contract / Order Win":
            competitor_implication = f"Major contract capture by {clean_sym} locks in capacity and shuts out peers ({', '.join(competitors[:2])}) from this tender pool."
        elif event_type == "Regulatory & Legal Action":
            competitor_implication = f"Compliance scrutiny or restrictions on {clean_sym} create near-term market share migration opportunities for rivals ({', '.join(competitors[:2])})."
        elif event_type == "Corporate Results / Earnings":
            competitor_implication = f"Operating margins and realization trends at {clean_sym} serve as an earnings bellwether for {', '.join(competitors[:2])}."

    if not ripple_notes:
        ripple_notes.append(f"Direct business impact concentrated in {sector} ecosystem; vendors and tier-2 suppliers track execution pace.")

    return {
        "beneficiaries": beneficiaries[:3],
        "detriments": detriments[:3],
        "competitor_implication": competitor_implication,
        "ripple_summary": " ".join(ripple_notes)
    }
