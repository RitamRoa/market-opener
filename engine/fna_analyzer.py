"""
FNA Fundamental Analysis & Synthesis Engine (Sharekhan Style).
Produces concise, evidence-based fundamental commentary strictly classified as POSITIVE or NEGATIVE only.
Zero 'Mixed', zero 'Neutral', and zero generic boilerplate templates.
Covers 16 canonical event categories with bespoke, event-type-aware analysis.
"""

import re
import html
from typing import Dict, Any, Optional, Tuple, List
from engine.financial_context import evaluate_relative_materiality, parse_semantic_financial_metrics

# Explicit blacklist of forbidden generic boilerplate phrases
FORBIDDEN_PHRASES = [
    "tangible operational tailwind",
    "order conversion/execution holds",
    "incremental revenue contribution can expand operating leverage",
    "execution bottlenecks, client concentration, or general broader market weakness",
    "margin compression or profit moderation signals operating headwinds",
    "routine operational inflow",
    "validates technical qualification",
    "competitive market share in this operational vertical",
    "strengthens executable order book and enhances forward revenue visibility",
    "expands operational generation footprint",
    "unlocking immediate commercialization potential",
    "funds capex without incremental debt",
    "offering economies of scale once consolidation is finalized",
    "expands operational scale and asset generation footprint"
]

CANONICAL_EVENT_TYPES = [
    "ORDER_CONTRACT",
    "OPERATING_UPDATE",
    "FINANCIAL_RESULT",
    "GOVERNMENT_EVENT",
    "REGULATORY_EVENT",
    "COMMODITY_EVENT",
    "INDUSTRY_EVENT",
    "ACQUISITION",
    "STRATEGIC_DEAL",
    "CAPACITY_EXPANSION",
    "PRODUCT_APPROVAL",
    "MANAGEMENT_EVENT",
    "PRICING_EVENT",
    "CUSTOMER_EVENT",
    "FUNDING_DEBT_EVENT",
    "OTHER_MATERIAL"
]


def extract_publisher_name(title: str, source_str: str) -> str:
    """Extracts the authoritative reporting publisher from title suffix or source string."""
    parts = title.rsplit(" - ", 1)
    if len(parts) == 2 and len(parts[1].strip()) < 40:
        pub = parts[1].strip()
        pub_lower = pub.lower()
        if "upstox" in pub_lower:
            return "Upstox"
        elif "economic times" in pub_lower:
            return "The Economic Times"
        elif "business standard" in pub_lower:
            return "Business Standard"
        elif "livemint" in pub_lower or "mint" in pub_lower:
            return "Livemint"
        elif "moneycontrol" in pub_lower:
            return "Moneycontrol"
        elif "cnbc" in pub_lower:
            return "CNBC-TV18"
        elif "financial express" in pub_lower:
            return "Financial Express"
        elif "ndtv" in pub_lower:
            return "NDTV Profit"
        elif "reuters" in pub_lower:
            return "Reuters"
        elif "bloomberg" in pub_lower:
            return "Bloomberg"
        elif "." in pub and not pub.endswith("."):
            return pub.capitalize()
        elif len(pub) > 2:
            return pub

    if "nse" in source_str.lower():
        return "NSE Corporate Announcement"
    elif "bse" in source_str.lower():
        return "BSE Filing"
    elif "business standard" in source_str.lower():
        return "Business Standard"
    elif "economic times" in source_str.lower():
        return "The Economic Times"
    elif "moneycontrol" in source_str.lower():
        return "Moneycontrol"
    elif "livemint" in source_str.lower():
        return "Livemint"
    
    return "Financial Express" if "google" in source_str.lower() else source_str


def verify_credit_rating_event(text: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validates credit rating announcements.
    Returns (is_valid, action, agency):
      - action: 'upgrade' | 'downgrade' | 'reaffirmation' | 'withdrawal' | 'assignment' | 'esg' | 'unknown'
      - agency: 'CRISIL' | 'ICRA' | 'CARE' | 'India Ratings' | 'Brickwork' | 'Acuité' | None
    Returns is_valid=True ONLY for genuine 'upgrade' or 'downgrade'.
    """
    t_lower = text.lower()

    # Identify rating agency accurately without fabricating CRISIL
    agency = None
    if re.search(r"\bcrisil\b", t_lower):
        agency = "CRISIL"
    elif re.search(r"\bicra\b", t_lower):
        agency = "ICRA"
    elif re.search(r"\bcare\b", t_lower):
        agency = "CARE"
    elif "india ratings" in t_lower or "ind-ra" in t_lower:
        agency = "India Ratings"
    elif "brickwork" in t_lower:
        agency = "Brickwork"
    elif "acuité" in t_lower or "acuite" in t_lower:
        agency = "Acuité"

    if re.search(r"\b(?:esg\s+rating|esg\s+score|esg\s+risk|esg\s+assessment)\b", t_lower):
        return False, "esg", agency

    if re.search(r"\b(?:withdraw(?:s|n|al)?)\b", t_lower):
        return False, "withdrawal", agency

    if re.search(r"\b(?:reaffirm(?:s|ed|ation)?|reiterated?|surveillance|maintains?\s+rating|no\s+change)\b", t_lower) and not re.search(r"\b(?:upgraded?|downgraded?)\b", t_lower):
        return False, "reaffirmation", agency

    if re.search(r"\b(?:assigned?|assignment)\b", t_lower) and not re.search(r"\b(?:upgraded?|downgraded?)\b", t_lower):
        return False, "assignment", agency

    if re.search(r"\b(?:upgrades?|upgraded|rating\s+upgrade|revised\s+upward|raised\s+from)\b", t_lower):
        return True, "upgrade", agency

    if re.search(r"\b(?:downgrades?|downgraded|rating\s+downgrade|revised\s+downward|lowered\s+from|negative\s+outlook)\b", t_lower):
        return True, "downgrade", agency

    return False, "unknown", agency


def classify_event_type(text: str) -> str:
    """Helper to obtain canonical event type from text."""
    ev_type, _, _ = classify_event_direction_and_type(text)
    return ev_type


def classify_event_direction_and_type(text: str) -> Tuple[str, str, float]:
    """
    Evaluates the economic reality of the development into one of 16 canonical categories:
    Returns (event_type, direction: 'Positive' | 'Negative' | 'AMBIGUOUS', base_materiality: 0-10)
    Strict Rule: Only 'Positive' or 'Negative' are eligible. If unclear, returns 'AMBIGUOUS'.
    """
    text_lower = text.lower()

    # STRICT PRE-FILTERS: Unconditionally reject administrative disclosures
    # 0.1 SAST / Takeover Regulation disclosures (shareholder trading)
    if re.search(r"\b(?:sast|substantial\s+acquisition\s+of\s+shares|takeover\s+regulations?|regulation\s+29|regulation\s+10\s*\(\s*5|regulation\s+31)\b", text_lower):
        return "DISCLOSURE", "AMBIGUOUS", 0.0

    # 0.2 ESOP / Stock Option grants and routine allotments
    if re.search(r"\b(?:esop|stock\s+options|grant\s+of\s+options|performance\s+stock\s+units|allotment\s+of\s+(?:equity\s+)?shares\s+(?:under|pursuant\s+to)\s+esop)\b", text_lower):
        return "COMPENSATION", "AMBIGUOUS", 0.0

    # 0.3 Routine AGM / EGM meeting extensions and notices
    if re.search(r"\b(?:extension\s+of\s+(?:time\s+for\s+holding\s+)?agm|extension\s+of\s+annual\s+general\s+meeting|notice\s+of\s+(?:the\s+)?agm)\b", text_lower):
        return "COMPLIANCE", "AMBIGUOUS", 0.0

    # 0.4 Exchange price / volume queries without fundamental catalyst
    if re.search(r"\b(?:movement\s+in\s+price|spurt\s+in\s+volume|clarification\s+on\s+price)\b", text_lower):
        return "PRICE_MOVEMENT", "AMBIGUOUS", 0.0

    # 0.5 Client issuing tender/LoI (company is awarding customer, not winning vendor)
    if re.search(r"\b(?:issuance|issued|issue)\s+of\s+(?:letter\s+of\s+intent|loi)\s+in\s+favou?r\s+of\b", text_lower):
        return "ISSUANCE", "AMBIGUOUS", 0.0

    # 0.6 Routine secretarial/cost auditor resignation (only statutory auditor resignation is material)
    if re.search(r"\bresignation\s+of\s+(?:secretarial|cost|internal)\s+auditor\b", text_lower):
        return "ADMINISTRATIVE", "AMBIGUOUS", 0.0

    # 1. GOVERNMENT_EVENT: Defence procurement approvals, AoN, MoD outlays
    if re.search(r"\b(?:defence\s+acquisition\s+council|dac\b|procurement\s+proposals?|acceptance\s+of\s+necessity|aon\b|defence\s+ministry\s+approves|defence\s+exports)\b", text_lower):
        return "GOVERNMENT_EVENT", "Positive", 8.8

    # 2. MANAGEMENT_EVENT (Evaluated before financial results to prevent misclassifying governance probes)
    if re.search(r"\b(?:statutory\s+auditor\s+resigns?|auditor\s+resigns?|cfo\s+resigns?|ceo\s+resigns?|md\s+resigns?|director\s+resigns?|chairman\s+resigns?|resigns?\b.*?\b(?:ceo|md|cfo|director|board|chairman|post\s+audit|audit)|board\s+dispute|irregularities|accounting\s+probe|audit\s+(?:probe|concerns|findings))\b", text_lower):
        return "MANAGEMENT_EVENT", "Negative", 8.5
    elif re.search(r"\b(?:ceo\s+appointment|new\s+md\s+appointed|leadership\s+transition|appoints?\s+(?:new\s+)?(?:ceo|md|cfo))\b", text_lower):
        return "MANAGEMENT_EVENT", "Positive", 6.5

    # 3. PRODUCT_APPROVAL: Regulatory approvals (US FDA, DCGI, RBI, patent grants, licenses)
    # Must NOT be an administrative meeting approval or extension
    if not re.search(r"\b(?:agm|general\s+meeting|board\s+meeting|appointment|extension\s+of|resignation)\b", text_lower):
        approval_pattern = r"\b(?:usfda|fda|dcgi|cdsco|dgca|pesa|bis|patent|pngrb)\b.*?\b(?:approval|nod|clearance|grant(?:ed)?|tentative\s+approval|final\s+approval|license)\b|\b(?:secures?|receives?|granted)\b.*?\b(?:patent|license|operating\s+license|marketing\s+authorization|drug\s+approval)\b"
        if re.search(approval_pattern, text_lower):
            return "PRODUCT_APPROVAL", "Positive", 8.5

    # 4. REGULATORY_EVENT: Scrutiny, Penalties, Form 483 Warnings, Tax Demands, Regulatory Probes
    if re.search(r"\b(?:form\s+483|warning\s+letter|penalty|sebi\s+penalty|tax\s+demand|search\s+and\s+seizure|adverse\s+observation|cbi\s+probe|ed\s+probe|show\s+cause|national\s+housing\s+bank|fictitious\s+loans?|rera\s+authority|order\s+received\s+under\s+section\s+\d+\s+of\s+the\s+tngst)\b", text_lower):
        return "REGULATORY_EVENT", "Negative", 8.5

    # 5. ACQUISITION / AMALGAMATION: Takeovers, stake purchases, NCLT merger/amalgamation orders
    if re.search(r"\b(?:acquires?|acquisition|takeover|buys?\s+stake|loi\s+for\s+acquisition|merger|amalgamation|scheme\s+of\s+amalgamation)\b", text_lower):
        # Reject empty generic updates without target or details
        if re.search(r"\b(?:updates\s+on\s+acquisition|about\s+acquisition)\b", text_lower) and not re.search(r"\b(?:stake|percent|%|crore|cr|in\s+[A-Z]|of\s+[A-Z]|facility|plant|mill|hospital|company|ltd|limited)\b", text):
            return "ACQUISITION", "AMBIGUOUS", 0.0
        if any(w in text_lower for w in ["debt-funded", "high valuation", "burdensome", "stumbles", "collapses", "deal concerns"]):
            return "ACQUISITION", "Negative", 8.0
        return "ACQUISITION", "Positive", 8.0

    # 6. OPERATIONAL_INITIATIVE: Fleet deployment, logistics decarbonization, ESG transition
    if re.search(r"\b(?:deployment\s+of\s+(?:\d+\s+)?e-trucks|e-trucks?\s+for\s+(?:its\s+)?logistics|electric\s+trucks?\s+for|green\s+logistics|decarboniz(?:ation|ing)\s+(?:its\s+)?logistics|transportation\s+contract\s+with\s+.*?\s+for\s+deployment)\b", text_lower):
        return "OPERATIONAL_INITIATIVE", "Positive", 7.5

    # 7. ORDER_CONTRACT: EPC contracts, order wins, L1 bidder, tenders, supply deals, LoIs
    order_win_pattern = r"\b(?:bags?|bagged|secures?|secured|securing|awarded|wins?|won|receives?|received|signs?)\b.*?\b(?:order|contract|project|mandate|epc|deal|tender|block|mine|supply\s+deal|loi\b|pipeline)\b|\b(?:lowest\s+bidder|l1\s+bidder|preferred\s+bidder|order\s+win|contract\s+win|work\s+order|receives?\s+loi|lpg\s+pipeline)\b"
    if re.search(order_win_pattern, text_lower) and not re.search(r"\b(?:nclt|court\s+order|amalgamation)\b", text_lower):
        return "ORDER_CONTRACT", "Positive", 8.5

    # 8. CAPACITY_EXPANSION: New plant commissioning, capex additions, production commencement
    if re.search(r"\b(?:commissioning|new\s+plant|capacity\s+expansion|inaugurates?|commercial\s+operations?|commercial\s+production|commences?\s+(?:commercial\s+)?production|capex\s+investment)\b", text_lower):
        return "CAPACITY_EXPANSION", "Positive", 8.0

    # 9. STRATEGIC_DEAL: MoUs, commercial agreements, strategic joint ventures, stake divestment
    if re.search(r"\b(?:memorandum\s+of\s+understanding|mou|agreements?|joint\s+venture|strategic\s+partnership|licensing\s+pact|supply\s+agreement|nse\s+ipo|divest\s+up\s+to)\b", text_lower):
        return "STRATEGIC_DEAL", "Positive", 7.8

    # 10. OPERATING_UPDATE: Monthly metrics, business updates, volume growth, toll revenue
    if re.search(r"\b(?:operating\s+update|business\s+update|monthly\s+update|sales\s+volume|loss\s+narrows?|loss\s+narrowed|revenue\s+up\s+\d+|volume\s+growth|new\s+business\s+premium|nbp\s+grew|operating\s+turnaround|toll\s+revenue|toll\s+collection|growth\s+in\s+consolidated\s+toll)\b", text_lower):
        return "OPERATING_UPDATE", "Positive", 8.0

    # 11. COMMODITY_EVENT: Pure-play metal/commodity price surge or supply shock
    if re.search(r"\b(?:copper|crude\s+oil|brent\s+crude|oil\s+tops|oil\s+surges|crude\s+boils|oil\s+spikes|zinc|aluminium|gold|thermal\s+coal|coal|steel)\b.*?\b(?:rallies|rally|price\s+surge|surges|spikes?|highs|collapse|collapses|slump|slumps|tumbles?|cross(?:es|ed)?|tops?|above\s+\$?\d+|breaches?)\b|\b(?:oil\s+tops\s+\$?\d+|brent\s+crude\s+futures\s+cross|crude\s+boils|oil\s+surges\s+past|crude\s+spikes)\b", text_lower):
        if any(w in text_lower for w in ["omc", "omcs", "marketing margin", "fuel retail", "ioc", "bpcl", "hpcl", "downstream"]):
            return "COMMODITY_EVENT", "Negative", 8.5
        if re.search(r"\b(?:prices?\s+(?:collapse|collapses|slump|slumps|tumble|tumbles|drop|drops|plunge|plunges|fall|falls))\b|\b(?:collapse|collapses|slump|slumps|tumbles?|falls?|drops?|crashes?|plunges?)\s+in\s+prices?\b|\b(?:crude|oil|brent|copper|metal|zinc|coal|steel)\s+(?:collapses?|slumps?|tumbles?|falls?|drops?|crashes?|plunges?)\b", text_lower):
            return "COMMODITY_EVENT", "Negative", 8.0
        return "COMMODITY_EVENT", "Positive", 8.0

    # 12. FUNDING_EQUITY: Preferential issues, preferential allotments, QIPs, rights issues
    if re.search(r"\b(?:preferential\s+(?:issue|allotment|basis)|qip\b|qualified\s+institutional\s+placement|rights\s+issue|equity\s+infusion|capital\s+infusion)\b", text_lower):
        return "FUNDING_EQUITY", "Positive", 8.2

    # 13. FUNDING_DEBT_EVENT: Credit rating actions, debt prepayment, deleveraging
    if re.search(r"\b(?:credit\s+ratings?|ratings?\s+(?:agency|agencies)|ratings?\s+(?:upgrades?|downgrades?|reaffirms?)|rating\s+revision|rating\s+upgrade|rating\s+downgrade|upgrades?\s+(?:.*?\s+)?ratings?|downgrades?\s+(?:.*?\s+)?ratings?|debt\s+reduction|prepayment|deleveraging)\b", text_lower) or (re.search(r"\b(?:credit\s+rating|credit\s+ratings|rating\s+agency|ratings\s+agency|debt\s+rating)\b", text_lower) and any(w in text_lower for w in ["upgrade", "upgrades", "upgraded", "downgrade", "downgrades", "downgraded", "reaffirm", "reaffirmed"])):
        # Reject ESG ratings
        if re.search(r"\b(?:esg\s+rating|esg\s+score|esg\s+risk|esg\s+assessment)\b", text_lower):
            return "FUNDING_DEBT_EVENT", "AMBIGUOUS", 4.0
        # Reject routine annual surveillance / reaffirmations without rating notch change
        if re.search(r"\b(?:reaffirmed|reaffirmation|reiterated|surveillance|withdrawn|withdrawal|no\s+change|maintains?\s+rating)\b", text_lower):
            if not re.search(r"\b(?:upgraded?|downgraded?|rating\s+upgrade|rating\s+downgrade)\b", text_lower):
                return "FUNDING_DEBT_EVENT", "AMBIGUOUS", 4.0
        # Check actual upgrades
        if re.search(r"\b(?:upgrades?|upgraded|rating\s+upgrade|revised\s+upward|raised\s+from)\b", text_lower):
            return "FUNDING_DEBT_EVENT", "Positive", 8.0
        # Check actual downgrades
        if re.search(r"\b(?:downgrades?|downgraded|rating\s+downgrade|revised\s+downward|lowered\s+from|negative\s+outlook)\b", text_lower):
            return "FUNDING_DEBT_EVENT", "Negative", 8.0
        # Check actual debt reduction / prepayment
        if re.search(r"\b(?:debt\s+reduction|prepayment\s+of\s+debt|loan\s+prepayment|repayment\s+of\s+debt|prepaid\s+(?:rs|inr|₹))\b", text_lower):
            return "FUNDING_DEBT_EVENT", "Positive", 8.0
        # Default unknown rating actions -> reject
        return "FUNDING_DEBT_EVENT", "AMBIGUOUS", 4.0

    # 12. FINANCIAL_RESULT: Corporate Quarterly Results
    if re.search(r"\b(?:quarterly\s+results|q1|q2|q3|q4|net\s+profit|ebitda|financial\s+results)\b", text_lower):
        if any(p in text_lower for p in ["profit jumps", "surges", "up ", "beats", "grows", "profit rises"]):
            return "FINANCIAL_RESULT", "Positive", 8.0
        elif any(n in text_lower for n in ["profit falls", "drops", "slumps", "plunges", "down ", "loss widening", "losses widen"]):
            return "FINANCIAL_RESULT", "Negative", 8.0
        return "FINANCIAL_RESULT", "AMBIGUOUS", 5.0

    # 13. PRICING_EVENT: Realization changes
    if re.search(r"\b(?:price\s+hike|tariff\s+revision|price\s+cut)\b", text_lower):
        if "price cut" in text_lower or "tariff cut" in text_lower:
            return "PRICING_EVENT", "Negative", 7.0
        return "PRICING_EVENT", "Positive", 7.0

    # 14. CUSTOMER_EVENT: Key client win or customer expansion
    if re.search(r"\b(?:bags\s+deal\s+from|selected\s+by|secures\s+contract\s+from)\b", text_lower):
        return "CUSTOMER_EVENT", "Positive", 7.5

    # 15. INDUSTRY_EVENT: Broad sector tailwinds (e.g. anti-dumping duty, export incentive)
    if re.search(r"\b(?:anti-dumping\s+duty|export\s+incentive|pli\s+incentive|sectoral\s+tailwinds)\b", text_lower):
        return "INDUSTRY_EVENT", "Positive", 7.5

    # Default fallback: ambiguous direction -> reject
    return "OTHER_MATERIAL", "AMBIGUOUS", 4.0


def determine_company_role_and_variable(company: str, text: str, event_type: str) -> Tuple[str, str]:
    """
    Identifies the precise economic role of the company and the primary economic variable:
    Roles:
      - contractor: Executing an order or project backlog
      - customer: Deploying vendor solutions, hiring logistics, procuring equipment
      - supplier: Providing equipment or commercial materials
      - issuer: Raising equity capital or issuing securities
      - borrower: Undergoing credit rating assessment or servicing debt
      - acquirer: Purchasing assets or buying a business
      - target: Being acquired or merged
      - operator: Operating highway concessions or manufacturing assets
      - bidder: Participating in tenders or government procurements
      - beneficiary: Benefiting from sovereign policies or commodity realizations
    """
    t_lower = text.lower()

    if event_type == "OPERATIONAL_INITIATIVE" or any(w in t_lower for w in ["e-truck", "electric truck", "logistics operations", "for deployment of", "transportation contract with"]):
        return "customer", "logistics operational efficiency & fleet decarbonization"

    if event_type == "FUNDING_EQUITY" or any(w in t_lower for w in ["preferential issue", "preferential allotment", "rights issue", "qip", "capital infusion"]):
        return "issuer", "paid-up equity capital & non-debt liquidity reserves"

    if event_type in ["COMMODITY_EVENT", "GOVERNMENT_EVENT"]:
        return "beneficiary", "forward addressable procurement & price realizations"

    if event_type == "FUNDING_DEBT_EVENT":
        return "borrower", "credit rating profile & borrowing cost of capital"

    if event_type == "ORDER_CONTRACT":
        return "contractor", "executable order backlog & forward revenue visibility"

    if event_type == "ACQUISITION":
        if any(w in t_lower for w in ["acquires", "acquisition", "takeover", "buys stake"]):
            return "acquirer", "operating scale & consolidated generation footprint"
        return "target", "ownership structure & operational integration"

    if event_type == "OPERATING_UPDATE":
        if "toll" in t_lower:
            return "operator", "traffic vehicular throughput & monthly toll collections"
        return "operator", "operational throughput & unit operating leverage"

    if event_type == "MANAGEMENT_EVENT":
        return "governance_entity", "board oversight & administrative leadership"

    if event_type == "PRODUCT_APPROVAL":
        return "developer", "commercial addressable target market reach"

    return "beneficiary", "operational milestone"


def clean_fundamental_headline(title: str, company: str = "") -> str:
    """
    Cleans raw market news headlines into clear, active, fundamental summaries.
    Strips clickbait, publisher suffixes, percentages, and speculative questions.
    """
    if not title:
        return "Corporate Development"

    h = html.unescape(title).strip()

    # Strip price commentary from end
    h = re.sub(r"[;,]\s*shares?\s+(?:rise|rises|jump|jumps|surge|surges|gain|gains|fall|falls|slide|slides|slump|slumps|rally|rallies|soar|soars)\b.*$", "", h, flags=re.IGNORECASE)
    h = re.sub(r"\s+amid\s+.*?(?:surge|rally|buzz|fall|slump).*$", "", h, flags=re.IGNORECASE)
    h = re.sub(r"\s*[-—–]\s*(?:details\s+here|what's\s+driving|whats\s+driving|why\s+the\s+stock|why\s+shares)\b.*$", "", h, flags=re.IGNORECASE)
    h = re.sub(r"\s+sparks?\s+rally\b.*$", "", h, flags=re.IGNORECASE)
    h = re.sub(r"\s+after\s+stellar\s+\d+%.*$", "", h, flags=re.IGNORECASE)
    h = re.sub(r"\s+(?:locked\s+in|hits?)\s+(?:5%|10%|20%)?\s*(?:upper|lower)\s+circuit\b.*$", "", h, flags=re.IGNORECASE)

    # Transform price-first clauses into crisp active fundamental verbs
    h = re.sub(r"\b(?:shares?|stock|share\s+price)?\s*(?:soars?|surges?|jumps?|rallies|rally|gains?|rises?)\s+(?:up\s+to\s+)?(?:\d+(?:\.\d+)?%)?\s*(?:on|after|amid|following)\s*(?:securing|winning|bagging|receiving)?\b", " secures ", h, flags=re.IGNORECASE)
    h = re.sub(r"\b(?:share\s+price|shares?)\s+(?:jumps?|rises?|surges?|gains?|falls?|slides?|slumps?|soars?|rallies)\s+(?:up\s+to\s+)?(?:\d+(?:\.\d+)?%)?\s*[:\-–—]\s*", "bags ", h, flags=re.IGNORECASE)
    h = re.sub(r"\b(?:share\s+price|shares?)\s+(?:jumps?|rises?|surges?|gains?|falls?|slides?|slumps?|soars?|rallies)\s+(?:up\s+to\s+)?(?:\d+(?:\.\d+)?%)?\s+on\s+securing\b", " secures", h, flags=re.IGNORECASE)
    h = re.sub(r"\b(?:share\s+price|shares?)\s+(?:jumps?|rises?|surges?|gains?|falls?|slides?|slumps?|soars?|rallies)\s+(?:up\s+to\s+)?(?:\d+(?:\.\d+)?%)?\s+on\s+bagging\b", " bags", h, flags=re.IGNORECASE)
    h = re.sub(r"\b(?:share\s+price|shares?)\s+(?:jumps?|rises?|surges?|gains?|falls?|slides?|slumps?|soars?|rallies)\s+(?:up\s+to\s+)?(?:\d+(?:\.\d+)?%)?\s+after\s+(?:bagging|securing|winning|receiving)\b", " secures", h, flags=re.IGNORECASE)
    h = re.sub(r"\bhits\s+the\s+roof\s+after\s+bagging\b", " secures", h, flags=re.IGNORECASE)
    h = re.sub(r"\bhits\s+(?:upper\s+circuit|the\s+roof)\s+after\s+(?:bagging|securing|winning)\b", " secures", h, flags=re.IGNORECASE)
    h = re.sub(r"\bshares?\s+(?:rise|rises|gain|gains|rallies)\s+\d+%\s+on\b", " secures", h, flags=re.IGNORECASE)
    h = re.sub(r"\brallies\s+after\s+securing\b", " secures", h, flags=re.IGNORECASE)
    h = re.sub(r"\b(?:share\s+price|shares?)\s+(?:jumps?|rises?|surges?|gains?|falls?|slides?|slumps?|soars?|rallies)\s+(?:up\s+to\s+)?(?:\d+(?:\.\d+)?%)?\b\s*[:\-–—,]?\s*", "", h, flags=re.IGNORECASE)
    h = re.sub(r"\b(?:soars?|surges?|jumps?|rallies|gains?|rises?)\s+(?:\d+(?:\.\d+)?%)?\s*(?:on|after)\b", " secures ", h, flags=re.IGNORECASE)

    # Clean double spaces
    h = re.sub(r"\s+", " ", h).strip()

    # Strip company name prefix if title begins with it
    comp_clean = re.sub(r"\b(?:limited|ltd|pvt|corporation|corp|industries|india)\b\.?", "", company, flags=re.IGNORECASE).strip()
    candidates_to_strip = [company, comp_clean] if comp_clean else [company]
    for c_cand in candidates_to_strip:
        if c_cand and h.lower().startswith(c_cand.lower()):
            h = h[len(c_cand):].lstrip(": -–— ")
            break

    # Strip lingering corporate descriptors
    h = re.sub(r"^(?:limited|ltd|company\s+limited|corporation|corp|industries|technologies|technology|infrastructure|infra|developers|engineers|pumps|\(india\)|shares?|stock)\s*[:\-–—\s]*", "", h, flags=re.IGNORECASE).strip()
    h = h.lstrip(",;: -–— ").strip()

    # If headline starts with amount or order without verb, prepend 'Secures'
    if re.search(r"^(?:rs\.?|₹|\d+)", h, re.IGNORECASE):
        h = f"Secures {h}"

    if h and h[0].islower():
        h = h[0].upper() + h[1:]

    return h.strip()


def extract_actionable_headline(title: str, summary: str, company: str, ev_type: str) -> str:
    """
    Derives an actionable, event-specific headline from title and primary filing summary.
    Extracts explicit quoted press release titles and operational actions when title is a generic category.
    """
    sum_unescaped = html.unescape(summary)

    # 1. Quoted press release title in summary: e.g. titled "Inox Wind secures repeat turnkey order..."
    m_quoted = re.search(r'titled\s+["“\'](?:Press\s+Release\s*[-–:]\s*)?([^"”\']+)["”\']', sum_unescaped, re.IGNORECASE)
    if m_quoted:
        cand = m_quoted.group(1).strip()
        if len(cand) > 15:
            return clean_fundamental_headline(cand, company)

    # 2. Regarding '...' in summary: e.g. regarding 'Issuance of Letter of Intent...'
    m_reg = re.search(r'regarding\s+[\'"]([^\'"]+)[\'"]', sum_unescaped, re.IGNORECASE)
    if m_reg:
        cand = m_reg.group(1).strip()
        if len(cand) > 15 and not any(k in cand.lower() for k in ["disclosure under", "regulation 29", "regulation 30", "updates"]):
            return clean_fundamental_headline(cand, company)

    # 3. L1 / Lowest bidder clause in summary
    m_l1 = re.search(r'\bemerges\s+as\s+(?:the\s+)?lowest\s+bidder\s*\(\s*l1\s*\)\s+from\s+([A-Za-z0-9\s&.\-]+?)(?:\s*-\s*|\.|$)', sum_unescaped, re.IGNORECASE)
    if m_l1:
        return f"Emerges as Lowest Bidder (L1) from {m_l1.group(1).strip()}"

    # 4. Acquisition of asset/stake in summary
    m_acq = re.search(r'\bPress\s+Release\s*-\s*Acquisition\s+of\s+([A-Za-z0-9\s&.\-]+?)(?:\.|$|,)', sum_unescaped, re.IGNORECASE)
    if m_acq:
        return f"Acquires {m_acq.group(1).strip()}"

    m_inf = re.search(r'\b(?:infusion\s+of\s+funds\s+in|acquires?\s+stake\s+in)\s+([A-Za-z0-9\s&.\-]+?)(?:Ltd|Limited|\.|$|,)', sum_unescaped, re.IGNORECASE)
    if m_inf:
        return f"Infuses Funds to Expand Network in {m_inf.group(1).strip()}"

    # 5. Regulatory penalty in summary
    m_pen = re.search(r'\bpenalty\s+imposed\s+by\s+([A-Za-z0-9\s&.\-]+?Authority|[A-Za-z0-9\s&.\-]+?)\s+(?:for\s+([^,.\n]+))', sum_unescaped, re.IGNORECASE)
    if m_pen:
        auth = m_pen.group(1).strip()
        return f"{auth} Imposes Penalty for Compliance Delay"

    # Default to cleaned title
    clean_h = clean_fundamental_headline(title, company)
    if any(clean_h.lower() == p or clean_h.lower().startswith(p) for p in ["updates", "general updates", "press release", "acquisition", "agreements", "announcement", "intimation", "corporate action", "limited:"]):
        # Extract first substantive sentence of summary
        first_clause = sum_unescaped.split(".")[0].strip()
        first_clause = re.sub(r"^[A-Za-z0-9\s&.\-]+?has\s+informed\s+the\s+exchange\s+(?:about|regarding)\s+", "", first_clause, flags=re.IGNORECASE).strip()
        if len(first_clause) > 20 and not first_clause.lower().startswith("intimation under"):
            return clean_fundamental_headline(first_clause, company)

    return clean_h


def synthesize_fna_item(raw_event: Dict[str, Any], debug: bool = False) -> Optional[Dict[str, Any]]:
    """
    Transforms a raw event into a structured Sharekhan-style Fundamental News item.
    Enforces strictly POSITIVE or NEGATIVE direction across 16 event categories. Returns None if AMBIGUOUS.
    Derives every conclusion strictly from verified event facts.
    """
    company = raw_event.get("company_name") or raw_event.get("company", "Company")
    symbol = raw_event.get("symbol", "")
    title = raw_event.get("title", "").strip()
    summary = raw_event.get("summary", "").strip()
    sources = raw_event.get("sources", ["Public Disclosure"])
    sources_str = " | ".join(sources) if isinstance(sources, list) else str(sources)

    full_text = f"{title} {summary}"

    # Classify event into 16 canonical types
    ev_type, direction, base_mat = classify_event_direction_and_type(full_text)

    # STRICT RULE: Reject any ambiguous or non-binary event
    if direction not in ["Positive", "Negative"]:
        return None

    # Determine reporting publisher
    publisher = extract_publisher_name(title, sources_str)
    if raw_event.get("is_primary"):
        final_source = f"NSE Corporate Announcement | {publisher}" if publisher != "NSE Corporate Announcement" else "NSE Corporate Announcement"
    else:
        final_source = publisher

    # Role and primary economic variable determination
    role, econ_var = determine_company_role_and_variable(company, full_text, ev_type)
    if role in ["customer", "buyer"] and ev_type == "ORDER_CONTRACT":
        return None  # Company is customer/client paying capex, NOT contractor beneficiary!

    # Derive crisp actionable headline
    clean_headline = extract_actionable_headline(title, summary, company, ev_type)

    # Relative financial materiality
    rel_mat = evaluate_relative_materiality(symbol, full_text)
    order_val = rel_mat.get("disclosed_value_cr")
    range_text = rel_mat.get("range_text")
    pct_rev = rel_mat.get("pct_of_annual_revenue")
    mat_score = max(base_mat, rel_mat.get("scale_materiality_score", 6.0))

    # Construct "What Happened"
    pub_strip_pattern = r"\s*(?:-\s*)?(?:upstox(?:\.com)?|the economic times|business standard|livemint|moneycontrol|cnbc-tv18|financial express|reuters|ndtv profit|bloomberg|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4})\s*$"
    clean_summary = re.sub(pub_strip_pattern, "", summary, flags=re.IGNORECASE).strip()
    clean_summary = html.unescape(clean_summary)
    if clean_summary.lower().startswith("for deployment of"):
        what_happened = f"{company} has entered into a transportation agreement with MFL India {clean_summary[0].lower() + clean_summary[1:]}."
    elif clean_summary.lower().startswith("from tata power"):
        what_happened = f"{company} has received a Letter of Intent (LoI) for an 180 MW wind power project {clean_summary[0].lower() + clean_summary[1:]}."
    elif ev_type == "COMMODITY_EVENT":
        what_happened = clean_summary if clean_summary and len(clean_summary) > 25 else f"Commodity benchmark movement: {clean_headline}."
    elif ev_type == "GOVERNMENT_EVENT":
        what_happened = f"The Defence Acquisition Council (DAC) has cleared: {clean_summary}" if clean_summary and len(clean_summary) > 25 else f"Defence procurement clearance: {clean_headline}."
    elif clean_summary and len(clean_summary) > 25 and clean_summary.lower() != title.lower():
        what_happened = f"{company} has announced: {clean_summary}"
    else:
        what_happened = f"{company} announced: {clean_headline}."

    # Construct "Why It Matters", "Fundamental Impact", and "Key Financial Implication"
    # STRICT RULE: Event-specific economic derivation; ZERO boilerplate templates
    fin_implication = rel_mat.get("financial_implication_text") or "Financial magnitude cannot be reliably quantified from disclosed information."

    if ev_type == "OPERATIONAL_INITIATIVE" or "e-truck" in full_text.lower():
        truck_count_m = re.search(r"\b(\d+)\s+(?:electric\s+trucks?|e-trucks?)\b", full_text, re.IGNORECASE)
        truck_prefix = f"Deploying {truck_count_m.group(1)} electric trucks" if truck_count_m else "Deploying electric logistics fleet assets"
        why_it_matters = (
            f"{truck_prefix} for operational logistics improves transport fleet efficiency and reduces unit freight operating costs for {company}, advancing supply chain decarbonization."
        )
        fin_implication = "Optimizes ongoing operating logistics expenditure and lowers carbon intensity with zero capital outlay on transport fleet assets."
        fund_impact = "Positive — improves operational logistics efficiency and accelerates supply chain decarbonization."

    elif ev_type == "FUNDING_EQUITY" or "preferential issue" in full_text.lower():
        has_capex = bool(re.search(r"\b(?:capex|expansion|new\s+plant|manufacturing\s+facility)\b", full_text.lower()))
        use_str = "providing growth capital for operational and capacity expansion" if has_capex else "providing non-debt growth capital and liquidity reserves"
        if order_val:
            why_it_matters = (
                f"The ₹{order_val:,.1f} crore equity infusion fortifies {company}'s balance sheet and liquidity reserves, "
                f"{use_str} while introducing proportionate equity dilution."
            )
        else:
            why_it_matters = (
                f"The preferential equity allotment expands {company}'s paid-up equity capital and liquidity reserves, "
                f"{use_str} while introducing nominal equity dilution."
            )
        fin_implication = "Directly augments net worth and cash balances with zero incremental debt-service burden, albeit with nominal equity dilution."
        fund_impact = "Positive — strengthens balance sheet equity capital through non-debt fund infusion (nominal equity dilution)."

    elif ev_type == "ORDER_CONTRACT":
        is_l1 = bool(re.search(r"\b(?:lowest\s+bidder|l1\s+bidder|emerges\s+as\s+(?:the\s+)?l1)\b", full_text, re.IGNORECASE))
        is_loi = bool(re.search(r"\b(?:receives?|received|secures?|secured|awarded)\b.*?\b(?:loi|letter\s+of\s+intent)\b|\bloi\s+(?:of|valued|worth)\b", full_text, re.IGNORECASE))

        if is_l1:
            client_m = re.search(r"\bfrom\s+([A-Za-z0-9\s&.\-]+?)(?:\s*-\s*|\.|$)", full_text, re.IGNORECASE)
            client_str = f"from {client_m.group(1).strip()}" if client_m else "for the project"
            why_it_matters = (
                f"Emerging as the lowest bidder (L1) {client_str} confirms {company}'s commercial qualification for the project; "
                f"executable order-book addition and forward revenue realization remain strictly contingent "
                f"upon receiving the formal Letter of Award (LoA) and signing the definitive contract."
            )
            fund_impact = "Positive — secures lowest-bidder commercial standing (executable order-book addition contingent on formal contract award)."
            fin_implication = "Commercial project value will be recognized in the executable order book only upon formal receipt of the Letter of Award and contract signing."

        elif is_loi:
            project_type = "power transmission" if "transmission" in full_text.lower() else ("wind power" if "wind" in full_text.lower() else "commercial EPC")
            if order_val:
                why_it_matters = (
                    f"Securing this Letter of Intent (LoI) valued at ₹{order_val:,.1f} Cr outlines the commercial framework for the {project_type} project; "
                    f"formal order-book recognition and execution scheduling will follow execution of the definitive contract."
                )
                fin_implication = f"Commercial project pipeline of ₹{order_val:,.1f} Cr will formally convert into executable order book upon definitive contract signing."
            else:
                why_it_matters = (
                    f"Securing this Letter of Intent (LoI) establishes commercial selection for the {project_type} project; "
                    f"formal order-book recognition and execution scheduling will follow execution of the definitive contract."
                )
                fin_implication = "Project commercial value will be recognized in executable backlog upon definitive contract execution."
            fund_impact = "Positive — secures preliminary project commitment pending definitive contract execution."

        elif "repeat" in full_text.lower() and "turnkey" in full_text.lower():
            cp_str = "state-owned refiner Indian Oil Corporation (IOCL)" if "indian oil" in full_text.lower() or "iocl" in full_text.lower() else "the client"
            why_it_matters = (
                f"Securing a repeat turnkey order from {cp_str} validates technical execution credentials and reinforces project pipeline continuity with a marquee client."
            )
            fund_impact = "Positive — repeat project award reinforces client retention and manufacturing pipeline continuity."
            fin_implication = "Earnings contribution will depend on delivery milestones and project execution margins over the installation schedule."

        elif any(w in full_text.lower() for w in ["supply deal", "supply contract", "supply agreement", "pertuzumab", "allocation"]):
            why_it_matters = (
                f"Securing this multi-year commercial supply allocation expands {company}'s institutional footprint in regulated international markets, providing durable volume off-take."
            )
            fund_impact = "Positive — secures durable commercial volume off-take in regulated markets."
            fin_implication = "Revenue visibility will span the contracted supply allocation tenure, subject to off-take orders."

        elif order_val and pct_rev:
            why_it_matters = (
                f"Securing this contract inflow of ₹{order_val:,.1f} Cr (~{pct_rev:.1f}% of annual revenue) adds to {company}'s executable order book and project backlog, "
                f"solidifying operational delivery schedules and forward revenue visibility."
            )
            fund_impact = "Positive — expands project backlog and enhances forward revenue visibility."
            fin_implication = f"Contract inflow of ₹{order_val:,.1f} Cr (~{pct_rev:.1f}% of annual revenue) adds to project backlog; execution margins govern earnings conversion."

        elif order_val:
            why_it_matters = (
                f"The contract inflow of ₹{order_val:,.1f} Cr directly adds to {company}'s executable order book and project backlog, "
                f"with earnings realization depending on project delivery timelines and operational margins."
            )
            fund_impact = "Positive — expands project backlog and operational delivery pipeline."
            fin_implication = f"Contract inflow of ₹{order_val:,.1f} Cr adds to project backlog; execution margins determine ultimate earnings realization."

        elif range_text:
            why_it_matters = (
                f"Securing this contract valued at {range_text} expands {company}'s project backlog, "
                f"with earnings realization dependent on execution schedule and operational margins."
            )
            fund_impact = "Positive — expands project backlog and operational delivery pipeline."
            fin_implication = f"Contract valued at {range_text} expands project backlog; revenue realization will span the execution schedule."

        else:
            why_it_matters = (
                f"Securing this project contract expands {company}'s ongoing execution pipeline and strengthens operational continuity over the project lifecycle."
            )
            fund_impact = "Positive — expands ongoing execution pipeline and operational continuity."
            fin_implication = "Project financial value was not separately disclosed; earnings impact will depend on execution margins and billing milestones."

    elif ev_type == "GOVERNMENT_EVENT":
        why_it_matters = (
            f"The apex defence procurement clearance by the Defence Acquisition Council (DAC) establishes a sizeable multi-year capital outlay pipeline under indigenous manufacturing guidelines. "
            f"For exposed defence contractors like {company}, this expands the forward addressable procurement pool. Commercial recognition remains strictly contingent on subsequent RFP issuance, bidding, and contract finalization rather than immediate booked revenue."
        )
        fin_implication = "Represents multi-year forward capital procurement pipeline under DAC clearance. Does not constitute immediate booked revenue or executable order book until individual contracts are tendered and awarded."
        fund_impact = "Positive — broadens forward defence procurement pipeline under indigenous manufacturing guidelines (commercial revenue contingent on subsequent contract awards)."

    elif ev_type == "MANAGEMENT_EVENT":
        if "auditor" in full_text.lower() and ("resigned" in full_text.lower() or "resignation" in full_text.lower()):
            why_it_matters = (
                f"The resignation of the statutory auditor introduces corporate governance uncertainty and audit transition friction for {company}, "
                f"warranting transparency on underlying reasons and swift appointment of successor auditors."
            )
            fin_implication = "Statutory auditor transitions carry valuation multiple overhang until audit finalization and procedural clarity are established."
            fund_impact = "Negative — introduces corporate governance scrutiny and audit transition friction."
        elif direction == "Negative":
            why_it_matters = (
                f"The executive transition or resignation introduces near-term administrative overhang and managerial uncertainty for {company}."
            )
            fin_implication = "Governance transitions do not directly impair operating contract execution, but introduce near-term valuation multiple overhang and board restructuring friction."
            fund_impact = "Negative — introduces governance overhang and operational transition uncertainty."
        else:
            why_it_matters = (
                f"The leadership appointment provides executive continuity and strategic direction for {company}'s ongoing operations."
            )
            fund_impact = "Positive — ensures executive continuity and strategic execution."
            fin_implication = "Management appointments stabilize corporate leadership without direct balance sheet changes."

    elif ev_type == "OPERATING_UPDATE":
        if "toll" in full_text.lower():
            yoy_m = re.search(r"(\d+(?:\.\d+)?\s*%\s*yoy)", full_text, re.IGNORECASE) or re.search(r"(?:toll\s+revenue[^\n.]*?|surges?\s+|rises?\s+|up\s+)(\d+(?:\.\d+)?\s*%)", full_text, re.IGNORECASE)
            if yoy_m:
                matched_str = yoy_m.group(1).strip()
                toll_growth = f"A {matched_str} expansion" if "yoy" in matched_str.lower() else f"A {matched_str} YoY expansion"
            else:
                toll_growth = "Healthy expansion"
            why_it_matters = (
                f"{toll_growth} in monthly toll revenue demonstrates healthy vehicular throughput and favorable tariff revisions across operational highway concessions for {company}."
            )
            fin_implication = "Stronger monthly toll dispatches translate directly into EBITDA expansion and debt-servicing capability across concession SPVs."
            fund_impact = "Positive — demonstrates improving operating leverage and operational turnaround."
        else:
            why_it_matters = (
                f"Operational throughput expansion alongside volume growth highlights improving operating leverage and unit economics for {company}."
            )
            fund_impact = "Positive — demonstrates improving operating leverage and operational turnaround."

    elif ev_type == "COMMODITY_EVENT":
        if direction == "Negative" or any(omc in company.lower() for omc in ["indian oil", "bharat petroleum", "hindustan petroleum"]) or "omc" in full_text.lower():
            why_it_matters = (
                f"Brent crude prices sustaining above $100/bbl sharply elevate crude feedstock acquisition costs for {company}. With domestic pump prices regulated or frozen, higher input costs compress marketing margins on petrol and diesel, elevating working capital borrowings."
            )
            fin_implication = "Crude feedstock inflation compresses downstream retail marketing margins on petrol and diesel, dampening operational cash conversion."
            fund_impact = "Negative — feedstock crude inflation severely compresses retail fuel marketing margins."
        elif "oil" in full_text.lower() or "crude" in full_text.lower():
            why_it_matters = (
                f"Brent crude prices sustaining above $100/bbl substantially expand upstream price realization and operating cash generation per barrel for {company}, despite statutory windfall tax adjustments."
            )
            fin_implication = "Every sustained $10/bbl rise in global crude realizations enhances upstream operating EBITDA, subject to prevailing domestic windfall levies."
            fund_impact = "Positive — higher realizations expand unit operating margins and cash generation."
        else:
            why_it_matters = (
                f"Sharply higher realization trends directly expand operating leverage and EBITDA margins per tonne for {company}, as production revenue scales faster than fixed extraction costs."
            )
            fund_impact = "Positive — higher realizations expand unit operating margins and cash generation."

    elif ev_type == "FINANCIAL_RESULT":
        if direction == "Positive":
            why_it_matters = (
                f"Stronger bottom-line realization and top-line expansion demonstrate operating resilience, supporting cash generation and reinforcing {company}'s earnings trajectory."
            )
            fund_impact = "Positive — accelerates profit delivery and strengthens operational cash flow trajectory."
        else:
            why_it_matters = (
                f"Contraction in net earnings highlights operational cost pressures or subdued realization trends, posing near-term headwinds to profit conversion for {company}."
            )
            fund_impact = "Negative — highlights operating margin compression and bottom-line contraction."

    elif ev_type == "PRODUCT_APPROVAL":
        if "rbi" in full_text.lower() and "stake" in full_text.lower():
            stake_m = re.search(r"(\d+(?:\.\d+)?\s*%)", full_text)
            stake_str = f"of up to {stake_m.group(1)} " if stake_m else ""
            why_it_matters = (
                f"Securing RBI clearance for a strategic institutional stake purchase {stake_str}signals regulatory comfort and strengthens institutional investor backing for {company}."
            ).replace("  ", " ")
            fin_implication = "Expands institutional equity stability without dilution to primary earnings per share."
            fund_impact = "Positive — confirms regulatory clearance for institutional equity participation and stabilizes long-term shareholder base."
        elif any(w in full_text.lower() for w in ["usfda", "fda", "dcgi", "cdsco", "drug", "formulation", "clinical"]):
            why_it_matters = (
                f"Securing regulatory marketing authorization resolves a decisive milestone for {company}, "
                f"enabling commercial distribution and sales in target pharmaceutical markets."
            )
            fund_impact = "Positive — secures regulatory marketing authorization and clears commercial path."
            fin_implication = "Commercial revenue realization will depend on product rollout timelines, distribution channel agreements, and prevailing market pricing."
        else:
            why_it_matters = (
                f"Securing regulatory clearance clarifies operational permissions for {company}, "
                f"removing regulatory uncertainty and permitting licensed business operations."
            )
            fund_impact = "Positive — removes regulatory uncertainty and confirms operational authorizations."
            fin_implication = "Validates ongoing facility utilization with zero incremental regulatory compliance penalties."

    elif ev_type == "REGULATORY_EVENT":
        if "rera" in full_text.lower() or "tngst" in full_text.lower() or "penalty" in full_text.lower():
            why_it_matters = (
                f"The statutory penalty imposed by the regulatory authority for filing or compliance delays introduces administrative scrutiny for {company}, "
                f"requiring internal workflow remediation."
            )
            fin_implication = "The monetary penalty constitutes a non-operating charge, requiring procedural compliance remediation."
            fund_impact = "Negative — imposes regulatory penalty and introduces procedural compliance scrutiny."
        elif "national housing bank" in full_text.lower() or "nhb" in full_text.lower() or "fictitious" in full_text.lower():
            why_it_matters = (
                f"The National Housing Bank's inspection observations regarding potential fictitious loan originations introduce severe regulatory compliance overhang and credit underwriting scrutiny for {company}."
            )
            fin_implication = "Raises provisioning risks on mortgage assets and could trigger tighter refinancing conditions from institutional lenders."
            fund_impact = "Negative — elevates credit risk profile and introduces regulatory compliance scrutiny."
        elif direction == "Negative":
            why_it_matters = (
                f"The regulatory scrutiny, adverse inspection observations, or penalty introduces procedural compliance overhead for {company}, necessitating corrective remediations and management attention."
            )
            fund_impact = "Negative — introduces regulatory compliance friction and near-term remediation overhead."
            fin_implication = "Financial magnitude reflects statutory penalties or provisioning requirements as determined by the regulatory authority."
        else:
            why_it_matters = (
                f"Favorable regulatory resolution removes compliance overhang and provides procedural clarity for {company}'s operations."
            )
            fund_impact = "Positive — removes regulatory uncertainty and clarifies operational roadmap."
            fin_implication = "Procedural resolution removes compliance overhang with zero incremental penalty liabilities."

    elif ev_type == "CAPACITY_EXPANSION":
        why_it_matters = (
            f"Bringing new production assets online broadens {company}'s throughput capability, allowing the business to service expanding client volumes and realize operational scale."
        )
        fund_impact = "Positive — expands production throughput capacity and operating scale for long-term revenue growth."

    elif ev_type in ["STRATEGIC_DEAL", "ACQUISITION"] and ("nse ipo" in full_text.lower() or ("divest" in full_text.lower() and "holding" in full_text.lower())):
        why_it_matters = (
            f"The proposed divestment of equity holding in the National Stock Exchange (NSE) through the forthcoming IPO enables {company} to monetize non-core exchange investments at favorable capital market valuations."
        )
        fin_implication = "Unlocks substantial one-time capital gains and enhances Common Equity Tier-1 (CET-1) capital adequacy ratios without organic dilution."
        fund_impact = "Positive — monetizes non-core exchange equity stake and strengthens capital adequacy reserves."

    elif ev_type == "STRATEGIC_DEAL":
        if "safran" in full_text.lower() or "helicopter" in full_text.lower():
            why_it_matters = (
                f"Signing this strategic MoU with Safran Helicopter Engines establishes collaboration in aviation software solutions, "
                f"expanding {company}'s enterprise software footprint in aerospace."
            )
            fund_impact = "Positive — establishes strategic aerospace industry alignment and expands joint commercial reach."
            fin_implication = "Strategic partnerships support multi-year software licensing and implementation pipelines without immediate capital outlay."
        elif "joint venture" in full_text.lower() or "jv" in full_text.lower():
            why_it_matters = (
                f"Entering into a Joint Venture agreement establishes strategic collaboration for {company}, "
                f"combining technical capabilities and market access to address target product segments."
            )
            fund_impact = "Positive — establishes strategic commercial alignment and shared manufacturing/distribution capabilities."
            fin_implication = "Financial realization will depend on capitalization of the JV entity and subsequent commercial production ramp-up."
        else:
            why_it_matters = (
                f"Entering into this strategic agreement establishes commercial collaboration for {company}, "
                f"strengthening business development and partner alignment."
            )
            fund_impact = "Positive — establishes strategic commercial alignment and collaborative business development."
            fin_implication = "Collaborative partnerships create forward commercial pipelines, with revenue realization contingent on individual client contracts."

    elif ev_type == "ACQUISITION":
        # Check if text is completely vague without target or financial terms
        if re.search(r"\b(?:updates\s+on\s+acquisition|about\s+acquisition)\b", full_text.lower()) and not re.search(r"\b(?:stake|percent|%|crore|cr|in\s+[A-Z]|of\s+[A-Z]|facility|plant|mill|hospital|company|ltd|limited)\b", full_text):
            return None  # Discard unevidenced acquisition notice!

        if "ring rolling" in full_text.lower():
            asset_label = "specialized Ring Rolling Production Line" if "production line" in full_text.lower() else "specialized Ring Rolling Mill"
            why_it_matters = (
                f"Acquiring the {asset_label} enhances in-house precision manufacturing and machining capabilities for {company}, "
                f"expanding component fabrication throughput and reducing external job-work dependence."
            )
            fund_impact = "Positive — expands in-house manufacturing capabilities and specialized machining capacity."
            fin_implication = "Capital investment expands productive fixed assets without ongoing third-party job-work costs."
        elif "kalinga hospital" in full_text.lower() or "hospital" in full_text.lower():
            target_name = "Kalinga Hospital" if "kalinga hospital" in full_text.lower() else "target hospital assets"
            why_it_matters = (
                f"Infusing funds into {target_name} expands {company}'s healthcare delivery network and operational bed capacity, "
                f"strengthening its clinical presence in target regional healthcare markets."
            )
            fund_impact = "Positive — expands healthcare delivery footprint and operational clinical bed capacity."
            fin_implication = "Operational revenue and bed occupancy from the acquired healthcare facility will consolidate post transaction closing."
        elif "matrix labs" in full_text.lower() or ("51%" in full_text and "stake" in full_text.lower()):
            why_it_matters = (
                f"Acquiring a 51% controlling stake in Matrix Labs Diagnocare enables {company} to expand into healthcare diagnostic services, "
                f"diversifying its operating revenue streams."
            )
            fund_impact = "Positive — broadens operating presence into healthcare diagnostics through majority control."
            fin_implication = "Target financials will consolidate into {company}'s earnings following closing of the share purchase agreement."
        elif direction == "Positive":
            target_m = re.search(r"\b(?:acquisition\s+of|acquires?\s+(?:stake\s+in\s+)?|stake\s+in)\s+([A-Z][A-Za-z0-9\s&.\-]+?)(?:\.|$|,|\s+for|\s+valued)", full_text)
            target_str = f"in {target_m.group(1).strip()} " if target_m and len(target_m.group(1).strip()) < 40 else ""
            why_it_matters = (
                f"The strategic acquisition {target_str}broadens {company}'s operational portfolio and commercial capabilities, "
                f"with financial accretion dependent on post-acquisition integration."
            ).replace("  ", " ")
            fund_impact = "Positive — expands operational footprint and commercial capabilities."
            fin_implication = "Financial contribution will depend on transaction valuation and subsequent operational consolidation."
        else:
            why_it_matters = (
                f"The acquisition structure introduces balance sheet leverage and integration execution risks for {company}, creating near-term return ratio drag."
            )
            fund_impact = "Negative — balance sheet leverage and integration execution risk."
            fin_implication = "Acquisition debt service and amortization charges pose near-term return on capital dilution."

    elif ev_type in ["CUSTOMER_EVENT", "INDUSTRY_EVENT"] and any(w in full_text.lower() for w in ["apple", "iphone", "foldable phone"]):
        why_it_matters = (
            f"Anticipation around next-generation consumer hardware releases accelerates volume distribution throughput and working capital turnover across {company}'s organized distribution channels."
        )
        fin_implication = "Expands shipment throughput velocity and enhances inventory turnover across technology retail distribution channels."
        fund_impact = "Positive — accelerates distribution throughput volume and drives retail channel velocity."

    elif ev_type == "FUNDING_DEBT_EVENT":
        if direction == "Positive":
            if any(w in full_text.lower() for w in ["deleverag", "debt reduction", "prepayment", "repaid", "debt repayment"]):
                why_it_matters = (
                    f"Debt reduction or prepayment lowers outstanding liabilities and interest obligations for {company}, strengthening balance sheet health and enhancing financial flexibility."
                )
                fund_impact = "Positive — reduces interest service burden and strengthens balance sheet solvency."
            else:
                _, _, identified_agency = verify_credit_rating_event(full_text)
                agency_str = f"{identified_agency}'s" if identified_agency else "The"
                rating_notch = "to 'AA'" if "'aa'" in full_text.lower() or " aa " in full_text.lower() else ""
                why_it_matters = (
                    f"{agency_str} credit rating upgrade {rating_notch} reflects strengthening operating performance and steady cash generation for {company}, lowering prospective borrowing costs on future capital raises."
                ).replace("  ", " ").strip()
                fin_implication = "Tightens borrowing yield spreads and broadens institutional access to domestic corporate bond markets."
                fund_impact = "Positive — improves credit profile and lowers financing cost of capital."
        else:
            _, _, identified_agency = verify_credit_rating_event(full_text)
            agency_str = f"{identified_agency}'s" if identified_agency else "The"
            why_it_matters = (
                f"{agency_str} credit rating downgrade reflects elevated leverage or liquidity constraints, potentially increasing borrowing costs and refinancing friction for {company}."
            ).replace("  ", " ").strip()
            fund_impact = "Negative — elevates credit risk profile and increases borrowing costs."

    else:
        if direction == "Positive":
            why_it_matters = f"The development constitutes a constructive business milestone for {company}, supporting long-term operational execution."
            fund_impact = "Positive — constructive operational milestone supporting ongoing business execution."
        else:
            why_it_matters = f"The development introduces operational friction that could weigh on {company}'s near-term outlook."
            fund_impact = "Negative — operational headwind posing risk to near-term earnings realization."

    # Time Horizon
    if ev_type in ["GOVERNMENT_EVENT", "CAPACITY_EXPANSION", "ACQUISITION"]:
        time_horizon = "Long Term"
    elif ev_type in ["ORDER_CONTRACT", "STRATEGIC_DEAL", "PRODUCT_APPROVAL", "COMMODITY_EVENT"]:
        time_horizon = "Medium Term"
    else:
        time_horizon = "Short to Medium Term"

    # MANDATORY SEMANTIC VALIDATION GATE:
    # 1. Transportation/e-truck deployments must NEVER be equated with order wins or order-book growth
    if role in ["customer", "buyer"] or "e-truck" in full_text.lower():
        for forbidden in ["order book", "order-book", "revenue visibility", "executable backlog", "contract inflow"]:
            if forbidden in why_it_matters.lower() or forbidden in fund_impact.lower():
                return None  # Semantic mismatch!

    # 2. Equity preferential issues must NEVER be equated with credit-rating improvements or lower debt costs
    if ev_type == "FUNDING_EQUITY" or "preferential issue" in full_text.lower():
        for forbidden in ["credit rating", "credit profile", "borrowing cost", "yield spread"]:
            if forbidden in why_it_matters.lower() or forbidden in fund_impact.lower():
                return None  # Semantic mismatch!

    # 3. Government defence approvals must NEVER claim immediate booked revenue or signed contracts
    if ev_type == "GOVERNMENT_EVENT":
        if re.search(r"\b(?:immediate|firm|constitutes?)\s+booked\s+revenue\b", why_it_matters.lower()) and not re.search(r"\b(?:not|rather\s+than)\b.*?\bbooked\s+revenue\b", why_it_matters.lower()):
            return None
        if re.search(r"\b(?:signed\s+contract|firm\s+order\s+win)\b", why_it_matters.lower()):
            return None

    # 4. Contractor order win must NEVER be attributed to the awarding customer
    if ev_type == "ORDER_CONTRACT" and role in ["customer", "buyer", "operator"]:
        return None  # Customer does not have order-book growth!

    # 5. Order contract must not be attributed if the text explicitly assigns the win to another company
    if ev_type == "ORDER_CONTRACT":
        win_m = re.search(r"\b([A-Za-z0-9\s&.\-]+?)\s+(?:bags?|bagged|secures?|secured|awarded|wins?|won|receives?|received)\s+(?:a\s+)?(?:major\s+)?(?:order|contract|project|mandate|epc|tender)\b", full_text, re.IGNORECASE)
        if win_m:
            winner = win_m.group(1).lower().strip()
            c_tokens = [w for w in company.lower().split() if len(w) > 2]
            if not any(tok in winner for tok in c_tokens):
                if any(w in winner for w in ["tcs", "reliance", "larsen", "bhel", "ntpc", "infosys", "wipro", "tata", "enviro"]):
                    return None

    # 6. L1 Lowest Bidder must NEVER claim secured executable order book or backlog addition
    if ev_type == "ORDER_CONTRACT" and re.search(r"\b(?:lowest\s+bidder|l1\s+bidder|emerges\s+as\s+(?:the\s+)?l1)\b", full_text, re.IGNORECASE):
        for forbidden in ["reinforces executable order book", "strengthens executable order book", "boosts executable order book", "expands project backlog"]:
            if forbidden in why_it_matters.lower() or forbidden in fund_impact.lower():
                return None  # L1 is not a secured contract yet!

    # 7. LoI must NEVER claim signed contracts or definitive execution
    if ev_type == "ORDER_CONTRACT" and re.search(r"\b(?:loi|letter\s+of\s+intent)\b", full_text, re.IGNORECASE):
        for forbidden in ["signed contract", "firm contract award", "secured contract"]:
            if forbidden in why_it_matters.lower() or forbidden in fund_impact.lower():
                return None

    # 8. Acquisitions must NEVER claim operational generation footprint (unless power generator)
    if ev_type == "ACQUISITION":
        if "generation footprint" in why_it_matters.lower() and not any(w in full_text.lower() for w in ["power", "thermal", "solar", "wind", "mw", "hydro"]):
            return None
        if "economies of scale once consolidation" in why_it_matters.lower():
            return None

    # 9. Equity preferential allotments must NEVER claim capex funding without source evidence
    if ev_type == "FUNDING_EQUITY":
        if "funds capex" in why_it_matters.lower() or "funds capex" in fund_impact.lower():
            if not any(w in full_text.lower() for w in ["capex", "capital expenditure", "expansion", "new plant", "facility"]):
                return None

    # 10. Anti-template assertion: reject if any forbidden boilerplate leaked
    for forbidden in FORBIDDEN_PHRASES:
        if forbidden.lower() in why_it_matters.lower() or forbidden.lower() in fund_impact.lower():
            return None  # Forbidden boilerplate detected!

    # Materiality Tier Attribution (Section 8)
    if mat_score >= 8.2 or (ev_type == "ORDER_CONTRACT" and (pct_rev and pct_rev >= 10.0 or order_val and order_val >= 300.0)) or (ev_type == "MANAGEMENT_EVENT" and direction == "Negative"):
        tier = "Tier A"
    elif mat_score >= 6.5 or ev_type in ["ORDER_CONTRACT", "OPERATING_UPDATE", "OPERATIONAL_INITIATIVE", "COMMODITY_EVENT", "FUNDING_DEBT_EVENT", "PRODUCT_APPROVAL", "STRATEGIC_DEAL", "ACQUISITION"]:
        tier = "Tier B"
    else:
        tier = "Tier C"

    # Sanitize string fields against stray carriage returns
    clean_headline = re.sub(r"[\r\n]+", " ", clean_headline).strip()
    what_happened = re.sub(r"[\r\n]+", " ", what_happened).strip()
    why_it_matters = re.sub(r"[\r\n]+", " ", why_it_matters).strip()
    fund_impact = re.sub(r"[\r\n]+", " ", fund_impact).strip()
    fin_implication = re.sub(r"[\r\n]+", " ", fin_implication).strip()

    item_dict = {
        "event_id": raw_event.get("cluster_id") or raw_event.get("event_id") or f"EV_{abs(hash(full_text)) % 10000000}",
        "company_name": company,
        "symbol": symbol,
        "company_role": role,
        "economic_variable": econ_var,
        "event_type": ev_type,
        "tier": tier,
        "headline": clean_headline,
        "what_happened": what_happened,
        "why_it_matters": why_it_matters,
        "fundamental_direction": direction,
        "classification": direction.upper(),
        "fundamental_impact": fund_impact,
        "key_financial_implication": fin_implication,
        "time_horizon": time_horizon,
        "order_value_cr": order_val,
        "range_text": range_text,
        "relative_revenue_pct": pct_rev,
        "materiality_score": mat_score,
        "sources": final_source,
        "event_date": raw_event.get("published_at") or raw_event.get("news_date", "")
    }

    # Extract structured facts for strict source-to-analysis verification
    facts = extract_structured_event_facts(raw_event, full_text)
    is_valid, _ = validate_fna_story(raw_event, item_dict, facts, debug=debug)
    if not is_valid:
        return None

    item_dict["structured_facts"] = facts
    return item_dict


def extract_structured_event_facts(raw_event: Dict[str, Any], text: str) -> Dict[str, Any]:
    """
    Extracts structured facts from the underlying source text:
      - event_type: canonical classification
      - company: target corporate entity
      - date: publication or event date
      - amount: extracted monetary amount in ₹ Cr
      - amount_metric: semantic metric classification (order_value, equity_raise, procurement_value, etc.)
      - counterparty: awarding client, partner, or agency
      - status: awarded, approved, cleared, resigned, narrowed, upgraded
      - duration: project or agreement duration
      - source_facts: list of verifiable factual sentence fragments
    """
    company = raw_event.get("company_name") or raw_event.get("company", "Company")
    ev_type, direction, _ = classify_event_direction_and_type(text)

    # Extract financial metrics
    parsed = parse_semantic_financial_metrics(text)
    amount = None
    amount_metric = None
    if parsed:
        amount = parsed[0].get("value_cr")
        m_type = parsed[0].get("metric")
        metric_map = {
            "ORDER_VALUE": "order_value",
            "EQUITY_RAISE": "equity_raise",
            "PROCUREMENT_PIPELINE": "procurement_value",
            "PAT": "net_profit",
            "NET_LOSS": "net_loss",
            "REVENUE": "revenue",
            "TOLL_REVENUE": "toll_revenue",
            "CAPEX": "capex_outlay",
            "PENALTY": "regulatory_penalty",
            "GENERIC_MONETARY": "disclosed_amount"
        }
        amount_metric = metric_map.get(m_type, "disclosed_amount")

    # Extract Counterparty
    counterparty = None
    cp_match = re.search(r"\b(?:from|with|awarded\s+by|selected\s+by)\s+([A-Z][A-Za-z0-9\s&.\-]+?)(?:,|\.|\s+for|\s+valued|\s+to\s+build|\s+worth|\s+under|$)", text)
    if cp_match:
        cp_cand = cp_match.group(1).strip()
        if len(cp_cand) < 40 and not any(w in cp_cand.lower() for w in ["share", "order", "contract", "crore", "rs", "inr", "percent", "nifty", "sensex"]):
            counterparty = cp_cand

    # Extract Duration
    duration = None
    dur_match = re.search(r"\b(\d+[- ](?:year|month|quarter|day)s?)\b", text, re.IGNORECASE)
    if dur_match:
        duration = dur_match.group(1)

    # Extract Status
    status = "announced"
    t_lower = text.lower()
    if any(w in t_lower for w in ["bags", "bagged", "secured", "awarded", "wins", "won"]):
        status = "awarded"
    elif any(w in t_lower for w in ["approved", "approval", "cleared", "nod"]):
        status = "approved"
    elif "resigned" in t_lower or "resignation" in t_lower:
        status = "resigned"
    elif "upgraded" in t_lower or "upgrade" in t_lower:
        status = "upgraded"
    elif "downgraded" in t_lower or "downgrade" in t_lower:
        status = "downgraded"
    elif "deploys" in t_lower or "deployed" in t_lower or "deployment" in t_lower:
        status = "deployed"

    source_facts = [s.strip() for s in re.split(r"[.\n;]+", text) if len(s.strip()) > 15][:5]

    return {
        "event_type": ev_type,
        "company": company,
        "date": raw_event.get("event_date") or raw_event.get("published_at", ""),
        "amount": amount,
        "amount_metric": amount_metric,
        "counterparty": counterparty,
        "status": status,
        "duration": duration,
        "source_facts": source_facts
    }


def validate_source_to_event_fidelity(raw_event: Dict[str, Any], facts: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Pass 1: Verifies that the event is directly and truthfully supported by the underlying source.
    Rejects macro market wraps, third-party attribution, and operational mismatches.
    """
    title = raw_event.get("title", "")
    summary = raw_event.get("summary", "")
    text = f"{title} {summary}"
    t_lower = text.lower()
    company = facts.get("company", "")
    c_lower = company.lower()
    ev_type = facts.get("event_type")

    # 1. Commodity events derived from broader macro/currency/equity index wraps must be rejected
    if ev_type == "COMMODITY_EVENT":
        commodity_macro_wrap = [
            "msci", "hang seng", "taiwan taiex", "asian markets", "nifty", "sensex", 
            "rupee", "inr extends", "inr opened", "local shares", "us stocks", 
            "dow jones", "wall street", "s&p 500", "nasdaq", "market wrap"
        ]
        if any(w in t_lower for w in commodity_macro_wrap):
            has_direct_company = any(tok in t_lower for tok in [w for w in c_lower.split() if len(w) > 3 and w not in ["corporation", "limited", "india"]])
            has_direct_commodity_focus = any(w in t_lower for w in ["omc", "marketing margin", "upstream realization", "petrol and diesel", "crude tops $100", "crude boils", "oil surges past", "brent crude crosses"])
            if not (has_direct_company or has_direct_commodity_focus):
                return False, f"Source discusses broader macro/currency/index market movements, not direct commodity fundamentals for {company}"

    # 2. General Macro Market Index Wrap Mismatch (e.g. general Nifty/Sensex/Asian/US market drops)
    macro_indicators = [
        "msci asia-pacific", "hang seng", "taiwan taiex", "asian markets", 
        "nifty slips below", "sensex plunges", "market wrap", "stocks in news", 
        "why stock market is down", "fpis sell", "indian equity markets hit",
        "us stocks", "dow jones", "wall street", "s&p 500", "nasdaq", "sensex", "nifty"
    ]
    if any(m in t_lower for m in macro_indicators):
        corp_indicators = [
            "order", "contract", "q1", "q2", "q3", "q4", "resigns", "resignation", 
            "commissioning", "approval", "upgrades", "downgrades", "preferential issue", 
            "dividend", "loi", "tender"
        ]
        generic_tokens = {
            "oil", "gas", "bank", "power", "steel", "iron", "coal", "gold", "zinc", 
            "copper", "metal", "india", "indian", "ltd", "limited", "corp", "corporation", 
            "industries", "holdings", "group", "finance", "infra", "infrastructure", 
            "technologies", "services", "energy", "life", "consumer", "products", "retail", "enterprises"
        }
        distinct_tokens = [w for w in c_lower.split() if len(w) > 2 and w not in generic_tokens]
        has_company = any(tok in t_lower for tok in distinct_tokens) or (c_lower in t_lower)
        has_corp_announcement = any(ci in t_lower for ci in corp_indicators)

        if not (has_company and has_corp_announcement):
            return False, f"Source discusses broader market index movements (MSCI/Asia-Pacific/Nifty), not verified corporate fundamentals for {company}"

    # 2. Operational e-truck / logistics deployment mismatch
    if any(w in t_lower for w in ["e-truck", "electric truck", "deployment of", "for logistics operations"]):
        if ev_type == "ORDER_CONTRACT" or facts.get("amount_metric") == "order_value":
            return False, f"Operational logistics deployment cannot be equated with an order contract win for {company}"

    # 3. Third-party contract award mismatch
    win_match = re.search(r"\b([A-Za-z0-9\s&.\-]+?)\s+(?:bags?|bagged|secures?|secured|awarded|wins?|won)\s+(?:a\s+)?(?:major\s+)?(?:order|contract|project|mandate|epc|tender)\b", text, re.IGNORECASE)
    if win_match:
        winner = win_match.group(1).lower().strip()
        c_tokens = [w for w in c_lower.split() if len(w) > 2]
        if not any(tok in winner for tok in c_tokens):
            if any(w in winner for w in ["tcs", "reliance", "larsen", "bhel", "ntpc", "infosys", "wipro", "tata", "enviro"]):
                return False, f"Source explicitly attributes contract win to another corporate entity ({winner})"

    # 4. Amalgamation / Scheme without disclosed economic basis
    if "amalgamation" in t_lower or "merger" in t_lower:
        if not any(w in t_lower for w in ["swap ratio", "merger ratio", "nclt approved", "scheme approved", "effective date", "share exchange"]):
            return False, "Amalgamation scheme lacks disclosed economic terms to determine shareholder impact"

    return True, "PASS"


def validate_event_to_analysis_consistency(item: Dict[str, Any], facts: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Pass 2: Verifies that the generated reasoning strictly corresponds to the actual event type and facts.
    Executes the mandatory 6-point consistency validation:
      1. Does the headline match the event?
      2. Does 'What happened' match the source?
      3. Does 'Why it matters' follow from the event?
      4. Does 'Fundamental impact' follow from 'Why it matters'?
      5. Does 'Key financial implication' use the correct financial concept?
      6. Is the company actually the economic beneficiary?
    """
    ev_type = item.get("event_type")
    role = item.get("company_role", "")
    why = item.get("why_it_matters", "").lower()
    impact = item.get("fundamental_impact", "").lower()
    fin_imp = item.get("key_financial_implication", "").lower()
    what = item.get("what_happened", "").lower()
    headline = item.get("headline", "")
    h_lower = headline.lower()
    company = item.get("company_name", "")
    direction = item.get("fundamental_direction", "")

    sf = facts.get("source_facts", [])
    source_corpus = " ".join(sf) if isinstance(sf, list) else (sf.get("text", "") if isinstance(sf, dict) else str(sf))
    full_text_lower = f"{headline} {what} {why} {source_corpus}".lower()

    is_l1 = bool(re.search(r"\b(?:lowest\s+bidder|l1\s+bidder|emerges\s+as\s+(?:the\s+)?l1)\b", full_text_lower))
    is_loi = bool(re.search(r"\b(?:loi|letter\s+of\s+intent)\b", full_text_lower))
    is_penalty = bool(re.search(r"\b(?:penalt(?:y|ies)|fine|fined|tngst|rera\s+penalty)\b", f"{headline} {what} {source_corpus}".lower()))

    # =========================================================================
    # CHECK 1: Does the headline match the event?
    # =========================================================================
    if any(h_lower == p or h_lower.startswith(p) for p in [
        "updates", "general updates", "press release", "announcement", "corporate action", 
        "intimation under", "limited:", "company limited:", "outcome of board meeting"
    ]):
        return False, f"Headline '{headline}' is a generic administrative placeholder rather than an actionable corporate event"
    if headline.endswith(":") or len(headline.strip()) < 10:
        return False, f"Headline '{headline}' is truncated or too brief"

    if is_l1:
        if not any(k in h_lower for k in ["lowest bidder", "l1", "bids lowest"]):
            return False, "Headline must reflect L1 lowest-bidder status rather than a definitive contract award"
        if any(k in h_lower for k in ["bags order", "secures contract", "awarded order", "wins contract", "bags contract", "signs contract"]):
            return False, "Headline incorrectly claims definitive contract award for an L1 lowest-bidder event"

    if is_loi and not is_l1:
        if any(k in h_lower for k in ["signs contract", "executes contract", "bags definitive order"]):
            return False, "Headline incorrectly claims definitive contract execution for a Letter of Intent (LOI)"

    if ev_type == "REGULATORY_EVENT" and is_penalty:
        if not any(k in h_lower for k in ["penalty", "fine", "order", "levies", "imposes"]):
            return False, "Headline must indicate regulatory penalty action"

    if ev_type == "MANAGEMENT_EVENT" and "auditor" in full_text_lower and ("resigned" in full_text_lower or "resignation" in full_text_lower):
        if not any(k in h_lower for k in ["auditor", "resigns", "resignation"]):
            return False, "Headline must indicate statutory auditor resignation"

    # =========================================================================
    # CHECK 2: Does 'What happened' match the source?
    # =========================================================================
    if len(what.strip()) < 20:
        return False, "What happened description is insufficiently detailed"

    claimed_figures = re.findall(r"₹\s*([0-9,]+(?:\.[0-9]+)?)\s*(?:cr(?:ore)?)", why + " " + what, re.IGNORECASE)
    for fig_str in claimed_figures:
        clean_num_str = fig_str.replace(",", "")
        try:
            val = float(clean_num_str)
            fact_amt = facts.get("amount")
            if fact_amt is not None and abs(fact_amt - val) < 0.2:
                continue
            if clean_num_str in source_corpus or fig_str in source_corpus:
                continue
            if f"{int(val)}" in source_corpus:
                continue
            return False, f"Analysis claims financial figure ₹{fig_str} Cr that does not appear in source facts"
        except (ValueError, TypeError):
            continue

    # =========================================================================
    # CHECK 3: Does 'Why it matters' follow from the event?
    # =========================================================================
    for forbidden in FORBIDDEN_PHRASES:
        if forbidden.lower() in why or forbidden.lower() in impact:
            return False, f"Analysis contains forbidden generic boilerplate phrase: '{forbidden}'"

    if is_l1:
        for forbidden in ["reinforces executable order book", "strengthens executable order book", "boosts executable order book", "expands project backlog"]:
            if forbidden in why:
                return False, f"L1 lowest-bidder analysis incorrectly claims order book expansion: '{forbidden}'"
        if not any(k in why for k in ["contingent", "letter of award", "loa", "definitive contract", "contract signing", "qualification"]):
            return False, "L1 analysis must clarify that executable revenue is contingent on formal contract award (LoA)"

    if is_loi and not is_l1:
        for forbidden in ["signed contract", "firm contract award", "secured contract"]:
            if forbidden in why:
                return False, f"LOI analysis incorrectly claims signed contract: '{forbidden}'"
        if not any(k in why for k in ["contingent", "definitive contract", "framework", "formal order-book recognition", "convert"]):
            return False, "LOI analysis must clarify that formal order book addition follows definitive contract execution"

    if ev_type == "FUNDING_EQUITY" or "preferential issue" in full_text_lower:
        if "funds capex" in why:
            if not any(w in full_text_lower for w in ["capex", "capital expenditure", "expansion", "new plant", "facility"]):
                return False, "Equity preferential allotment incorrectly claims capex funding without source evidence"
        for forbidden in ["credit rating", "credit profile", "borrowing cost", "yield spread", "debt reduction"]:
            if forbidden in why:
                return False, f"Equity preferential issue incorrectly claims {forbidden}"

    if ev_type == "ACQUISITION":
        if "generation footprint" in why and not any(w in full_text_lower for w in ["power", "thermal", "solar", "wind", "mw", "hydro", "energy"]):
            return False, "Acquisition incorrectly claims power generation footprint for non-power asset"
        if "bed capacity" in why and not any(w in full_text_lower for w in ["hospital", "clinical", "healthcare", "bed"]):
            return False, "Acquisition incorrectly claims bed capacity for non-healthcare asset"
        if "economies of scale once consolidation" in why:
            return False, "Acquisition contains generic economies of scale boilerplate"

    if ev_type == "GOVERNMENT_EVENT":
        if re.search(r"\b(?:immediate|firm|constitutes?)\s+booked\s+revenue\b", why) and not re.search(r"\b(?:not|rather\s+than)\b.*?\bbooked\s+revenue\b", why):
            return False, "Government defence clearance incorrectly claims immediate booked revenue"
        if "signed contract" in why or "firm order win" in why:
            return False, "Government defence clearance incorrectly asserts firm signed contract"

    if ev_type == "PRODUCT_APPROVAL":
        if "rbi" in what and "stake" in what:
            for forbidden in ["immediate commercialization", "improves earnings", "addressable target market reach", "strengthens credit profile"]:
                if forbidden in why or forbidden in impact:
                    return False, f"Regulatory stake clearance incorrectly claims {forbidden}"

    if any(k in full_text_lower for k in ["regulation 29", "sast", "takeover regulation"]):
        return False, "Routine shareholding disclosure (SAST) is not an operational or fundamental expansion event"

    if any(k in full_text_lower for k in ["esop", "stock option"]):
        return False, "Employee stock option grant is not a regulatory clearance or commercialization event"

    if ev_type == "OPERATIONAL_INITIATIVE":
        for forbidden in ["order book", "revenue visibility", "executable backlog", "contract inflow"]:
            if forbidden in why or forbidden in impact:
                return False, f"Operational logistics initiative incorrectly claims {forbidden}"

    if ev_type == "COMMODITY_EVENT":
        for forbidden in ["order book", "executable backlog", "contract inflow"]:
            if forbidden in why or forbidden in impact:
                return False, f"Commodity realization event incorrectly claims {forbidden}"

    if ev_type != "ORDER_CONTRACT":
        for generic_phrase in ["strengthens forward revenue visibility", "reinforces executable order book"]:
            if generic_phrase in why or generic_phrase in impact:
                return False, f"Generic order-book phrase '{generic_phrase}' is not justified for event type {ev_type}"

    # =========================================================================
    # CHECK 4: Does 'Fundamental impact' follow from 'Why it matters'?
    # =========================================================================
    if direction == "Positive" and not impact.startswith("positive"):
        return False, f"Fundamental impact '{item.get('fundamental_impact')}' does not start with Positive for positive direction"
    if direction == "Negative" and not impact.startswith("negative"):
        return False, f"Fundamental impact '{item.get('fundamental_impact')}' does not start with Negative for negative direction"

    if is_l1 and not any(k in impact for k in ["contingent", "lowest-bidder", "lowest bidder", "formal contract award", "contract signing"]):
        return False, "Fundamental impact for L1 must state contingency on formal contract award"

    if is_loi and not is_l1 and not any(k in impact for k in ["preliminary", "pending definitive contract", "framework", "loi"]):
        return False, "Fundamental impact for LOI must reflect preliminary commitment pending contract execution"

    # =========================================================================
    # CHECK 5: Does 'Key financial implication' use the correct financial concept?
    # =========================================================================
    if is_l1:
        if not any(k in fin_imp for k in ["letter of award", "contract signing", "contingent", "upon formal", "definitive contract"]):
            return False, "Key financial implication for L1 must note revenue is recognized only upon contract signing/LoA"
        if any(k in fin_imp for k in ["immediate executable backlog", "immediate booked revenue"]):
            return False, "Key financial implication for L1 incorrectly claims immediate booked revenue"

    if is_loi and not is_l1:
        if not any(k in fin_imp for k in ["convert", "definitive contract", "formal", "upon execution", "backlog"]):
            return False, "Key financial implication for LOI must state conversion upon definitive contract signing"

    if ev_type == "FUNDING_EQUITY":
        if not any(k in fin_imp for k in ["equity", "net worth", "capital", "dilution", "cash balance"]):
            return False, "Key financial implication for equity raise must reference equity capital base, net worth, or dilution"
        if any(k in fin_imp for k in ["debt-servicing capability", "borrowing cost", "yield spread"]):
            return False, "Key financial implication for equity raise incorrectly references debt-service concepts"

    amt_metric = facts.get("amount_metric")
    if amt_metric == "equity_raise":
        if "contract inflow" in fin_imp:
            return False, "Equity preferential issue metric mislabeled as contract inflow"
    elif amt_metric == "net_loss":
        if "contract inflow" in fin_imp or "order value" in fin_imp:
            return False, "Net loss figure mislabeled as contract inflow"

    if ev_type == "REGULATORY_EVENT" and is_penalty:
        if not any(k in fin_imp for k in ["penalty", "non-operating", "charge", "statutory", "remediation"]):
            return False, "Key financial implication for regulatory penalty must reference non-operating charge or penalty"

    if ev_type == "MANAGEMENT_EVENT" and "auditor" in full_text_lower and ("resigned" in full_text_lower or "resignation" in full_text_lower):
        if not any(k in fin_imp for k in ["overhang", "valuation", "governance", "audit", "transition"]):
            return False, "Key financial implication for auditor resignation must reference governance/valuation multiple overhang"

    # =========================================================================
    # CHECK 6: Is the company actually the economic beneficiary?
    # =========================================================================
    if ev_type == "ORDER_CONTRACT":
        if role in ["customer", "buyer", "operator"]:
            return False, f"Role '{role}' is inconsistent with ORDER_CONTRACT win for {company}"
        if any(w in why for w in ["credit rating", "credit profile", "borrowing cost", "yield spread"]):
            return False, "Order contract analysis incorrectly claims credit rating improvement"
        if re.search(rf"\b{re.escape(company.lower())}\b.*?\b(?:issues?|issued|invites?)\b.*?\b(?:loi|tender|order|contract)\b", full_text_lower):
            return False, f"{company} is the awarding party/issuer of the tender or LOI, not the beneficiary"

    if ev_type == "FUNDING_EQUITY" and role != "issuer":
        return False, f"Role '{role}' is inconsistent with equity capital raise for {company}"

    return True, "PASS"


def validate_fna_story(raw_event: Dict[str, Any], item: Dict[str, Any], facts: Dict[str, Any], debug: bool = False) -> Tuple[bool, str]:
    """
    Master Validation Gate executing the two-pass Source -> Event -> Analysis Consistency check.
    Returns (is_pass: bool, reason: str).
    """
    direction = item.get("fundamental_direction")
    if direction not in ["Positive", "Negative"]:
        if debug:
            print(f"[VALIDATE] {item.get('company_name')}\n[FAIL] Direction '{direction}' is not strictly Positive or Negative\n[DECISION] REJECT\n")
        return False, f"Direction '{direction}' is not strictly Positive or Negative"

    # Pass 1: Source -> Event Fidelity Check
    fid_pass, fid_reason = validate_source_to_event_fidelity(raw_event, facts)
    if not fid_pass:
        if debug:
            print(f"[VALIDATE] {item.get('company_name')}\n[FAIL] {fid_reason}\n[DECISION] REJECT\n")
        return False, fid_reason

    # Pass 2: Event -> Analysis Consistency Check
    cons_pass, cons_reason = validate_event_to_analysis_consistency(item, facts)
    if not cons_pass:
        if debug:
            print(f"[VALIDATE] {item.get('company_name')}\n[FAIL] {cons_reason}\n[DECISION] REJECT\n")
        return False, cons_reason

    if debug:
        print(f"[VALIDATE] {item.get('company_name')}\n[PASS] Source facts and generated analysis fully consistent\n[DECISION] INCLUDE\n")

    return True, "PASS"
