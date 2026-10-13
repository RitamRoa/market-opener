import sys, os
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
from datetime import datetime, timedelta
from engine.equity_master import resolve_entity

def get_market_prices(symbol, date_str):
    """
    Returns (price_930, price_1500, status_note) for a given symbol and date.
    Handles NSE, BSE fallback, 5m bars, 1h bars, and weekend/holiday.
    """
    clean_sym = symbol.strip()
    # Resolve BSE scrip codes to NSE ticker if possible
    if clean_sym.endswith(".BO") or clean_sym.isdigit():
        resolved_sym, _ = resolve_entity(clean_sym)
        if resolved_sym and not resolved_sym.isdigit():
            clean_sym = f"{resolved_sym}.NS"
        elif not clean_sym.endswith(".BO"):
            clean_sym = f"{clean_sym}.BO"
    elif not clean_sym.endswith(".NS") and not clean_sym.endswith(".BO"):
        clean_sym = f"{clean_sym}.NS"

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    is_weekend = dt.weekday() in [5, 6]
    next_day = (dt + timedelta(days=1)).strftime("%Y-%m-%d")

    # If weekend
    if is_weekend:
        day_name = dt.strftime("%A")
        # Try getting previous close
        t = yf.Ticker(clean_sym)
        hist = t.history(end=date_str, period="5d")
        prev_close = round(hist['Close'].iloc[-1], 2) if not hist.empty else None
        return None, None, f"Market Closed ({day_name})" + (f" [Prev Close: ₹{prev_close}]" if prev_close else "")

    t = yf.Ticker(clean_sym)
    
    # Try 5m interval first
    try:
        df_5m = t.history(start=date_str, end=next_day, interval="5m")
        if not df_5m.empty:
            p_930 = None
            p_1500 = None
            for idx, row in df_5m.iterrows():
                t_str = idx.strftime("%H:%M")
                if t_str in ["09:30", "09:25", "09:35"] and p_930 is None:
                    p_930 = round(float(row["Close"]), 2)
                if t_str in ["15:00", "14:55", "15:05"]:
                    p_1500 = round(float(row["Close"]), 2)
            if p_930 is not None or p_1500 is not None:
                return p_930, p_1500, "Traded (5m exact)"
    except Exception:
        pass

    # Try 1h interval fallback
    try:
        df_1h = t.history(start=date_str, end=next_day, interval="1h")
        if not df_1h.empty:
            p_930 = None
            p_1500 = None
            for idx, row in df_1h.iterrows():
                t_str = idx.strftime("%H:%M")
                if t_str == "09:15":
                    # 09:15 bar spans 09:15 to 10:15; Open is 9:15, Close is 10:15
                    # Midpoint or close
                    p_930 = round(float(row["Open"]), 2)
                if t_str == "14:15":
                    # 14:15 bar spans 14:15 to 15:15; Close is ~15:15
                    p_1500 = round(float(row["Close"]), 2)
                elif t_str == "15:15" and p_1500 is None:
                    p_1500 = round(float(row["Open"]), 2)
            if p_930 is not None or p_1500 is not None:
                return p_930, p_1500, "Traded (1h bar)"
    except Exception:
        pass

    # Try 1d interval fallback (holiday/data issue)
    try:
        df_1d = t.history(start=date_str, end=next_day, interval="1d")
        if df_1d.empty:
            return None, None, "Market Closed (Trading Holiday)"
        else:
            close_val = round(float(df_1d["Close"].iloc[0]), 2)
            return close_val, close_val, f"Daily only (Close: ₹{close_val})"
    except Exception:
        pass

    return None, None, "No Price Data"

print("Test 1: SBIN on 2026-08-01 (Saturday):", get_market_prices("SBIN.NS", "2026-08-01"))
print("Test 2: SBIN on 2026-08-07 (Traded):", get_market_prices("SBIN.NS", "2026-08-07"))
print("Test 3: 533278.BO (Coal India) on 2026-08-07:", get_market_prices("533278.BO", "2026-08-07"))
print("Test 4: SBIN on 2026-08-21 (Traded 5m):", get_market_prices("SBIN.NS", "2026-08-21"))
