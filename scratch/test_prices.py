import yfinance as yf
from datetime import datetime, timedelta

def get_intraday_prices(symbol, date_str):
    # Try 5m interval first (available within 60 days)
    # Next day for end
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    next_day = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
    
    t = yf.Ticker(symbol)
    
    # Check 5m
    df_5m = t.history(start=date_str, end=next_day, interval="5m")
    if not df_5m.empty:
        print(f"{symbol} 5m on {date_str}: {len(df_5m)} bars")
        # Find bar at 9:30 and 15:00
        # Print times
        times = [ts.strftime("%H:%M") for ts in df_5m.index]
        print("Sample times:", times[:5], "...", times[-5:])
        # 9:30 is 09:30:00
        # 15:00 is 15:00:00
        p_930 = None
        p_1500 = None
        for idx, row in df_5m.iterrows():
            t_str = idx.strftime("%H:%M")
            if t_str in ["09:30", "09:25", "09:35"] and p_930 is None:
                p_930 = row["Close"]
            if t_str in ["15:00", "14:55", "15:05"]:
                p_1500 = row["Close"]
        print(f"9:30: {p_930}, 15:00: {p_1500}")
        return p_930, p_1500
        
    # Check 1h
    df_1h = t.history(start=date_str, end=next_day, interval="1h")
    if not df_1h.empty:
        print(f"{symbol} 1h on {date_str}: {len(df_1h)} bars")
        for idx, row in df_1h.iterrows():
            print(idx.strftime("%H:%M"), row['Open'], row['Close'])
        # 09:15 bar: 9:30 is between 9:15 and 10:15
        # 14:15 bar: 15:00 is between 14:15 and 15:15
        return None, None
        
    # If weekend / holiday
    df_1d = t.history(start=date_str, end=next_day, interval="1d")
    print(f"{symbol} 1d on {date_str}: {len(df_1d)} bars")
    return None, None

for sym in ["SBIN.NS", "TITAN.NS", "KAYNES.NS"]:
    print(f"\n--- Testing {sym} for 2026-08-07 ---")
    get_intraday_prices(sym, "2026-08-07")
    print(f"\n--- Testing {sym} for 2026-08-21 ---")
    get_intraday_prices(sym, "2026-08-21")
