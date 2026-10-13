import yfinance as yf

ticker = yf.Ticker("RELIANCE.NS")
h = ticker.history(start="2026-08-01", end="2026-08-05", interval="1h")
print("1h data for 2026-08-01 to 2026-08-05:")
print(h[['Open', 'High', 'Low', 'Close']])
