import yfinance as yf
from datetime import datetime, timedelta

ticker = yf.Ticker("RELIANCE.NS")
now = datetime.now()
print("Now:", now)

for days_ago in [50, 55, 58, 60, 65, 70, 75]:
    dt = now - timedelta(days=days_ago)
    start_str = dt.strftime("%Y-%m-%d")
    end_str = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        h = ticker.history(start=start_str, end=end_str, interval="5m")
        print(f"5m data for {start_str} ({days_ago} days ago): {len(h)}")
    except Exception as e:
        print(f"Error for {start_str}: {e}")
