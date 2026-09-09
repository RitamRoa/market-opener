"""
Event Detector & Catalyst Classifier for Indian Equities.
Classifies raw announcements and clustered news into specific corporate event categories.
Evaluates economic impact (POSITIVE, NEGATIVE, MIXED, NEUTRAL) based on business reality, not just headlines.
"""

import re
from typing import Dict, Any, Tuple

# Regex keyword sets for corporate catalysts
CATALYST_RULES = [
    {
        "type": "Contract / Order Win",
        "keywords": [r"\border\b", r"\bcontract\b", r"\bbagged\b", r"\bsecures\b", r"\bwon\b", r"\bdeal\b", r"\bproject award\b", r"\bwork order\b", r"\bcr order\b", r"\bcrore order\b"],
        "default_sentiment": "POSITIVE",
        "materiality": 0.85
    },
    {
        "type": "Corporate Results / Earnings",
        "keywords": [r"\bq[1-4]\b", r"\bquarterly results\b", r"\bnet profit\b", r"\bebitda\b", r"\brevenue jumps\b", r"\bprofit surges\b", r"\bearnings\b", r"\bfinancial results\b"],
        "default_sentiment": "MIXED", # Will refine based on growth vs contraction
        "materiality": 0.90
    },
    {
        "type": "Acquisitions & M&A",
        "keywords": [r"\bacquires\b", r"\bacquisition\b", r"\bmerger\b", r"\btakeover\b", r"\bbuyout\b", r"\bstake buy\b", r"\bjoint venture\b", r"\bjv\b"],
        "default_sentiment": "POSITIVE",
        "materiality": 0.80
    },
    {
        "type": "Regulatory & Legal Action",
        "keywords": [r"\bsebi\b", r"\brbi\b", r"\bus fda\b", r"\bform 483\b", r"\bwarning letter\b", r"\bpenalty\b", r"\braid\b", r"\btax demand\b", r"\benforcement directorate\b", r"\bprobe\b", r"\bcci penalty\b"],
        "default_sentiment": "NEGATIVE",
        "materiality": 0.95
    },
    {
        "type": "Promoter & Capital Actions",
        "keywords": [r"\bbuyback\b", r"\bdividend\b", r"\bpromoter buying\b", r"\bopen offer\b", r"\bpreferential issue\b", r"\bqip\b", r"\brights issue\b", r"\bpromoter stake\b", r"\bpledge\b"],
        "default_sentiment": "POSITIVE",
        "materiality": 0.75
    },
    {
        "type": "Management & Governance",
        "keywords": [r"\bresignation\b", r"\bceo steps down\b", r"\bcfo resigns\b", r"\bauditor resigns\b", r"\bboard change\b", r"\bappointed\b", r"\bnew md\b"],
        "default_sentiment": "MIXED",
        "materiality": 0.70
    },
    {
        "type": "Capacity Expansion & Capex",
        "keywords": [r"\bcommissioning\b", r"\bnew plant\b", r"\bcapacity expansion\b", r"\bgreenfield\b", r"\bbrownfield\b", r"\bcommercial production\b", r"\binaugurates\b"],
        "default_sentiment": "POSITIVE",
        "materiality": 0.75
    },
    {
        "type": "Credit Rating & Upgrades",
        "keywords": [r"\brating upgrade\b", r"\bcrisil\b", r"\bicra\b", r"\bcare ratings\b", r"\boutlook revised\b", r"\bdowngrade\b"],
        "default_sentiment": "MIXED",
        "materiality": 0.65
    }
]

POSITIVE_INDICATORS = [
    r"\bjumps\b", r"\bsurges\b", r"\bgrows\b", r"\bsoars\b", r"\brecord high\b", r"\bup \d+%\b",
    r"\bbeat estimates\b", r"\bguidance raised\b", r"\bexpansion\b", r"\bbonus issue\b", r"\bapproves buyback\b"
]

NEGATIVE_INDICATORS = [
    r"\bslumps\b", r"\bdrops\b", r"\btumbles\b", r"\bplunges\b", r"\bdown \d+%\b", r"\bprofit falls\b",
    r"\bmisses estimates\b", r"\bguidance cut\b", r"\bsuspension\b", r"\binjunction\b", r"\bfda observation\b",
    r"\bpenalty imposed\b", r"\bfraud\b", r"\bdefault\b", r"\binsolvency\b"
]


def detect_event_type_and_sentiment(title: str, summary: str = "") -> Tuple[str, str, float]:
    """
    Analyzes title and summary to determine:
    1. Event Type (e.g. Contract / Order Win, Corporate Results, etc.)
    2. Economic Sentiment (POSITIVE, NEGATIVE, MIXED, NEUTRAL)
    3. Materiality Score (0.0 to 1.0)
    """
    text = f"{title} {summary}".lower()

    detected_type = "General Corporate Development"
    materiality = 0.50
    sentiment = "NEUTRAL"

    # Match catalyst rule
    for rule in CATALYST_RULES:
        for kw in rule["keywords"]:
            if re.search(kw, text):
                detected_type = rule["type"]
                sentiment = rule["default_sentiment"]
                materiality = rule["materiality"]
                break
        if detected_type != "General Corporate Development":
            break

    # Refine sentiment using economic indicators
    pos_matches = sum(1 for p in POSITIVE_INDICATORS if re.search(p, text))
    neg_matches = sum(1 for n in NEGATIVE_INDICATORS if re.search(n, text))

    if detected_type == "Regulatory & Legal Action":
        # Regulatory actions are almost always negative or high risk
        sentiment = "NEGATIVE"
        materiality = max(materiality, 0.90)
    elif detected_type == "Contract / Order Win":
        sentiment = "POSITIVE"
        materiality = max(materiality, 0.80)
    elif pos_matches > neg_matches:
        sentiment = "POSITIVE"
    elif neg_matches > pos_matches:
        sentiment = "NEGATIVE"
    elif pos_matches > 0 and neg_matches > 0:
        sentiment = "MIXED"

    return detected_type, sentiment, materiality
