"""
Opportunity Scorer & Thesis Generator.
Calculates the multi-factor Opportunity Score (0-100), Sub-scores, Confidence,
and synthesizes balanced Bull & Bear cases with strict FACT/ANALYSIS/ESTIMATE verification tagging.
"""

from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


def score_deep_stock(analyzed_stock: Dict[str, Any], market_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes final opportunity scores and thesis according to Section 18:
      - News Materiality:       25%
      - Fundamental Impact:     20%
      - Surprise:               15%
      - Price Setup:            15%
      - Historical Reaction:    10%
      - Volume Confirmation:     5%
      - Sector/Market Support:   5%
      - Risk (Inverse/Mitig):    5%
    """
    materiality = analyzed_stock.get("materiality", 0.5)
    sentiment = analyzed_stock.get("sentiment", "NEUTRAL")
    fund_impact = analyzed_stock.get("fundamental_impact", {}).get("overall_impact", 5.0)
    priced_in = analyzed_stock.get("priced_in_score", 5.0)
    ret_1d = analyzed_stock.get("ret_1d", 0.0)
    ret_1m = analyzed_stock.get("ret_1m", 0.0)
    vol_ratio = analyzed_stock.get("volume_ratio", 1.0)
    pe_ratio = analyzed_stock.get("deep_financials", {}).get("pe_ratio")
    is_primary = analyzed_stock.get("is_primary", False)
    sources_count = len(analyzed_stock.get("sources", []))

    # 1. News Materiality Score (0-100)
    news_score = round(min(100.0, materiality * 100.0), 1)

    # 2. Fundamental Impact Score (0-100)
    fundamental_score = round(min(100.0, fund_impact * 10.0), 1)

    # 3. Surprise Score (0-100): High when priced_in is low
    surprise_score = round(max(0.0, (10.0 - priced_in) * 10.0), 1)

    # 4. Price Setup Score (0-100)
    # Rewards positive confirmation if sentiment is positive, or downside confirmation if negative
    if sentiment == "POSITIVE":
        if ret_1d > 0.5 and ret_1m < 15.0:
            price_setup_score = 85.0
        elif ret_1d > 0.0:
            price_setup_score = 70.0
        elif ret_1m > 30.0:
            price_setup_score = 40.0 # Overextended
        else:
            price_setup_score = 55.0
    elif sentiment == "NEGATIVE":
        if ret_1d < -1.0:
            price_setup_score = 80.0
        else:
            price_setup_score = 60.0
    else:
        price_setup_score = 50.0

    # 5. Historical Reaction Score (0-100)
    hist_str = analyzed_stock.get("historical_comparison", "")
    if "Insufficient" in hist_str:
        hist_reaction_score = 50.0
    else:
        hist_reaction_score = 75.0

    # 6. Volume Confirmation Score (0-100)
    if vol_ratio >= 2.0:
        volume_conf_score = 95.0
    elif vol_ratio >= 1.3:
        volume_conf_score = 75.0
    elif vol_ratio >= 0.8:
        volume_conf_score = 50.0
    else:
        volume_conf_score = 30.0

    # 7. Sector/Market Support Score (0-100)
    regime = market_context.get("regime", "Neutral")
    if "Bullish" in regime:
        market_support_score = 80.0 if sentiment == "POSITIVE" else 40.0
    elif "Bearish" in regime:
        market_support_score = 80.0 if sentiment == "NEGATIVE" else 40.0
    else:
        market_support_score = 60.0

    # 8. Risk Score (0-100, where higher means safer / lower downside risk)
    risk_deductions = 0.0
    if priced_in >= 7.5:
        risk_deductions += 25.0
    if pe_ratio and pe_ratio > 60:
        risk_deductions += 20.0
    if vol_ratio < 0.7:
        risk_deductions += 15.0
    risk_score = round(max(10.0, 100.0 - risk_deductions), 1)

    # Weighted Opportunity Score Calculation (Section 18)
    opportunity_score = round(
        (news_score * 0.25) +
        (fundamental_score * 0.20) +
        (surprise_score * 0.15) +
        (price_setup_score * 0.15) +
        (hist_reaction_score * 0.10) +
        (volume_conf_score * 0.05) +
        (market_support_score * 0.05) +
        (risk_score * 0.05),
        1
    )

    # Adjust for valuation trap & high priced-in score (Section 19 requirement)
    if sentiment == "POSITIVE" and priced_in >= 7.5 and (pe_ratio and pe_ratio > 50):
        opportunity_score = round(opportunity_score * 0.80, 1)

    # Confidence Score (0-100): Based on data verification (primary source, multiple sources, price history)
    conf = 60.0
    if is_primary:
        conf += 20.0
    if sources_count >= 2:
        conf += 10.0
    if analyzed_stock.get("valid_price", True):
        conf += 10.0
    confidence_score = min(95.0, conf)

    # Synthesize Bull and Bear cases
    bull_case, bear_case, timeframe = generate_thesis(analyzed_stock, opportunity_score, priced_in, pe_ratio)

    result = dict(analyzed_stock)
    result.update({
        "opportunity_score": opportunity_score,
        "news_score": news_score,
        "fundamental_score": fundamental_score,
        "price_setup_score": price_setup_score,
        "surprise_score": surprise_score,
        "risk_score": risk_score,
        "confidence_score": round(confidence_score, 1),
        "priced_in_score": priced_in,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "expected_timeframe": timeframe
    })
    return result


def generate_thesis(stock: Dict[str, Any], opp_score: float, priced_in: float, pe_ratio: Any) -> Tuple[str, str, str]:
    """
    Generates structured Bull and Bear cases with strict fact-check demarcation.
    """
    comp = stock.get("company", stock["symbol"])
    sym = stock["symbol"]
    ev_type = stock.get("event_type", "Event")
    event_title = stock.get("main_event", "")
    vol_ratio = stock.get("volume_ratio", 1.0)
    ret_1m = stock.get("ret_1m", 0.0)

    # Bull Case
    bull_points = [
        f"[FACT] Corporate event: {event_title}.",
        f"[ANALYSIS] Catalyst category '{ev_type}' provides tangible operational tailwind with overall fundamental impact score of {stock.get('fundamental_impact', {}).get('overall_impact', 5.0)}/10.",
        f"[ESTIMATE] If order conversion/execution holds, incremental revenue contribution can expand operating leverage over the next 2-4 quarters.",
    ]
    if priced_in <= 4.0:
        bull_points.append(f"[ANALYSIS] Priced-in score of only {priced_in}/10 means the street has not fully discounted this catalyst into current valuations.")
    if vol_ratio >= 1.5:
        bull_points.append(f"[FACT] Current trading volume is {vol_ratio:.1f}x its 20-day average, signaling institutional accumulation.")

    bull_case = " ".join(bull_points)

    # Bear Case
    bear_points = []
    if priced_in >= 7.0:
        bear_points.append(f"[ANALYSIS] High priced-in score of {priced_in}/10: stock experienced a {ret_1m:+.1f}% move over the last month, presenting severe 'sell on news' profit booking risk.")
    else:
        bear_points.append(f"[ANALYSIS] Market could treat this as an isolated milestone if follow-up quarterly order inflows or earnings do not demonstrate sequential expansion.")

    if pe_ratio and isinstance(pe_ratio, (int, float)) and pe_ratio > 45:
        bear_points.append(f"[FACT] Trailing P/E stands at {pe_ratio:.1f}x, leaving little cushion for execution delays or margin compression.")
    else:
        bear_points.append(f"[ANALYSIS] External input cost volatility and macro sector rotation could cap valuation re-rating.")

    bear_points.append("[ESTIMATE] Execution bottlenecks, client concentration, or general broader market weakness could delay thesis realization.")
    bear_case = " ".join(bear_points)

    # Expected Timeframe
    if ev_type in ["Contract / Order Win", "Acquisitions & M&A"]:
        timeframe = "Medium-Term (3 to 9 months)"
    elif ev_type in ["Corporate Results / Earnings", "Regulatory & Legal Action"]:
        timeframe = "Short-to-Medium Term (2 to 8 weeks)"
    else:
        timeframe = "Short-Term (1 to 4 weeks)"

    return bull_case, bear_case, timeframe
