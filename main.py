"""
股价实时悬浮窗 - 入口文件
"""

import sys
import json
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from stock_widget import StockWidget
from stock_fetcher import map_stock_to_sina_code


def load_config():
    """加载配置文件，若不存在则生成默认配置"""
    default_config = {
        "stocks": [
            {"symbol": "sh000001", "market": "IDX", "name": "上证指数"},
            {"symbol": "gb_ixic", "market": "IDX", "name": "纳斯达克"},
            {"symbol": "rt_hk03032", "market": "IDX", "name": "恒生科技"},
            {"symbol": "hf_XAU", "market": "IDX", "name": "伦敦金"},
            {"symbol": "sh000300", "market": "IDX", "name": "沪深300"},
            {"symbol": "sh000510", "market": "IDX", "name": "中证A500"},
            {"symbol": "sh000905", "market": "IDX", "name": "中证500"},
            {"symbol": "hf_OIL", "market": "IDX", "name": "布伦特原油"}
        ],
        "refresh_interval": 2,
        "opacity": 0.85,
        "ai_settings": {},
        "gold_data_settings": {},
    }

    def normalize_config_symbols(config):
        stocks = config.get("stocks", [])
        symbol_mapping = {}
        for stock in stocks:
            old_symbol = stock.get("symbol", "")
            parsed = map_stock_to_sina_code(stock)
            if parsed:
                stock["symbol"] = parsed[0]
                stock.pop("sina_code", None)
            symbol_mapping[old_symbol] = stock.get("symbol", old_symbol)

        visible_stocks = config.get("visible_stocks", [])
        normalized_visible = []
        for symbol in visible_stocks:
            mapped_symbol = symbol_mapping.get(symbol, symbol)
            if mapped_symbol == symbol:
                parsed = map_stock_to_sina_code({"symbol": symbol, "market": "IDX", "name": symbol})
                if parsed:
                    mapped_symbol = parsed[0]
            if mapped_symbol not in normalized_visible:
                normalized_visible.append(mapped_symbol)
        config["visible_stocks"] = normalized_visible
        return config

    if getattr(sys, 'frozen', False):
        # 打包后：优先从 exe 目录读取，不存在则从 _internal 复制
        exe_dir = os.path.dirname(sys.executable)
        exe_config_path = os.path.join(exe_dir, "config.json")

        if os.path.exists(exe_config_path):
            try:
                with open(exe_config_path, "r", encoding="utf-8") as f:
                    return normalize_config_symbols(json.load(f))
            except Exception:
                pass

        # exe 目录不存在，从 _internal 复制一份
        internal_dir = getattr(sys, '_MEIPASS', exe_dir)
        internal_config_path = os.path.join(internal_dir, "config.json")

        if os.path.exists(internal_config_path):
            try:
                with open(internal_config_path, "r", encoding="utf-8") as f:
                    config = normalize_config_symbols(json.load(f))
                # 复制到 exe 目录
                with open(exe_config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                return config
            except Exception:
                pass
    else:
        # 开发环境
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "config.json")

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return normalize_config_symbols(json.load(f))
            except Exception:
                pass

        # 开发环境创建默认配置
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    return normalize_config_symbols(default_config)


def main():
    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    config = load_config()
    widget = StockWidget(config)
    widget.show()

    # 使用 QCoreApplication.instance() 来确保正确清理
    result = app.exec_()

    # 强制退出，确保所有线程被终止
    import os
    os._exit(result)


if __name__ == "__main__":
    main()
