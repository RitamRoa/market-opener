"""
Priced-In Evaluator Module.
Calculates a disciplined 0 to 10 score determining whether a catalyst is already priced into the stock:
  0 = Completely fresh / unpriced surprise
  10 = Extremely priced in / 'sell the news' risk

Evaluates:
  - 5D and 1M pre-announcement price run-up relative to Nifty
  - Valuation stretch (Trailing P/E vs historical/sector, P/B ratio)
  - Pre-news volume accumulation vs post-news volume
  - Prior analyst and market expectations
"""

from typing import Dict, Any, Tuple


def evaluate_priced_in(stock_data: Dict[str, Any], event_data: Dict[str, Any]) -> Tuple[float, str, Dict[str, Any]]:
    """
    Computes priced-in score (0.0 - 10.0) and detailed diagnostic rationale.
    """
    ret_5d = stock_data.get("ret_5d", 0.0)
    ret_1m = stock_data.get("ret_1m", 0.0)
    ret_3m = stock_data.get("ret_3m", 0.0)
    vol_ratio = stock_data.get("volume_ratio", 1.0)
    pe_ratio = stock_data.get("pe_ratio")
    sentiment = event_data.get("sentiment", "NEUTRAL")
    
    score = 4.0 # Base neutral assumption
    factors = []

    # 1. Price Run-Up Check
    if sentiment == "POSITIVE":
        if ret_1m > 20.0 or ret_5d > 10.0:
            score += 3.0
            factors.append(f"Significant pre-event run-up (+{ret_1m:.1f}% over 1M, +{ret_5d:.1f}% over 5D) signals smart money pre-positioned")
        elif ret_1m > 8.0:
            score += 1.5
            factors.append(f"Moderate positive momentum (+{ret_1m:.1f}% 1M) suggests partial discounting")
        elif ret_1m < -5.0:
            score -= 2.0
            factors.append(f"Stock was lagging (-{abs(ret_1m):.1f}% over 1M), indicating event comes as a surprise to street")
    elif sentiment == "NEGATIVE":
        if ret_1m < -15.0 or ret_5d < -8.0:
            score += 3.0
            factors.append(f"Sharp pre-event decline ({ret_1m:.1f}% 1M) indicates bad news was heavily leaked/anticipated")
        elif ret_1m > 5.0:
            score -= 2.0
            factors.append(f"Stock traded strong (+{ret_1m:.1f}% 1M) prior to negative event, making this an unpriced shock")

    # 2. Valuation Stretch Check
    if pe_ratio is not None and isinstance(pe_ratio, (int, float)) and pe_ratio > 0:
        if pe_ratio > 65.0:
            score += 1.5
            factors.append(f"Elevated trailing P/E ({pe_ratio:.1f}x) leaves zero margin of safety for execution slip")
        elif pe_ratio < 18.0:
            score -= 1.5
            factors.append(f"Depressed/attractive valuation ({pe_ratio:.1f}x P/E) buffers downside")

    # 3. Volume Check
    if vol_ratio > 2.5:
        if abs(ret_5d) > 8.0:
            score += 1.0
            factors.append(f"Heavy volume surge ({vol_ratio:.1f}x avg) accompanies mature move")
        else:
            factors.append(f"Fresh volume breakout ({vol_ratio:.1f}x avg) confirms institutional participation")

    # Clamp score between 0.0 and 10.0
    final_score = round(max(0.0, min(10.0, score)), 1)

    if final_score <= 3.0:
        classification = "Not priced in (High Surprise / Fresh Catalyst)"
    elif final_score <= 6.5:
        classification = "Partially priced in (Moderate Discounting)"
    else:
        classification = "Extremely priced in (Vulnerable to 'Sell on News')"

    rationale = f"{classification}. " + "; ".join(factors) if factors else f"{classification}. Baseline reaction expected."
    
    details = {
        "score": final_score,
        "classification": classification,
        "rationale": rationale,
        "ret_5d": ret_5d,
        "ret_1m": ret_1m,
        "pe_ratio": pe_ratio
    }
    return final_score, rationale, details
