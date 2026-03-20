import yfinance as yf

symbols = {
    "上证指数": "000001.SS",
    "纳斯达克指数": "^IXIC",
    "恒生科技指数": "^HSTECH",
    "伦敦金": "GC=F", # or XAUUSD=X
    "沪深300": "000300.SS",
    "中证A500": "000510.SS",
    "中证500": "000905.SS",
    "布伦特原油": "BZ=F",
}

for name, sym in symbols.items():
    try:
        ticker = yf.Ticker(sym)
        # 尝试快速获取信息
        info = ticker.fast_info
        price = info.last_price
        prev_close = info.previous_close
        change = price - prev_close
        pct = (change / prev_close) * 100 if prev_close else 0
        print(f"✅ {name}({sym}): Price={price:.2f}, Change={change:.2f}, Pct={pct:.2f}%")
    except Exception as e:
        print(f"❌ {name}({sym}): Failed - {e}")
