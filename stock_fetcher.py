"""
股价数据获取模块
支持 A 股（akshare）和美股（yfinance）
"""

import os
import traceback
from PyQt5.QtCore import QThread, pyqtSignal

# 抑制 yfinance 和 akshare 的进度条输出
os.environ["TQDM_DISABLE"] = "1"


class StockFetcher(QThread):
    """在后台线程中获取股价数据"""
    data_ready = pyqtSignal(dict)  # {symbol: {name, price, change, change_pct, market}}
    error_occurred = pyqtSignal(str)

    def __init__(self, stock_list):
        super().__init__()
        self.stock_list = stock_list
        self._running = True

    def run(self):
        results = {}
        # 按市场分组
        a_stocks = [s for s in self.stock_list if s["market"] == "A"]
        us_stocks = [s for s in self.stock_list if s["market"] in ("US", "IDX")]

        # 获取 A 股数据
        if a_stocks:
            try:
                a_data = self._fetch_a_shares(a_stocks)
                results.update(a_data)
            except Exception as e:
                self.error_occurred.emit(f"A股: {type(e).__name__}")

        # 获取美股数据
        if us_stocks:
            try:
                us_data = self._fetch_us_stocks(us_stocks)
                results.update(us_data)
            except Exception as e:
                self.error_occurred.emit(f"US: {type(e).__name__}")

        if results:
            self.data_ready.emit(results)

    def _fetch_a_shares(self, stocks):
        """使用 akshare 逐个获取 A 股实时行情 (避免全量拉取导致的代理连接断开)"""
        import akshare as ak

        results = {}
        name_map = {s["symbol"]: s["name"] for s in stocks}

        for s in stocks:
            code = s["symbol"]
            try:
                # 获取个股实时行情 (盘口/最新价等)
                df = ak.stock_bid_ask_em(symbol=code)
                # DataFrame有两列: item (指标) 和 value (数值)
                # 提取最新价、涨跌额、涨跌幅
                latest = df.loc[df["item"] == "最新", "value"].values
                change_amt = df.loc[df["item"] == "涨跌", "value"].values
                change_pct = df.loc[df["item"] == "涨幅", "value"].values
                
                price = _safe_float(latest[0] if len(latest) > 0 else 0)
                change = _safe_float(change_amt[0] if len(change_amt) > 0 else 0)
                pct = _safe_float(change_pct[0] if len(change_pct) > 0 else 0)
                
                results[code] = {
                    "name": name_map.get(code, code),
                    "price": price,
                    "change": change,
                    "change_pct": pct,
                    "market": "A",
                }
            except Exception:
                # 网络错误时静默跳过，保留上次数据
                pass
        return results

    def _fetch_us_stocks(self, stocks):
        """使用 yfinance 获取美股实时报价，逐个获取以提高容错"""
        import yfinance as yf

        results = {}
        name_map = {s["symbol"]: s["name"] for s in stocks}

        for s in stocks:
            sym = s["symbol"]
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                price = _safe_float(getattr(info, "last_price", None))
                prev_close = _safe_float(getattr(info, "previous_close", None))
                if prev_close == 0:
                    prev_close = price
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close != 0 else 0
                results[sym] = {
                    "name": name_map.get(sym, sym),
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "market": "US",
                }
            except Exception:
                # 网络错误时静默跳过，保留上次数据
                pass
        return results

    def stop(self):
        self._running = False


def _safe_float(val):
    """安全转换为 float，无效值返回 0"""
    try:
        if val is None:
            return 0.0
        f = float(val)
        if f != f:  # NaN check
            return 0.0
        return f
    except (ValueError, TypeError):
        return 0.0
