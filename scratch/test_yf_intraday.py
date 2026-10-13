import yfinance as yf

ticker = yf.Ticker("RELIANCE.NS")
for yr in [2026, 2025, 2024, 2023]:
    h = ticker.history(start=f"{yr}-08-01", end=f"{yr}-08-02", interval="5m")
    print(f"Intraday 5m for {yr}-08-01:", len(h))
    h1h = ticker.history(start=f"{yr}-08-01", end=f"{yr}-08-02", interval="60m")
    print(f"Intraday 60m for {yr}-08-01:", len(h1h))
