"""
股价实时悬浮窗 - 入口文件
"""

import sys
import json
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from stock_widget import StockWidget


def load_config():
    """加载配置文件，若不存在则生成默认配置"""
    # 兼容 PyInstaller 打包后的路径
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    config_path = os.path.join(base_dir, "config.json")
    
    default_config = {
        "stocks": [
            {"symbol": "000001.SS", "market": "IDX", "name": "上证指数"},
            {"symbol": "^IXIC", "market": "IDX", "name": "纳斯达克"},
            {"symbol": "3032.HK", "market": "IDX", "name": "恒生科技"},
            {"symbol": "GC=F", "market": "IDX", "name": "伦敦金"},
            {"symbol": "000300.SS", "market": "IDX", "name": "沪深300"},
            {"symbol": "000510.SS", "market": "IDX", "name": "中证A500"},
            {"symbol": "000905.SS", "market": "IDX", "name": "中证500"},
            {"symbol": "BZ=F", "market": "IDX", "name": "布伦特原油"}
        ],
        "refresh_interval": 2,
        "opacity": 0.85,
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass # fallback to default if parsing fails

    # 创建默认配置
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
        
    return default_config


def main():
    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    config = load_config()
    widget = StockWidget(config)
    widget.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
