"""
股价悬浮窗 - PyQt5 半透明无边框可拖动窗口
"""

import datetime
import json
import os
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMenu, QAction,
    QWidgetAction, QSlider, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QCursor

from stock_fetcher import StockFetcher


class StockRow(QWidget):
    """单只股票的显示行"""

    def __init__(self, symbol, name, market, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.market = market
        self._base_opacity = 1.0
        self._current_color = "#888888"  # 当前文字颜色
        self._current_change_pct = None  # 当前涨跌幅
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 2)
        layout.setSpacing(8)

        # 名称标签
        self.name_label = QLabel(name)
        self.name_label.setFixedWidth(72)
        self.name_label.setFont(QFont("Microsoft YaHei", 9))
        self.name_label.setStyleSheet("color: #B0B8C8;")

        # 价格标签
        self.price_label = QLabel("--")
        self.price_label.setFixedWidth(72)
        self.price_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.price_label.setFont(QFont("Consolas", 10, QFont.Bold))
        self.price_label.setStyleSheet("color: #FFFFFF;")

        # 涨跌幅标签
        self.change_label = QLabel("--")
        self.change_label.setFixedWidth(64)
        self.change_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.change_label.setFont(QFont("Consolas", 9))
        self.change_label.setStyleSheet("color: #888888;")

        layout.addWidget(self.name_label)
        layout.addStretch()
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)

    def _hex_to_rgba(self, hex_color, alpha):
        """将 hex 颜色转换为带透明度的 rgba 格式"""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        a = int(alpha * 255)
        return f"rgba({r},{g},{b},{a})"

    def set_opacity(self, opacity):
        """根据透明度更新所有标签的颜色"""
        self._base_opacity = opacity
        self.name_label.setStyleSheet(f"color: {self._hex_to_rgba('#B0B8C8', opacity)};")
        # 重新应用当前颜色（带新透明度）
        if self._current_change_pct is not None:
            rgba = self._hex_to_rgba(self._current_color, opacity)
            self.price_label.setStyleSheet(f"color: {rgba};")
            self.change_label.setStyleSheet(f"color: {rgba};")

    def update_data(self, price, change, change_pct):
        """更新价格和涨跌数据"""
        self._current_change_pct = change_pct
        if price == 0:
            self.price_label.setText("--")
            self.change_label.setText("--")
            self._current_color = "#888888"
            rgba = self._hex_to_rgba("#888888", self._base_opacity)
            self.change_label.setStyleSheet(f"color: {rgba};")
            self.price_label.setStyleSheet(f"color: {rgba};")
            return

        # 格式化价格
        if self.market == "A":
            self.price_label.setText(f"¥{price:.2f}")
        elif self.market == "US":
            self.price_label.setText(f"${price:.2f}")
        else:
            self.price_label.setText(f"{price:.2f}")

        # 涨跌幅颜色（中国习惯：红涨绿跌）
        if change_pct > 0:
            color = "#FF4757"  # 红色 - 涨
            sign = "+"
        elif change_pct < 0:
            color = "#2ED573"  # 绿色 - 跌
            sign = ""
        else:
            color = "#888888"  # 灰色 - 平
            sign = ""

        self._current_color = color
        rgba_color = self._hex_to_rgba(color, self._base_opacity)
        self.change_label.setText(f"{sign}{change_pct:.2f}%")
        self.change_label.setStyleSheet(f"color: {rgba_color};")
        self.price_label.setStyleSheet(f"color: {rgba_color};")


class StockWidget(QWidget):
    """主悬浮窗组件"""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.stock_list = config.get("stocks", [])
        self.refresh_interval = config.get("refresh_interval", 2) * 1000
        self.bg_opacity = config.get("opacity", 0.85)
        self.text_opacity = config.get("text_opacity", 1.0)
        self.stock_rows = {}
        self._drag_pos = None
        self._fetcher = None
        self._finished_fetchers = []  # 保持引用防止GC
        
        # 边缘吸附及隐藏相关
        self._hide_edge = None       # 吸附的边缘 ('top', 'left', 'right' 或 None)
        self._is_hidden = False      # 当前是否处于隐藏状态
        self._normal_geometry = None # 正常展开时的几何尺寸
        self._animation = QPropertyAnimation(self, b"geometry")
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.InOutQuad)

        self._init_ui()
        self._init_timer()
        
        # 绑定退出时保存配置
        QApplication.instance().aboutToQuit.connect(self._save_config)
        
        self._fetch_data()  # 首次立即获取

    def _init_ui(self):
        """初始化界面"""
        # 窗口属性
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool  # 不在任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(260)

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 8, 0, 4)
        self.main_layout.setSpacing(0)


        # 添加股票行
        for stock in self.stock_list:
            row = StockRow(stock["symbol"], stock["name"], stock["market"])
            self.stock_rows[stock["symbol"]] = row
            self.main_layout.addWidget(row)

        # 状态栏
        self.status_label = QLabel("加载中...")
        self.status_label.setFont(QFont("Microsoft YaHei", 7))
        self.status_label.setStyleSheet("color: #3A4A5A;")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setContentsMargins(0, 4, 0, 2)
        self.main_layout.addWidget(self.status_label)

        # 初始化时同步透明度到所有 StockRow
        for row in self.stock_rows.values():
            row.set_opacity(self.text_opacity)
        self.status_label.setStyleSheet(f"color: rgba(58, 74, 90, {self.text_opacity});")

        # 初始位置：屏幕右上角
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 300, 60)

    def _init_timer(self):
        """初始化定时器"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._fetch_data)
        self.timer.start(self.refresh_interval)

    def _fetch_data(self):
        """启动后台数据获取（如果上次还在跑则跳过）"""
        # 清理已完成的线程
        self._finished_fetchers = [
            f for f in self._finished_fetchers if f.isRunning()
        ]
        # 如果上次获取还在进行中，跳过本次
        if self._fetcher is not None and self._fetcher.isRunning():
            return
        self._fetcher = StockFetcher(self.stock_list)
        self._fetcher.data_ready.connect(self._on_data_ready)
        self._fetcher.error_occurred.connect(self._on_error)
        self._fetcher.finished.connect(self._on_fetch_finished)
        self._finished_fetchers.append(self._fetcher)
        self._fetcher.start()

    def _on_data_ready(self, data):
        """数据返回后更新 UI"""
        for symbol, info in data.items():
            if symbol in self.stock_rows:
                self.stock_rows[symbol].update_data(
                    info["price"], info["change"], info["change_pct"]
                )
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.status_label.setText(f"更新于 {now}")

    def _on_error(self, msg):
        """显示错误信息"""
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.status_label.setText(f"{now} ⚠ {msg[:20]}")

    def _on_fetch_finished(self):
        """获取线程完成后清理"""
        pass

    # ── 绘制圆角半透明背景 ─────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # 半透明深色背景
        bg_color = QColor(220, 220, 220, int(255 * self.bg_opacity))
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        painter.end()

    # ── 拖动与边缘停靠支持 ─────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            # 拖动时解除吸附状态
            self._hide_edge = None
            self._is_hidden = False
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._check_edge_snap()

    def _check_edge_snap(self):
        """检查是否靠近屏幕边缘并自动吸附"""
        screen = QApplication.primaryScreen().geometry()
        geo = self.frameGeometry()
        margin = 10  # 边缘吸附阈值（像素）

        if geo.top() <= screen.top() + margin:
            self._hide_edge = 'top'
            geo.moveTop(screen.top())
        elif geo.left() <= screen.left() + margin:
            self._hide_edge = 'left'
            geo.moveLeft(screen.left())
        elif geo.right() >= screen.right() - margin:
            self._hide_edge = 'right'
            geo.moveRight(screen.right())
        else:
            self._hide_edge = None

        if self._hide_edge:
            self.setGeometry(geo)
            self._normal_geometry = QRect(geo)
            # 判断鼠标当前是否在窗口外，如果是则立即隐藏
            if not self.underMouse():
                self._hide_window()

    def enterEvent(self, event):
        """鼠标进入时展开"""
        if self._hide_edge and self._is_hidden:
            self._show_window()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开时隐藏"""
        if self._hide_edge and not self._is_hidden:
            # 延迟一下触发或者直接隐藏，这里直接隐藏
            self._hide_window()
        super().leaveEvent(event)

    def _show_window(self):
        if not self._normal_geometry:
            return
        self._animation.stop()
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(self._normal_geometry)
        self._animation.start()
        self._is_hidden = False

    def _hide_window(self):
        if not self._normal_geometry:
            return
        
        geo = QRect(self._normal_geometry)
        show_width = 4  # 边缘保留可见的像素用于鼠标触发
        screen = QApplication.primaryScreen().geometry()
        
        if self._hide_edge == 'top':
            geo.moveBottom(screen.top() + show_width)
        elif self._hide_edge == 'left':
            geo.moveRight(screen.left() + show_width)
        elif self._hide_edge == 'right':
            geo.moveLeft(screen.right() - show_width)
            
        self._animation.stop()
        self._animation.setStartValue(self.geometry())
        self._animation.setEndValue(geo)
        self._animation.start()
        self._is_hidden = True

    # ── 右键菜单 ─────────────────────────────
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a1f2e;
                color: #c0c8d8;
                border: 1px solid #2a3040;
                border-radius: 6px;
                padding: 4px;
                font-family: 'Microsoft YaHei';
                font-size: 9pt;
            }
            QMenu::item:selected {
                background-color: #2a3548;
            }
        """)

        # 背景透明度滑动条
        bg_opacity_menu = menu.addMenu("🎨 背景透明度")
        bg_slider_action = QWidgetAction(bg_opacity_menu)
        bg_slider_widget = QWidget()
        bg_slider_layout = QHBoxLayout(bg_slider_widget)
        bg_slider_layout.setContentsMargins(10, 4, 10, 4)

        bg_opacity_slider = QSlider(Qt.Horizontal)
        bg_opacity_slider.setMinimum(10)
        bg_opacity_slider.setMaximum(100)
        bg_opacity_slider.setValue(int(self.bg_opacity * 100))
        bg_opacity_slider.setFixedWidth(100)
        bg_opacity_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #3A4A5A;
                height: 4px;
                background: #1a1f2e;
                margin: 2px 0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #8A9AA0;
                border: 1px solid #5A6A80;
                width: 10px;
                margin: -4px 0;
                border-radius: 5px;
            }
        """)

        bg_val_label = QLabel(f"{int(self.bg_opacity * 100)}%")
        bg_val_label.setFont(QFont("Consolas", 8))
        bg_val_label.setStyleSheet("color: #c0c8d8;")
        bg_val_label.setFixedWidth(32)

        def on_bg_slider_changed(val):
            bg_val_label.setText(f"{val}%")
            self._set_bg_opacity(val / 100)

        bg_opacity_slider.valueChanged.connect(on_bg_slider_changed)
        bg_opacity_slider.sliderReleased.connect(self._save_config)

        bg_slider_layout.addWidget(bg_opacity_slider)
        bg_slider_layout.addWidget(bg_val_label)
        bg_slider_action.setDefaultWidget(bg_slider_widget)
        bg_opacity_menu.addAction(bg_slider_action)

        # 文字透明度滑动条
        text_opacity_menu = menu.addMenu("🔤 文字透明度")
        text_slider_action = QWidgetAction(text_opacity_menu)
        text_slider_widget = QWidget()
        text_slider_layout = QHBoxLayout(text_slider_widget)
        text_slider_layout.setContentsMargins(10, 4, 10, 4)

        text_opacity_slider = QSlider(Qt.Horizontal)
        text_opacity_slider.setMinimum(10)
        text_opacity_slider.setMaximum(100)
        text_opacity_slider.setValue(int(self.text_opacity * 100))
        text_opacity_slider.setFixedWidth(100)
        text_opacity_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #3A4A5A;
                height: 4px;
                background: #1a1f2e;
                margin: 2px 0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #8A9AA0;
                border: 1px solid #5A6A80;
                width: 10px;
                margin: -4px 0;
                border-radius: 5px;
            }
        """)

        text_val_label = QLabel(f"{int(self.text_opacity * 100)}%")
        text_val_label.setFont(QFont("Consolas", 8))
        text_val_label.setStyleSheet("color: #c0c8d8;")
        text_val_label.setFixedWidth(32)

        def on_text_slider_changed(val):
            text_val_label.setText(f"{val}%")
            self._set_text_opacity(val / 100)

        text_opacity_slider.valueChanged.connect(on_text_slider_changed)
        text_opacity_slider.sliderReleased.connect(self._save_config)

        text_slider_layout.addWidget(text_opacity_slider)
        text_slider_layout.addWidget(text_val_label)
        text_slider_action.setDefaultWidget(text_slider_widget)
        text_opacity_menu.addAction(text_slider_action)

        # 刷新间隔
        interval_menu = menu.addMenu("⏱ 刷新间隔")
        for sec in [1, 2, 3, 5, 10]:
            action = interval_menu.addAction(f"{sec} 秒")
            action.triggered.connect(lambda checked, s=sec: self._set_interval(s))

        menu.addSeparator()

        # 立即刷新
        refresh_action = menu.addAction("🔄 立即刷新")
        refresh_action.triggered.connect(self._fetch_data)

        menu.addSeparator()

        # 退出
        quit_action = menu.addAction("❌ 退出")
        quit_action.triggered.connect(QApplication.quit)

        menu.exec_(event.globalPos())

    def _set_bg_opacity(self, val):
        self.bg_opacity = val
        self.update()

    def _set_text_opacity(self, val):
        self.text_opacity = val
        # 更新所有股票行的文字透明度
        for row in self.stock_rows.values():
            row.set_opacity(val)
        # 更新状态栏透明度
        self.status_label.setStyleSheet(f"color: rgba(58, 74, 90, {val});")

    def _set_interval(self, sec):
        self.refresh_interval = sec * 1000
        self.timer.setInterval(self.refresh_interval)
        self._save_config()

    def _get_config_path(self):
        """获取配置文件的正确路径（兼容打包后）"""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "config.json")

    def _save_config(self):
        """保存当前配置到文件"""
        config_path = self._get_config_path()
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            else:
                config_data = self.config.copy()
                
            config_data["opacity"] = self.bg_opacity
            config_data["text_opacity"] = self.text_opacity
            config_data["refresh_interval"] = self.refresh_interval // 1000
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")
