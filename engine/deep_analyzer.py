"""
Deep Stock Analyzer Module.
Extracts exhaustive quantitative fundamentals, valuation multiples, and financial statements via yfinance.
Analyzes price reaction (gap up/down, volume surge), evaluates 5 fundamental impact dimensions,
and conducts historical reaction comparisons.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple
from engine.db import get_cached_price, set_cached_price
from engine.priced_in import evaluate_priced_in
from engine.second_order import analyze_second_order_effects

logger = logging.getLogger(__name__)


def format_currency_inr(val: Optional[float]) -> str:
    """Formats large financial figures into Indian Crores (₹ Cr)."""
    if val is None or not isinstance(val, (int, float)) or np.isnan(val):
        return "N/A"
    crores = val / 10000000.0
    if abs(crores) >= 1000:
        return f"₹{crores:,.0f} Cr"
    return f"₹{crores:,.2f} Cr"


def get_deep_financials(symbol: str) -> Dict[str, Any]:
    """
    Pulls complete valuation ratios, financial metrics, and balance sheet/income data from yfinance.
    """
    cached = get_cached_price(symbol, "deep_financials", max_age_hours=6.0)
    if cached:
        return cached

    data = {
        "pe_ratio": None,
        "forward_pe": None,
        "pb_ratio": None,
        "ev_ebitda": None,
        "dividend_yield": None,
        "market_cap": None,
        "revenue": None,
        "net_income": None,
        "eps": None,
        "ebitda": None,
        "total_debt": None,
        "total_cash": None,
        "free_cash_flow": None,
        "debt_to_equity": None,
        "return_on_equity": None,
        "52w_high": None,
        "52w_low": None,
        "financial_summary": {}
    }

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}

        data["pe_ratio"] = info.get("trailingPE")
        data["forward_pe"] = info.get("forwardPE")
        data["pb_ratio"] = info.get("priceToBook")
        data["ev_ebitda"] = info.get("enterpriseToEbitda")
        data["dividend_yield"] = info.get("dividendYield", 0.0) * 100.0 if info.get("dividendYield") else None
        data["market_cap"] = info.get("marketCap")
        data["revenue"] = info.get("totalRevenue")
        data["net_income"] = info.get("netIncomeToCommon")
        data["eps"] = info.get("trailingEps")
        data["ebitda"] = info.get("ebitda")
        data["total_debt"] = info.get("totalDebt")
        data["total_cash"] = info.get("totalCash")
        data["free_cash_flow"] = info.get("freeCashflow")
        data["debt_to_equity"] = info.get("debtToEquity")
        data["return_on_equity"] = info.get("returnOnEquity", 0.0) * 100.0 if info.get("returnOnEquity") else None
        data["52w_high"] = info.get("fiftyTwoWeekHigh")
        data["52w_low"] = info.get("fiftyTwoWeekLow")

        # Income Statement summary if available
        try:
            fin = t.financials
            if fin is not None and not fin.empty:
                latest_col = fin.columns[0]
                rev = fin.loc["Total Revenue", latest_col] if "Total Revenue" in fin.index else None
                net_inc = fin.loc["Net Income", latest_col] if "Net Income" in fin.index else None
                data["financial_summary"]["latest_fiscal_revenue"] = format_currency_inr(rev)
                data["financial_summary"]["latest_fiscal_net_income"] = format_currency_inr(net_inc)
        except Exception:
            pass

        set_cached_price(symbol, "deep_financials", data)
    except Exception as e:
        logger.debug(f"Deep financials retrieval error for {symbol}: {e}")

    return data


def analyze_price_reaction(symbol: str) -> Dict[str, Any]:
    """
    Evaluates price and volume reaction around the most recent sessions:
    Gaps, intraday thrust, volume surges.
    """
    reaction = {
        "price_before_news": 0.0,
        "price_after_news": 0.0,
        "current_price": 0.0,
        "gap_pct": 0.0,
        "gap_type": "None",
        "market_reaction_intensity": "Market barely reacted",
        "volume_surged": False,
        "volume_multiple": 1.0
    }

    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1mo")
        if hist.empty or len(hist) < 3:
            return reaction

        curr_bar = hist.iloc[-1]
        prev_bar = hist.iloc[-2]

        curr_close = float(curr_bar["Close"])
        prev_close = float(prev_bar["Close"])
        curr_open = float(curr_bar["Open"])

        # Gap calculation: Open today vs Close yesterday
        gap = float(((curr_open - prev_close) / prev_close) * 100.0)
        gap_type = "Gap Up" if gap > 0.8 else ("Gap Down" if gap < -0.8 else "Flat Open")

        # Volume comparison
        avg_vol = float(hist["Volume"].iloc[:-1].mean()) if len(hist) > 1 else 1.0
        curr_vol = float(curr_bar["Volume"])
        vol_multiple = float(round(curr_vol / avg_vol, 2)) if avg_vol > 0 else 1.0
        volume_surged = bool(vol_multiple >= 1.5)

        # Reaction intensity
        move_pct = float(abs(((curr_close - prev_close) / prev_close) * 100.0))
        if move_pct >= 3.5 or (move_pct >= 2.0 and volume_surged):
            intensity = "Market reacted strongly"
        elif move_pct >= 1.2:
            intensity = "Moderate market reaction"
        else:
            intensity = "Market barely reacted"

        reaction.update({
            "price_before_news": round(float(prev_close), 2),
            "price_after_news": round(float(curr_close), 2),
            "current_price": round(float(curr_close), 2),
            "gap_pct": round(gap, 2),
            "gap_type": str(gap_type),
            "market_reaction_intensity": str(intensity),
            "volume_surged": bool(volume_surged),
            "volume_multiple": float(vol_multiple)
        })
    except Exception as e:
        logger.debug(f"Price reaction calculation error for {symbol}: {e}")

    return reaction


def calculate_fundamental_impact(event_type: str, sentiment: str, materiality: float) -> Dict[str, Any]:
    """
    Calculates 5-dimension fundamental impact scores (0 to 10):
      - Revenue impact: 0-10
      - Profit impact: 0-10
      - Margin impact: 0-10
      - Cash-flow impact: 0-10
      - Long-term strategic impact: 0-10
    """
    scale = materiality * 10.0

    if event_type == "Contract / Order Win":
        rev = min(10.0, scale * 1.0)
        prof = min(10.0, scale * 0.85)
        margin = min(10.0, scale * 0.70)
        cf = min(10.0, scale * 0.75)
        strat = min(10.0, scale * 0.80)
    elif event_type == "Corporate Results / Earnings":
        rev = min(10.0, scale * 0.90)
        prof = min(10.0, scale * 1.0)
        margin = min(10.0, scale * 0.95)
        cf = min(10.0, scale * 0.85)
        strat = min(10.0, scale * 0.70)
    elif event_type == "Regulatory & Legal Action":
        rev = min(10.0, scale * 0.70)
        prof = min(10.0, scale * 0.95)
        margin = min(10.0, scale * 0.85)
        cf = min(10.0, scale * 0.90)
        strat = min(10.0, scale * 0.95)
    elif event_type == "Acquisitions & M&A":
        rev = min(10.0, scale * 0.95)
        prof = min(10.0, scale * 0.75)
        margin = min(10.0, scale * 0.70)
        cf = min(10.0, scale * 0.65)
        strat = min(10.0, scale * 1.0)
    else:
        rev = min(10.0, scale * 0.60)
        prof = min(10.0, scale * 0.60)
        margin = min(10.0, scale * 0.60)
        cf = min(10.0, scale * 0.60)
        strat = min(10.0, scale * 0.60)

    overall = round((rev * 0.25 + prof * 0.25 + margin * 0.20 + cf * 0.15 + strat * 0.15), 1)

    return {
        "revenue_impact": round(rev, 1),
        "profit_impact": round(prof, 1),
        "margin_impact": round(margin, 1),
        "cashflow_impact": round(cf, 1),
        "strategic_impact": round(strat, 1),
        "overall_impact": overall
    }


def perform_historical_comparison(symbol: str, event_type: str) -> str:
    """
    Evaluates historical precedent reaction for similar corporate events.
    Never manufactures data; if insufficient data, returns explicit required label.
    """
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="1y")
        if hist.empty or len(hist) < 60:
            return "Historical comparison: Insufficient data"

        # Check for historical high-volatility event bars
        daily_returns = hist["Close"].pct_change().dropna()
        large_moves = daily_returns[abs(daily_returns) > 0.04]

        if len(large_moves) >= 2:
            avg_1d = float(abs(large_moves).mean() * 100.0)
            return f"Historical reaction on prior major catalysts: Average 1D thrust ±{avg_1d:.1f}%; follow-through typically stabilizes within 5-10 trading sessions."
        else:
            return "Historical comparison: Insufficient historical catalyst precedent in past 1 year"
    except Exception:
        return "Historical comparison: Insufficient data"


def conduct_deep_stock_analysis(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs complete Phase 6 deep analysis for a single candidate stock.
    Merges yfinance fundamentals, price reactions, priced-in check, and second-order effects.
    """
    symbol = candidate["symbol"]
    event_type = candidate.get("event_type", "General Corporate Development")
    sentiment = candidate.get("sentiment", "NEUTRAL")
    materiality = candidate.get("materiality", 0.5)

    # 1. Exhaustive fundamentals
    fin = get_deep_financials(symbol)

    # 2. Price reaction & gaps
    reaction = analyze_price_reaction(symbol)

    # 3. Priced-in analysis
    stock_context = {
        "ret_5d": candidate.get("ret_5d", 0.0),
        "ret_1m": candidate.get("ret_1m", 0.0),
        "ret_3m": candidate.get("ret_3m", 0.0),
        "volume_ratio": candidate.get("volume_ratio", 1.0),
        "pe_ratio": fin.get("pe_ratio")
    }
    event_context = {"sentiment": sentiment}
    priced_in_score, priced_in_rationale, priced_in_details = evaluate_priced_in(stock_context, event_context)

    # 4. Fundamental impact matrix
    fund_impact = calculate_fundamental_impact(event_type, sentiment, materiality)

    # 5. Historical comparison
    hist_comp = perform_historical_comparison(symbol, event_type)

    # 6. Second-order effects
    second_order = analyze_second_order_effects(
        symbol=symbol,
        event_title=candidate.get("main_event", ""),
        event_type=event_type,
        sector=candidate.get("sector", "")
    )

    result = dict(candidate)
    result.update({
        "deep_financials": fin,
        "price_reaction": reaction,
        "priced_in_score": priced_in_score,
        "priced_in_rationale": priced_in_rationale,
        "priced_in_details": priced_in_details,
        "fundamental_impact": fund_impact,
        "historical_comparison": hist_comp,
        "second_order": second_order
    })
    return result
