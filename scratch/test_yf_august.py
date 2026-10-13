import yfinance as yf
import datetime

# Test yfinance for Reliance on various August dates (2026, 2024, 2023)
ticker = yf.Ticker("RELIANCE.NS")
print("History 1mo:")
h = ticker.history(period="5d", interval="5m")
print("Recent 5m data available:", not h.empty)
if not h.empty:
    print(h.index[0], "to", h.index[-1])

# Check what years have data
for yr in [2026, 2025, 2024, 2023]:
    d = ticker.history(start=f"{yr}-08-01", end=f"{yr}-08-05", interval="1d")
    print(f"Daily data for Aug {yr}:", len(d))
