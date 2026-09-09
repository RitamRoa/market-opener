"""
News Deduplication & Noise Filter Module.
Collapses multiple media reports into single canonical corporate events.
Filters out clickbait, promotional lists, and generic market roundups without underlying corporate catalysts.
"""

import re
import hashlib
from typing import List, Dict, Any, Tuple
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
    r"\bwhere\s+to\s+invest\b"
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


def tokenize_text(text: str) -> set:
    """Extracts lowercase alphabetic tokens of length >= 3."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    stop_words = {"the", "and", "for", "with", "this", "that", "from", "shares", "stock", "stocks", "india", "ltd", "limited", "company"}
    return {w for w in words if w not in stop_words}


def calculate_similarity(tokens1: set, tokens2: set) -> float:
    """Calculates Jaccard similarity between two token sets."""
    if not tokens1 or not tokens2:
        return 0.0
    intersection = len(tokens1.intersection(tokens2))
    union = len(tokens1.union(tokens2))
    return intersection / union if union > 0 else 0.0


def deduplicate_and_cluster_news(news_items: List[Dict[str, Any]], similarity_threshold: float = 0.35) -> List[Dict[str, Any]]:
    """
    Clusters duplicate articles reporting the exact same event from multiple publishers.
    Stores all unique sources under a single canonical event.
    """
    filtered_items = []
    for item in news_items:
        title = item.get("title", "")
        summary = item.get("summary", "")
        if not is_noise_article(title, summary):
            filtered_items.append(item)

    clusters: List[Dict[str, Any]] = []

    for item in filtered_items:
        title = item.get("title", "")
        tokens = tokenize_text(title)
        item_symbol = item.get("symbol")

        matched_cluster = None
        for cluster in clusters:
            # If both have assigned symbols and they mismatch, cannot be in same cluster
            if item_symbol and cluster.get("symbol") and item_symbol != cluster.get("symbol"):
                continue

            sim = calculate_similarity(tokens, cluster["tokens"])
            if sim >= similarity_threshold:
                matched_cluster = cluster
                break

        if matched_cluster:
            # Add source and URL to existing cluster
            source_name = item.get("source", "Web")
            if source_name not in matched_cluster["sources"]:
                matched_cluster["sources"].append(source_name)
            
            url = item.get("url")
            if url and url not in matched_cluster["source_urls"]:
                matched_cluster["source_urls"].append(url)
            
            # Prefer primary exchange announcement title if available
            if item.get("is_primary"):
                matched_cluster["title"] = item["title"]
                matched_cluster["is_primary"] = True
                if item.get("symbol"):
                    matched_cluster["symbol"] = item["symbol"]
            
            matched_cluster["articles_count"] += 1
            # Merge tokens for broader cluster coverage
            matched_cluster["tokens"].update(tokens)
        else:
            # Create new canonical cluster
            source_name = item.get("source", "Web")
            source_url = item.get("url")
            clusters.append({
                "cluster_id": hashlib.md5(title.encode("utf-8")).hexdigest()[:12],
                "title": title,
                "summary": item.get("summary", ""),
                "published_at": item.get("published_at", ""),
                "symbol": item.get("symbol"),
                "company_name": item.get("company_name"),
                "tokens": tokens,
                "sources": [source_name],
                "source_urls": [source_url] if source_url else [],
                "articles_count": 1,
                "is_primary": item.get("is_primary", False)
            })

    return clusters
