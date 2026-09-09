"""
Noise Filter & Quality Control Gating Module.
Enforces the 'FNA-Worthy' and 'Why Today?' Freshness Gates:
  1. Filters routine administrative disclosures & compliance filings (trading window, duplicate shares, etc.)
  2. Filters stale historical quarterly earnings articles (e.g. FY24/FY25 resurfacing in search)
  3. Filters broker target-price changes and generic analyst recommendations lacking primary corporate catalysts
  4. Retains genuine, current fundamental catalysts (Order wins, Capex, FDA, Regulatory, M&A)
"""

import re
from datetime import datetime
from typing import Tuple

# Routine corporate filings and compliance disclosures to filter out
ROUTINE_FILING_PATTERNS = [
    r"\bclosure\s+of\s+trading\s+window\b",
    r"\btrading\s+window\s+closure\b",
    r"\bloss\s+of\s+share\s+certificate\b",
    r"\bduplicate\s+share\s+certificate\b",
    r"\bregulation\s+74\s*\(\s*5\s*\)",
    r"\bregulation\s+7\s*\(\s*3\s*\)",
    r"\bregulation\s+40\s*\(\s*9\s*\)",
    r"\bregulation\s+39\s*\(\s*3\s*\)",
    r"\bscrutinizer['’]?s\s+report\b",
    r"\bvoting\s+results\s+of\s+postal\s+ballot\b",
    r"\bpostal\s+ballot\s+notice\b",
    r"\bschedule\s+of\s+(?:analyst|institutional\s+investor)\s+meet\b",
    r"\bintimation\s+of\s+schedule\s+of\s+analyst\b",
    r"\baudio\s+recording\s+of\s+(?:earnings|conference)\s+call\b",
    r"\btranscript\s+of\s+(?:earnings|conference)\s+call\b",
    r"\bboard\s+meeting\s+intimation\b",
    r"\bboard\s+meeting\s+to\s+consider\s+(?:financial\s+results|unaudited)\b",
    r"\bnotice\s+of\s+board\s+meeting\b",
    r"\bnewspaper\s+publication\b",
    r"\bnewspaper\s+advertisement\b",
    r"\bchange\s+in\s+registered\s+office\b",
    r"\bchange\s+in\s+company\s+secretary\b",
    r"\bcompliance\s+certificate\b",
    r"\brecord\s+date\s+for\s+annual\s+general\s+meeting\b",
    r"\bbook\s+closure\s+intimation\b",
    r"\bclarification\s+sought\s+from\b"
]

ROUTINE_REGEX = re.compile("|".join(ROUTINE_FILING_PATTERNS), re.IGNORECASE)

# Broker target price & generic analyst recommendation patterns (Section 34)
BROKER_RECOMMENDATION_PATTERNS = [
    r"\braises?\s+target\s+price\b",
    r"\bcuts?\s+target\s+price\b",
    r"\bsets?\s+target\s+price\b",
    r"\bmaintains?\s+(?:buy|sell|hold|neutral|accumulate|outperform)\b",
    r"\bretains?\s+(?:buy|sell|hold|neutral|accumulate)\b",
    r"\binitiates?\s+coverage\b",
    r"\b(?:overweight|underweight|equal-weight|outperform|underperform)\b",
    r"\bgives?\s+buy\s+call\b",
    r"\btarget\s+price\s+of\s+rs\b",
    r"\btarget\s+price\b",
    r"\bprice\s+target\b",
    r"\bprice\s+target\s+hiked\b",
    r"\bbrokerage\s+calls?\b",
    r"\bbrokerage\s+sees\b",
    r"\bbroker\s+target\b",
    r"\btop\s+shares\s+to\s+buy\b",
    r"\bexpert\s+views\b",
    r"\bbull\s+of\s+the\s+day\b",
    r"\bshares\s+to\s+buy\b",
    r"\bshould\s+you\s+buy\b",
    r"\bwhat\s+should\s+investors\s+do\b",
    r"\b(?:bernstein|jefferies|morgan\s+stanley|macquarie|ubs|clsa|nomura|jpmorgan|citi|goldman\s+sachs)\s+(?:prefers|favours|favors|sees|says|initiates|maintains|reiterates|bullish|bearish)\b",
    r"\bwhy\s+(?:bernstein|jefferies|morgan\s+stanley|macquarie|ubs|clsa|nomura|jpmorgan|citi|goldman\s+sachs)\s+prefers\b"
]

BROKER_REGEX = re.compile("|".join(BROKER_RECOMMENDATION_PATTERNS), re.IGNORECASE)

# Clickbait and generic promotional market noise patterns
CLICKBAIT_PATTERNS = [
    r"\btop\s+\d+\s+stocks\b",
    r"\bstocks\s+to\s+buy\b",
    r"\bhot\s+stocks\b",
    r"\bwealth\s+creators?\b",
    r"\bmultibagger\b",
    r"\btrading\s+ideas\b",
    r"\bmarket\s+live\s+updates\b",
    r"\bclosing\s+bell\b",
    r"\bopening\s+bell\b",
    r"\bgift\s+nifty\b",
    r"\bwhere\s+to\s+invest\b",
    r"\bhow\s+to\s+invest\b"
]

CLICKBAIT_REGEX = re.compile("|".join(CLICKBAIT_PATTERNS), re.IGNORECASE)

# Stale historical quarterly results pattern (e.g. FY24 / FY23 articles when reporting in 2026)
STALE_QUARTER_PATTERNS = [
    r"\bq[1-4]\s*(?:of\s*)?fy\s*(?:23|24|2023|2024)\b",
    r"\bfy\s*(?:23|24|2023|2024)\s+(?:results|earnings|net\s+profit|pat|performance|slump)\b",
    r"\bended\s+march\s+31,?\s*2024\b",
    r"\bended\s+december\s+31,?\s*2023\b"
]

STALE_REGEX = re.compile("|".join(STALE_QUARTER_PATTERNS), re.IGNORECASE)

# Keywords indicating genuine fundamental developments
MATERIAL_KEYWORDS = [
    r"\border\b", r"\bcontract\b", r"\bbagged\b", r"\bsecures\b", r"\bwon\b", r"\bdeal\b",
    r"\bloi\b", r"\bletter\s+of\s+intent\b", r"\bmou\b", r"\bproject\b", r"\bwind\s+power\b", r"\bsolar\s+plant\b", r"\brenewable\b",
    r"\bexpansion\b", r"\bcommission(?:ing|ed|s)?\b", r"\bnew\s+plant\b", r"\bcapex\b", r"\bcommercial\s+production\b",
    r"\bacquisition\b", r"\bacquires\b", r"\bmerger\b", r"\bamalgamation\b", r"\bscheme\s+of\s+amalgamation\b", r"\bjoint\s+venture\b", r"\bjv\b",
    r"\bfda\b", r"\busfda\b", r"\bform\s+483\b", r"\bwarning\s+letter\b", r"\bapproval\b", r"\bclears?\b", r"\bclearance\b",
    r"\bsebi\b", r"\brbi\b", r"\bpenalty\b", r"\btax\s+demand\b", r"\bsearch\s+and\s+seizure\b",
    r"\bnet\s+profit\b", r"\bebitda\b", r"\brevenue\b", r"\bquarterly\s+results\b", r"\bearnings\b",
    r"\btoll\s+revenue\b", r"\btoll\s+collection\b", r"\bvolume\s+growth\b", r"\bdispatches\b",
    r"\bpreferential\s+(?:issue|allotment)\b", r"\bcapital\s+infusion\b",
    r"\bratings?\s+upgrades?\b", r"\bratings?\s+downgrades?\b", r"\bcredit\s+ratings?\s+upgrades?\b", r"\bcredit\s+ratings?\s+downgrades?\b",
    r"\bupgrades?\b.*?\b(?:rating|ratings|debt)\b", r"\bdowngrades?\b.*?\b(?:rating|ratings|debt)\b",
    r"\bdebt\s+reduction\b", r"\brepayment\b", r"\bprepayment\b",
    r"\bresignation\b", r"\bappointed\b", r"\bnew\s+ceo\b", r"\bnew\s+md\b", r"\bauditor\s+resigned\b",
    r"\bprice\s+hike\b", r"\btariff\s+revision\b", r"\bprice\s+increase\b",
    r"\bprocurement\b", r"\bdac\b", r"\bdefence\s+acquisition\b", r"\bl1\s+bidder\b", r"\blowest\s+bidder\b", r"\blakh\s+crore\b",
    r"\bcrude\s+oil\b", r"\bbrent\s+crude\b", r"\boil\s+tops\b", r"\boil\s+surges\b", r"\bcopper\b"
]

MATERIAL_REGEX = re.compile("|".join(MATERIAL_KEYWORDS), re.IGNORECASE)


def is_material_fundamental_event(title: str, summary: str = "", is_primary_exchange_filing: bool = False, published_at: str = "") -> Tuple[bool, str]:
    """
    Quality Control Gate: Enforces FNA-worthiness and 'Why Today?' Freshness tests.
    Returns (True, 'Reason accepted') if event is a current, genuine fundamental corporate catalyst.
    Returns (False, 'Reason filtered') if event is routine compliance, stale news, broker call, clickbait,
    multi-company roundup container, pure price rally, or routine credit rating reaffirmation.
    """
    text = f"{title} {summary}".strip()
    if len(text) < 15:
        return False, "Discarded: text too short to contain substantive corporate development."

    # 1. Freshness Check: Reject stale historical quarterly results
    if not is_primary_exchange_filing:
        if published_at and any(y in published_at.lower() for y in ["2024", "2023", "2022", "2021", "2020"]):
            return False, "Discarded: stale historical news (published in 2024/2023)."

        if STALE_REGEX.search(text):
            return False, "Discarded: stale historical news (refers to old FY24/FY23 quarterly periods)."

        if any(y in text for y in ["2024", "2023", "2022"]) and any(k in text.lower() for k in ["q1", "q2", "q3", "q4", "quarter", "net profit", "revenue", "results", "ended march 31"]):
            return False, "Discarded: stale historical news (refers to old 2024/2023 quarterly results)."

    # Identify if a primary corporate or sovereign fundamental catalyst exists
    has_primary_catalyst = bool(re.search(
        r"\b(?:dac\b|defence\s+acquisition|procurement|lakh\s+crore|order\b|contract\b|bags?\b|secures?\b|wins?\b|loi\b|epc\b|usfda\b|fda\b|acquisition\b|merger\b|amalgamation\b|toll\s+revenue|toll\s+collection|preferential\s+issue|rating\s+upgrade|upgrades?\s+rating|crude\s+oil|oil\s+tops|oil\s+surges|resignation\b.*?\b(?:chairman|auditor|ceo|md))\b",
        title,
        re.IGNORECASE
    ))

    # 2. Multi-Company Roundup Container Check (Section 8 & 9, Test 2)
    # E.g. "Stocks in news: Biocon, Bank of Baroda, TCS, Sanofi India and Tata Capital..."
    if not is_primary_exchange_filing and not has_primary_catalyst:
        if re.search(r"\b(?:stocks\s+in\s+news|stocks\s+to\s+watch|buzzing\s+stocks|top\s+stocks\s+to\s+watch|stocks\s+to\s+track)\b", title, re.IGNORECASE):
            return False, "Discarded: multi-company market roundup article lacking single-company catalyst focus."
        
        parts = title.split(" - ")[0]
        if parts.count(",") >= 2 and any(conj in parts.lower() for conj in [" and ", " & ", "order sparks", "shares in focus", "details here"]):
            return False, "Discarded: multi-company roundup headline lacking single-company focus."

    # 3. Broker Target Price Check: Reject articles whose primary content is a broker recommendation
    # (unless an actual primary contract win or corporate action is the underlying catalyst)
    if (BROKER_REGEX.search(title) or BROKER_REGEX.search(text)) and not is_primary_exchange_filing:
        if not has_primary_catalyst and not re.search(r"\b(?:bags|secures|wins|contract|order|fda|acquires|plant|quarterly\s+results)\b", title, re.IGNORECASE):
            return False, "Discarded: broker target-price revision or recommendation without primary corporate catalyst."

    # 4. Pure Price Movement Check without Fundamental Catalyst (Section 18, Test 4)
    # E.g. "Company shares rise 8%", "stock rallies 5%", "locked in upper circuit" without operational reason
    if re.search(r"\b(?:shares?\s+(?:rise|rises|jump|jumps|surge|surges|fall|falls|slide|slides|gain|gains|slump|slumps|rally|rallies)\b|(?:hits?|locked\s+in)\s+(?:upper|lower)\s+circuit)\b", title, re.IGNORECASE):
        if not has_primary_catalyst and not re.search(r"\b(?:order|contract|epc|project|pat|profit|results|revenue|ebitda|fda|usfda|approval|acquisition|merger|capex|plant|tender|l1|deal|rating\s+upgrade|rating\s+downgrade|procurement)\b", text, re.IGNORECASE):
            return False, "Discarded: market price movement only; lacks identifiable underlying fundamental corporate catalyst."

    # 5. Clickbait and promotional lists
    if CLICKBAIT_REGEX.search(text) and not is_primary_exchange_filing and not has_primary_catalyst:
        return False, "Discarded: promotional clickbait or generic trading recommendation without verified corporate catalyst."

    # 6. Check routine compliance filings
    if ROUTINE_REGEX.search(text):
        if not (re.search(r"\b(?:order|contract|fda|acquisition|penalty|expansion)\b", text, re.I)):
            return False, "Discarded: routine administrative / compliance filing (board meet notice, trading window, duplicate share, etc.)."

    # 7. ESG Rating Rejection: non-debt sustainability assessment (Section 12 & 13)
    if re.search(r"\b(?:esg\s+rating|esg\s+score|esg\s+risk|esg\s+assessment)\b", text, re.IGNORECASE):
        return False, "Discarded: ESG rating disclosure; not a debt credit rating change."

    # 7.1 Credit Rating Gating: Reject routine reaffirmations without upgrade/downgrade
    if re.search(r"\b(?:credit\s+ratings?|ratings?\s+(?:agency|agencies)|ratings?\s+(?:upgrades?|downgrades?|reaffirms?)|debt\s+ratings?)\b", text, re.IGNORECASE) or ("rating" in text.lower() and any(w in text.lower() for w in ["crisil", "icra", "care", "india ratings", "fitch", "moody", "s&p", "reaffirmed", "upgrade", "downgrade"])):
        # Reject routine annual surveillance / reaffirmations without rating notch change
        if re.search(r"\b(?:reaffirmed|reaffirmation|reiterated|surveillance|withdrawn|withdrawal|no\s+change|maintains?\s+rating)\b", text, re.IGNORECASE):
            if not re.search(r"\b(?:upgrades?|upgraded|downgrades?|downgraded|rating\s+upgrade|rating\s+downgrade)\b", text, re.IGNORECASE):
                return False, "Discarded: routine credit rating reaffirmation / surveillance without rating change."

    # 8. Verify presence of fundamental business catalyst
    if MATERIAL_REGEX.search(text) or has_primary_catalyst:
        return True, "Accepted: contains substantive fundamental catalyst."

    return False, "Discarded: lacks identifiable fundamental business or financial catalyst."
