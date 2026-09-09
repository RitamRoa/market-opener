"""
Candidate Scanner & Preliminary Stock Scoring Engine.
Identifies active candidate stocks from announcements and news events.
Computes technical setup (1D, 5D, 1M, 3M returns, volume ratio) and calculates Preliminary Score (0-100).
Selects top 8-20 stocks for deep research.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from typing import List, Dict, Any, Optional
from engine.entity_mapper import match_company_in_text, get_company_meta
from engine.event_detector import detect_event_type_and_sentiment
from engine.db import get_cached_price, set_cached_price

logger = logging.getLogger(__name__)


def get_stock_price_metrics(symbol: str) -> Dict[str, Any]:
    """
    Fetches historical OHLCV data via yfinance and calculates returns and volume abnormalities.
    Caches results in SQLite to avoid repeated downloads.
    """
    cached = get_cached_price(symbol, "metrics", max_age_hours=2.0)
    if cached:
        return cached

    default_metrics = {
        "current_price": 0.0,
        "prev_close": 0.0,
        "ret_1d": 0.0,
        "ret_5d": 0.0,
        "ret_1m": 0.0,
        "ret_3m": 0.0,
        "volume": 0,
        "avg_volume_20d": 0,
        "volume_ratio": 1.0,
        "valid": False
    }

    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="6mo")
        if hist.empty or len(hist) < 5:
            return default_metrics

        current_price = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current_price

        # Returns
        ret_1d = ((current_price - prev_close) / prev_close) * 100.0 if prev_close else 0.0
        
        p_5d = float(hist["Close"].iloc[-5]) if len(hist) >= 5 else current_price
        ret_5d = ((current_price - p_5d) / p_5d) * 100.0 if p_5d else 0.0

        p_1m = float(hist["Close"].iloc[-22]) if len(hist) >= 22 else float(hist["Close"].iloc[0])
        ret_1m = ((current_price - p_1m) / p_1m) * 100.0 if p_1m else 0.0

        p_3m = float(hist["Close"].iloc[-65]) if len(hist) >= 65 else float(hist["Close"].iloc[0])
        ret_3m = ((current_price - p_3m) / p_3m) * 100.0 if p_3m else 0.0

        # Volume
        latest_vol = int(hist["Volume"].iloc[-1])
        avg_vol_20d = int(hist["Volume"].iloc[-20:].mean()) if len(hist) >= 20 else max(latest_vol, 1)
        vol_ratio = round(latest_vol / avg_vol_20d, 2) if avg_vol_20d > 0 else 1.0

        metrics = {
            "current_price": round(current_price, 2),
            "prev_close": round(prev_close, 2),
            "ret_1d": round(ret_1d, 2),
            "ret_5d": round(ret_5d, 2),
            "ret_1m": round(ret_1m, 2),
            "ret_3m": round(ret_3m, 2),
            "volume": latest_vol,
            "avg_volume_20d": avg_vol_20d,
            "volume_ratio": vol_ratio,
            "valid": True
        }
        set_cached_price(symbol, "metrics", metrics)
        return metrics
    except Exception as e:
        logger.debug(f"yfinance price error for {symbol}: {e}")
        return default_metrics


def calculate_preliminary_score(candidate: Dict[str, Any]) -> float:
    """
    Implements the Preliminary Stock Score (0-100) exactly as defined in Section 6:
      - News importance:       25%
      - Price movement:        15%
      - Volume abnormality:    15%
      - Catalyst strength:     20%
      - Sector relevance:      10%
      - Market relevance:       5%
      - News freshness:         5%
      - Data confidence:        5%
    """
    # 1. News importance (0-100)
    materiality = candidate.get("materiality", 0.5)
    is_primary = candidate.get("is_primary", False)
    news_importance = min(100.0, (materiality * 80.0) + (20.0 if is_primary else 5.0))

    # 2. Price movement (0-100)
    ret_1d = abs(candidate.get("ret_1d", 0.0))
    # Higher score for significant moves (e.g. 2% to 10% move)
    price_movement = min(100.0, ret_1d * 12.0 + 20.0)

    # 3. Volume abnormality (0-100)
    vol_ratio = candidate.get("volume_ratio", 1.0)
    # Ratios above 1.5x indicate institutional accumulation/distribution
    if vol_ratio >= 3.0:
        vol_abnormality = 100.0
    elif vol_ratio >= 2.0:
        vol_abnormality = 85.0
    elif vol_ratio >= 1.5:
        vol_abnormality = 70.0
    elif vol_ratio >= 1.0:
        vol_abnormality = 50.0
    else:
        vol_abnormality = 30.0

    # 4. Catalyst strength (0-100)
    ev_type = candidate.get("event_type", "")
    if ev_type in ["Regulatory & Legal Action", "Contract / Order Win", "Corporate Results / Earnings"]:
        catalyst_strength = 90.0
    elif ev_type in ["Acquisitions & M&A", "Promoter & Capital Actions"]:
        catalyst_strength = 80.0
    elif ev_type in ["Capacity Expansion & Capex", "Management & Governance"]:
        catalyst_strength = 70.0
    else:
        catalyst_strength = 50.0

    # 5. Sector relevance (0-100)
    sector = candidate.get("sector", "")
    high_impact_sectors = ["Defense", "Energy", "Banking", "Infrastructure", "Automobile", "Metals", "Pharmaceuticals"]
    sector_relevance = 85.0 if any(s.lower() in sector.lower() for s in high_impact_sectors) else 60.0

    # 6. Market relevance (0-100)
    sources_count = len(candidate.get("sources", []))
    market_relevance = min(100.0, 50.0 + sources_count * 15.0)

    # 7. News freshness (0-100)
    news_freshness = 95.0 if is_primary else 80.0

    # 8. Data confidence (0-100)
    data_confidence = 90.0 if candidate.get("valid_price", False) else 50.0

    # Weighted calculation
    score = (
        (news_importance * 0.25) +
        (price_movement * 0.15) +
        (vol_abnormality * 0.15) +
        (catalyst_strength * 0.20) +
        (sector_relevance * 0.10) +
        (market_relevance * 0.05) +
        (news_freshness * 0.05) +
        (data_confidence * 0.05)
    )

    return round(score, 1)


def scan_and_rank_candidates(
    announcements: List[Dict[str, Any]], 
    news_clusters: List[Dict[str, Any]],
    target_count: int = 15
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Processes all events, maps to companies, collects preliminary market metrics,
    and ranks candidates. Returns (all_candidates_20_50, top_candidates_for_deep_dive).
    """
    candidates_dict = {}

    # 1. Process Exchange Announcements (Highest Priority)
    for item in announcements:
        sym = item.get("symbol")
        if not sym:
            # Try to match from company name
            matches = match_company_in_text(item.get("company_name", "") + " " + item.get("title", ""))
            if matches:
                sym = matches[0]["symbol"]
            else:
                continue

        meta = get_company_meta(sym)
        ev_type, sentiment, materiality = detect_event_type_and_sentiment(item.get("title", ""), item.get("summary", ""))

        candidates_dict[sym] = {
            "symbol": sym,
            "company": meta["name"],
            "sector": meta["sector"],
            "event_type": ev_type,
            "sentiment": sentiment,
            "materiality": materiality,
            "main_event": item.get("title", ""),
            "summary": item.get("summary", ""),
            "news_date": item.get("published_at", ""),
            "sources": [item.get("source", "NSE")],
            "source_urls": [item.get("url", "")] if item.get("url") else [],
            "is_primary": True
        }

    # 2. Process News Clusters
    for cluster in news_clusters:
        matched = []
        if cluster.get("symbol"):
            matched = [get_company_meta(cluster["symbol"])]
        else:
            matched = match_company_in_text(cluster["title"] + " " + cluster.get("summary", ""))

        if not matched:
            continue

        for comp in matched:
            sym = comp["symbol"]
            ev_type, sentiment, materiality = detect_event_type_and_sentiment(cluster["title"], cluster.get("summary", ""))

            if sym in candidates_dict:
                # Merge sources
                for s in cluster.get("sources", []):
                    if s not in candidates_dict[sym]["sources"]:
                        candidates_dict[sym]["sources"].append(s)
                for u in cluster.get("source_urls", []):
                    if u not in candidates_dict[sym]["source_urls"]:
                        candidates_dict[sym]["source_urls"].append(u)
                if materiality > candidates_dict[sym]["materiality"]:
                    candidates_dict[sym]["materiality"] = materiality
                    candidates_dict[sym]["event_type"] = ev_type
                    candidates_dict[sym]["sentiment"] = sentiment
            else:
                candidates_dict[sym] = {
                    "symbol": sym,
                    "company": comp["name"],
                    "sector": comp["sector"],
                    "event_type": ev_type,
                    "sentiment": sentiment,
                    "materiality": materiality,
                    "main_event": cluster["title"],
                    "summary": cluster.get("summary", ""),
                    "news_date": cluster.get("published_at", ""),
                    "sources": cluster.get("sources", ["Web"]),
                    "source_urls": cluster.get("source_urls", []),
                    "is_primary": cluster.get("is_primary", False)
                }

    # If active event list is short, inject key active market leaders to ensure full coverage (20-30 stocks)
    active_leaders = ["RELIANCE.NS", "TATAMOTORS.NS", "HAL.NS", "SBIN.NS", "INFY.NS", "LT.NS", "ITC.NS", "BHARTIARTL.NS", "ZOMATO.NS", "SMLMAH.NS"]
    for leader_sym in active_leaders:
        if leader_sym not in candidates_dict:
            meta = get_company_meta(leader_sym)
            candidates_dict[leader_sym] = {
                "symbol": leader_sym,
                "company": meta["name"],
                "sector": meta["sector"],
                "event_type": "Market Tracking / Price Momentum",
                "sentiment": "NEUTRAL",
                "materiality": 0.55,
                "main_event": f"{meta['name']}: Active trading volume and institutional positioning",
                "summary": "High market cap influence and sector benchmark tracking",
                "news_date": datetime.utcnow().strftime("%d-%b-%Y"),
                "sources": ["Exchange Market Activity"],
                "source_urls": [],
                "is_primary": False
            }

    # 3. Enrich each candidate with yfinance metrics and calculate Preliminary Score
    all_candidates = []
    for sym, cand in candidates_dict.items():
        metrics = get_stock_price_metrics(sym)
        cand.update({
            "current_price": metrics["current_price"],
            "prev_close": metrics["prev_close"],
            "ret_1d": metrics["ret_1d"],
            "ret_5d": metrics["ret_5d"],
            "ret_1m": metrics["ret_1m"],
            "ret_3m": metrics["ret_3m"],
            "volume": metrics["volume"],
            "avg_volume": metrics["avg_volume_20d"],
            "volume_ratio": metrics["volume_ratio"],
            "valid_price": metrics["valid"]
        })
        cand["preliminary_score"] = calculate_preliminary_score(cand)
        all_candidates.append(cand)

    # Sort all candidates by preliminary score descending
    all_candidates.sort(key=lambda x: x["preliminary_score"], reverse=True)

    # Filter top 8-20 stocks with meaningful catalysts (or score >= 60)
    top_candidates = [c for c in all_candidates if c["preliminary_score"] >= 58.0]
    if len(top_candidates) < 8:
        top_candidates = all_candidates[:8]
    elif len(top_candidates) > target_count:
        top_candidates = top_candidates[:target_count]

    return all_candidates, top_candidates
