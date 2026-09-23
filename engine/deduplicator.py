"""
News Deduplication & Multi-Source Clustering Module.
Authoritatively collapses multiple media reports covering the same underlying corporate event
into a single canonical corporate event before scoring and synthesis.
Picks the single most detailed article as the basis for the summary — zero concatenation.
Filters out clickbait, promotional lists, and generic market roundups.
"""

import re
import hashlib
from typing import List, Dict, Any, Tuple, Optional, Set
from collections import defaultdict

NOISE_PATTERNS = [
    r"\btop\s+\d+\s+stocks\b",
    r"\bstocks\s+to\s+buy\b",
    r"\bhot\s+stocks\b",
    r"\bwealth\s+creators\b",
    r"\bmultibagger\s+stocks?\b",
    r"\bexpert\s+recommendations?\b",
    r"\btrading\s+ideas\b",
    r"\bstock\s+market\s+live\b",
    r"\bclosing\s+bell\b",
    r"\bopening\s+bell\b",
    r"\bweekly\s+wrap\b",
    r"\bmarket\s+cues\b",
    r"\bmarket\s+live\b",
    r"\bgift\s+nifty\b",
    r"\bstock\s+picks?\b",
    r"\bhow\s+to\s+invest\b",
    r"\bwhere\s+to\s+invest\b",
    r"\b\d+\s+(?:stocks|companies|shares)\s+(?:for|to|with|have)\b",
    r"\b\d+\s+stocks\s+for\s+dividends\b",
    r"\bdividend\s+record\s+dates?\b",
    r"\bex-dividend\b",
    r"\btrading\s+ex-dividend\b",
    r"\bdividend\s+alert\b",
    r"\bupcoming\s+dividends\b",
    r"\bcorporate\s+actions?\s+this\s+week\b",
    r"\bpenny\s+stocks?\b",
    r"\bpenny\s+stock\s+under\s+\d+\b",
]

NOISE_REGEX = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)


def is_noise_article(title: str, summary: str = "") -> bool:
    """
    Identifies clickbait, promotional lists, and generic roundups lacking company-specific catalysts.
    """
    text = f"{title} {summary}".lower()
    if NOISE_REGEX.search(text):
        return True
    
    # Very short titles with no informative content
    words = title.split()
    if len(words) < 4:
        return True

    return False


def tokenize_text(text: str) -> Set[str]:
    """Extracts lowercase alphabetic tokens of length >= 3."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    stop_words = {
        "the", "and", "for", "with", "this", "that", "from", "shares", "stock", "stocks", 
        "india", "ltd", "limited", "company", "announced", "announces", "secures", "wins", 
        "bags", "order", "contract", "worth", "crore", "after", "over"
    }
    return {w for w in words if w not in stop_words}


def calculate_similarity(tokens1: Set[str], tokens2: Set[str]) -> float:
    """Calculates Jaccard similarity between two token sets."""
    if not tokens1 or not tokens2:
        return 0.0
    intersection = len(tokens1.intersection(tokens2))
    union = len(tokens1.union(tokens2))
    return intersection / union if union > 0 else 0.0


def extract_clustering_features(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts structured clustering features from an article:
      - canonical_symbol: stripped symbol (e.g. 'ORIANA', 'MAZDOCK')
      - company_norm: normalized company name
      - event_type: canonical event category
      - amounts: set of detected monetary amounts in Cr
      - units: set of detected capacity units (e.g. '900mw', '1.8gwh', 'bess')
      - counterparty: detected client/counterparty
      - detail_score: numerical measure of article completeness and precision
    """
    title = item.get("title", "")
    summary = item.get("summary", "")
    full_text = f"{title} {summary}".lower()

    # Symbol normalization
    raw_sym = item.get("symbol") or ""
    clean_sym = raw_sym.upper().replace(".NS", "").replace(".BO", "").replace(".BSE", "").strip()

    # Company name normalization
    raw_comp = item.get("company_name") or ""
    from engine.equity_master import normalize_corporate_name
    comp_norm = normalize_corporate_name(raw_comp)

    # Classify event type
    from engine.fna_analyzer import classify_event_direction_and_type
    ev_type, _, _ = classify_event_direction_and_type(f"{title} {summary}")

    # Extract amounts (in Cr)
    amounts = set()
    amt_matches = re.findall(r"(?:rs\.?|₹|inr)\s*(\d+(?:[.,]\d+)?)\s*(?:cr|crore)?", full_text)
    for m in amt_matches:
        try:
            val = float(m.replace(",", ""))
            amounts.add(round(val, 1))
        except ValueError:
            pass

    # Extract physical capacity / units (e.g. 900 MW, 1.8 GWh, 1800 MWh, BESS)
    units = set()
    unit_matches = re.findall(r"\b(\d+(?:[.,]\d+)?\s*(?:mw|gw|mwh|gwh|bess|mtpa|tpd|tonne|km))\b", full_text)
    for u in unit_matches:
        units.add(re.sub(r"\s+", "", u.lower()))
    if "bess" in full_text:
        units.add("bess")

    # Extract Counterparty
    counterparty = ""
    cp_match = re.search(r"\b(?:from|with|awarded\s+by|selected\s+by)\s+([A-Z][A-Za-z0-9&.\-']+(?:\s+[A-Za-z0-9&.\-']+){0,2})", f"{title} {summary}")
    if cp_match:
        cand_cp = cp_match.group(1).lower().strip()
        if not any(w in cand_cp for w in ["share", "order", "contract", "crore", "rs", "inr", "percent"]):
            counterparty = cand_cp

    # Detail score: prioritizes official primary disclosures, concrete figures, and rich factual summaries
    detail_score = 0
    if item.get("is_primary"):
        detail_score += 50
    if amounts:
        detail_score += 25
    if units:
        detail_score += 15
    if counterparty:
        detail_score += 15
    # Information density (length of summary, capped)
    detail_score += min(30, len(summary.strip()) // 10)

    tokens = tokenize_text(f"{title} {summary}")

    return {
        "symbol": clean_sym,
        "company_norm": comp_norm,
        "event_type": ev_type,
        "amounts": amounts,
        "units": units,
        "counterparty": counterparty,
        "detail_score": detail_score,
        "tokens": tokens,
        "date": (item.get("published_at") or item.get("news_date") or "")[:10]
    }


def is_same_canonical_event(feat1: Dict[str, Any], feat2: Dict[str, Any]) -> bool:
    """
    Authoritatively determines if two articles refer to the exact same canonical corporate development:
      1. Must refer to the same corporate entity (same symbol or normalized company name).
      2. Must share the same event type (or both are commercial agreements/contracts).
      3. Must match key figures (amounts, physical units, counterparty) OR have high semantic token similarity.
    """
    # 1. Entity check: Symbols must match if both present, or company norm must match
    entity_match = False
    if feat1["symbol"] and feat2["symbol"]:
        entity_match = (feat1["symbol"] == feat2["symbol"])
    elif feat1["company_norm"] and feat2["company_norm"]:
        entity_match = (feat1["company_norm"] == feat2["company_norm"])
    elif feat1["symbol"] or feat2["symbol"]:
        # One has symbol, check if other company norm aligns
        entity_match = False

    if not entity_match:
        return False

    # 2. Event type check
    type1 = feat1["event_type"]
    type2 = feat2["event_type"]
    same_type = (type1 == type2)
    # Related commercial contract types
    contract_types = {"ORDER_CONTRACT", "STRATEGIC_DEAL", "OPERATIONAL_INITIATIVE"}
    if type1 in contract_types and type2 in contract_types:
        same_type = True

    if not same_type:
        return False

    # 3. Key figures matching:
    # A. Amounts match (within 5% tolerance or exact rounded Cr)
    shared_amounts = feat1["amounts"].intersection(feat2["amounts"])
    if shared_amounts:
        return True
    if feat1["amounts"] and feat2["amounts"]:
        for a1 in feat1["amounts"]:
            for a2 in feat2["amounts"]:
                if a1 > 0 and a2 > 0 and abs(a1 - a2) / max(a1, a2) < 0.05:
                    return True

    # B. Physical units match (e.g. both refer to 900mw or bess)
    shared_units = feat1["units"].intersection(feat2["units"])
    if shared_units:
        # If both explicitly mention BESS or a specific MW capacity, it's the same contract
        return True

    # C. Counterparty matches (e.g. both mention MSEDCL or Saudi Aramco)
    if feat1["counterparty"] and feat2["counterparty"]:
        if feat1["counterparty"] in feat2["counterparty"] or feat2["counterparty"] in feat1["counterparty"]:
            return True

    # D. High token similarity on headline/summary (Jaccard >= 0.40)
    sim = calculate_similarity(feat1["tokens"], feat2["tokens"])
    if sim >= 0.40:
        return True

    # E. Same date and non-trivial token overlap (>= 0.28)
    if feat1["date"] and feat2["date"] and feat1["date"] == feat2["date"] and sim >= 0.28:
        return True

    return False


def deduplicate_and_cluster_news(news_items: List[Dict[str, Any]], similarity_threshold: float = 0.50) -> List[Dict[str, Any]]:
    """
    Authoritatively clusters duplicate articles covering the same corporate event before scoring/synthesis.
    Clusters all articles referring to the same entity + same event type + same key figures into one canonical event.
    Picks the single most detailed article as the basis for the canonical summary — zero concatenation.
    """
    filtered_items = []
    for item in news_items:
        title = item.get("title", "")
        summary = item.get("summary", "")
        if not is_noise_article(title, summary):
            filtered_items.append(item)

    clusters: List[Dict[str, Any]] = []

    for item in filtered_items:
        item_feat = extract_clustering_features(item)
        matched_cluster = None

        for cluster in clusters:
            cluster_feat = cluster["features"]
            if is_same_canonical_event(item_feat, cluster_feat):
                matched_cluster = cluster
                break

        if matched_cluster:
            # 1. Accumulate unique sources and URLs
            source_name = item.get("source", "Web")
            if source_name and source_name not in matched_cluster["sources"]:
                matched_cluster["sources"].append(source_name)

            url = item.get("url")
            if url and url not in matched_cluster["source_urls"]:
                matched_cluster["source_urls"].append(url)

            matched_cluster["articles_count"] += 1

            # 2. Pick the single most detailed article as the basis for title and summary — do NOT concatenate!
            if item_feat["detail_score"] > matched_cluster["best_detail_score"] or item.get("is_primary"):
                matched_cluster["title"] = item["title"]
                matched_cluster["summary"] = item.get("summary", "")
                matched_cluster["published_at"] = item.get("published_at") or matched_cluster.get("published_at")
                matched_cluster["best_detail_score"] = item_feat["detail_score"]
                if item.get("symbol"):
                    matched_cluster["symbol"] = item["symbol"]
                if item.get("company_name"):
                    matched_cluster["company_name"] = item["company_name"]
                if item.get("is_primary"):
                    matched_cluster["is_primary"] = True

            # Merge tokens and key figures into cluster features
            matched_cluster["features"]["tokens"].update(item_feat["tokens"])
            matched_cluster["features"]["amounts"].update(item_feat["amounts"])
            matched_cluster["features"]["units"].update(item_feat["units"])
            if not matched_cluster["features"]["counterparty"] and item_feat["counterparty"]:
                matched_cluster["features"]["counterparty"] = item_feat["counterparty"]

        else:
            # Create new canonical cluster
            source_name = item.get("source", "Web")
            source_url = item.get("url")
            title = item.get("title", "")
            clusters.append({
                "cluster_id": hashlib.md5(f"{item_feat['symbol']}_{title}".encode("utf-8")).hexdigest()[:12],
                "title": title,
                "summary": item.get("summary", ""),
                "published_at": item.get("published_at", ""),
                "symbol": item.get("symbol"),
                "company_name": item.get("company_name"),
                "sources": [source_name] if source_name else ["Web"],
                "source_urls": [source_url] if source_url else [],
                "articles_count": 1,
                "is_primary": item.get("is_primary", False),
                "features": item_feat,
                "best_detail_score": item_feat["detail_score"]
            })

    return clusters
