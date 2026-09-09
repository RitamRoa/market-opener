"""
Market Context Engine for Indian Equities.
Fetches NIFTY 50, BANK NIFTY, India VIX, USD/INR, Brent Crude, Gold, and US markets via yfinance.
Calculates market regime (Bullish/Bearish/Neutral/Risk-On/Risk-Off/High Volatility) and macro drivers.
"""

import logging
from typing import Dict, Any
import yfinance as yf
from engine.db import get_cached_price, set_cached_price

logger = logging.getLogger(__name__)

BENCHMARKS = {
    "nifty": "^NSEI",
    "bank_nifty": "^NSEBANK",
    "sensex": "^BSESN",
    "vix": "^INDIAVIX",
    "usdinr": "INR=X",
    "brent": "BZ=F",
    "gold": "GC=F",
    "sp500": "^GSPC"
}


def get_market_context() -> Dict[str, Any]:
    """
    Fetches benchmark indices and computes market regime and macro drivers.
    Returns structured market context dictionary.
    """
    # Check cache first
    cached = get_cached_price("MARKET_CONTEXT", "context", max_age_hours=0.5)
    if cached:
        return cached

    results = {}
    for key, ticker_symbol in BENCHMARKS.items():
        try:
            t = yf.Ticker(ticker_symbol)
            hist = t.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                current_price = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2])
                change_pct = ((current_price - prev_close) / prev_close) * 100.0
                results[key] = {
                    "price": round(current_price, 2),
                    "change_pct": round(change_pct, 2),
                    "prev_close": round(prev_close, 2)
                }
            elif not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
                results[key] = {
                    "price": round(current_price, 2),
                    "change_pct": 0.0,
                    "prev_close": round(current_price, 2)
                }
            else:
                results[key] = {"price": 0.0, "change_pct": 0.0, "prev_close": 0.0}
        except Exception as e:
            logger.warning(f"Error fetching benchmark {key} ({ticker_symbol}): {e}")
            results[key] = {"price": 0.0, "change_pct": 0.0, "prev_close": 0.0}

    # Evaluate Market Regime
    nifty_change = results.get("nifty", {}).get("change_pct", 0.0)
    bank_change = results.get("bank_nifty", {}).get("change_pct", 0.0)
    vix_val = results.get("vix", {}).get("price", 14.0)
    brent_change = results.get("brent", {}).get("change_pct", 0.0)

    regimes = []
    if vix_val >= 20.0:
        regimes.append("High Volatility")
    
    if nifty_change > 0.6 and bank_change > 0.5:
        regimes.append("Bullish")
        regimes.append("Risk-On")
    elif nifty_change < -0.6 and bank_change < -0.5:
        regimes.append("Bearish")
        regimes.append("Risk-Off")
    else:
        regimes.append("Neutral")

    primary_regime = " / ".join(regimes) if regimes else "Neutral"

    # Identify major market drivers
    drivers = []
    if abs(brent_change) > 1.5:
        drivers.append(f"Crude oil swing ({brent_change:+.1f}%) impacting energy, paints, and transport costs")
    if vix_val > 18.0:
        drivers.append(f"Elevated India VIX at {vix_val:.1f} indicating defensive positioning")
    elif vix_val < 13.0:
        drivers.append(f"Subdued India VIX at {vix_val:.1f} showing market complacency")
    
    if abs(nifty_change) > 0.75:
        direction = "rally" if nifty_change > 0 else "pullback"
        drivers.append(f"NIFTY broad-based {direction} ({nifty_change:+.2f}%)")
    
    if abs(bank_change) > 0.75:
        drivers.append(f"Banking sector divergence/momentum ({bank_change:+.2f}%)")

    if not drivers:
        drivers.append("Range-bound session with stock-specific news driving selective outperformance")

    context = {
        "regime": primary_regime,
        "nifty": results.get("nifty", {"price": 23800.0, "change_pct": 0.0}),
        "bank_nifty": results.get("bank_nifty", {"price": 51000.0, "change_pct": 0.0}),
        "vix": results.get("vix", {"price": 14.5, "change_pct": 0.0}),
        "brent": results.get("brent", {"price": 82.0, "change_pct": 0.0}),
        "gold": results.get("gold", {"price": 2400.0, "change_pct": 0.0}),
        "usdinr": results.get("usdinr", {"price": 83.5, "change_pct": 0.0}),
        "sp500": results.get("sp500", {"price": 5500.0, "change_pct": 0.0}),
        "drivers": drivers
    }

    # Store in cache
    set_cached_price("MARKET_CONTEXT", "context", context)
    return context
