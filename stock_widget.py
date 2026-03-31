"""
股价悬浮窗 - PyQt5 半透明无边框可拖动窗口
"""
import datetime
import json
import os
import sys
import requests
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMenu, QAction,
    QWidgetAction, QSlider, QApplication, QSystemTrayIcon,
    QListWidget, QListWidgetItem, QPushButton, QDialog, QMessageBox
)
from PyQt5.QtCore import (
    Qt, QTimer, QPoint, QRect, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup
)
from PyQt5.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QCursor, QIcon, QPixmap
)
from stock_fetcher import StockFetcher, search_stocks, get_display_quote_code, _safe_float
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QLineEdit, QScrollArea, QWidget as QtQWidget,
    QVBoxLayout as QtVBoxLayout
)
import urllib.parse

UI_FONT_FAMILY = 'Microsoft YaHei UI'
UI_FONT_FALLBACK = 'Microsoft YaHei'
MONO_FONT_FAMILY = 'Consolas'
MONO_FONT_FALLBACK = 'Consolas'


def get_theme_tokens(dark_mode):
    """返回菜单和对话框使用的主题色。"""
    if dark_mode:
        return {
            'panel': '#1a1f2e', 'panel_alt': '#0d1117',
            'panel_hover': '#161b22', 'panel_active': '#1f2937',
            'surface': '#2a3548', 'surface_hover': '#3a4558',
            'surface_pressed': '#253040', 'border': '#2a3040',
            'border_soft': '#3a4a5a', 'text': '#c0c8d8',
            'text_strong': '#e0e8f0', 'text_muted': '#5a6a7a',
            'accent': '#4a9eff', 'accent_hover': '#5aafff',
            'accent_pressed': '#3a8eef', 'scrollbar': '#3a4a5a',
            'slider_handle': '#8a9aa0', 'slider_handle_border': '#5a6a80'
        }
    else:
        return {
            'panel': '#f7f9fc', 'panel_alt': '#ffffff',
            'panel_hover': '#f0f4f8', 'panel_active': '#e8eef7',
            'surface': '#edf2f7', 'surface_hover': '#e2e8f0',
            'surface_pressed': '#d9e2ec', 'border': '#d7dee8',
            'border_soft': '#bcc8d6', 'text': '#425466',
            'text_strong': '#253040', 'text_muted': '#6b7a8c',
            'accent': '#2f7cf6', 'accent_hover': '#438cff',
            'accent_pressed': '#216de0', 'scrollbar': '#bcc8d6',
            'slider_handle': '#6b7a8c', 'slider_handle_border': '#98a6b6'
        }


def build_menu_stylesheet(tokens):
    return f"""
        QMenu {{
            background-color: {tokens['panel']};
            color: {tokens['text']};
            border: 1px solid {tokens['border']};
            border-radius: 6px;
            padding: 4px;
            font-family: 'Microsoft YaHei';
            font-size: 9pt;
        }}
        QMenu::item:selected {{
            background-color: {tokens['surface']};
        }}
    """


def build_button_stylesheet(tokens, primary=False):
    if primary:
        bg = tokens['accent']
        hover = tokens['accent_hover']
        pressed = tokens['accent_pressed']
        border = tokens['accent']
        text = '#ffffff'
    else:
        bg = tokens['surface']
        hover = tokens['surface_hover']
        pressed = tokens['surface_pressed']
        border = tokens['border_soft']
        text = tokens['text']
    return f"""
        QPushButton {{
            background-color: {bg};
            color: {text};
            border: 1px solid {border};
            border-radius: 4px;
            padding: 2px 10px;
            font-size: 8pt;
            font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;
        }}
        QPushButton:hover {{
            background-color: {hover};
        }}
        QPushButton:pressed {{
            background-color: {pressed};
        }}
    """


def build_input_stylesheet(tokens):
    return f"""
        QLineEdit {{
            background-color: {tokens['panel_alt']};
            border: 1px solid {tokens['border']};
            border-radius: 4px;
            padding: 4px 8px;
            color: {tokens['text']};
            font-size: 9pt;
            font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;
        }}
        QLineEdit:focus {{
            border: 1px solid {tokens['accent']};
        }}
    """


def build_list_stylesheet(tokens, with_indicator=False):
    indicator_css = ''
    if with_indicator:
        indicator_css = f"""
            QListWidget::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid {tokens['border_soft']};
                background-color: {tokens['panel']};
            }}
            QListWidget::indicator:checked {{
                background-color: {tokens['accent']};
                border-color: {tokens['accent']};
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iMTAiIHZpZXdCb3g9IjAgMCAxMCAxMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMiA1TDQgN0w4IDMiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgZmlsbD0ibm9uZSIgbGluZWpvaW49InJvdW5kIi8+PC9zdmc+);
            }}
            QListWidget::indicator:checked:hover {{
                background-color: {tokens['accent_hover']};
            }}
            QListWidget::indicator:unchecked:hover {{
                border-color: {tokens['accent']};
                background-color: {tokens['surface']};
            }}
        """
    return f"""
        QListWidget {{
            background-color: {tokens['panel_alt']};
            border: 1px solid {tokens['border']};
            border-radius: 6px;
            color: {tokens['text']};
            font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;
            font-size: 9pt;
            outline: none;
        }}
        QListWidget::item {{
            padding: 2px 6px;
            border-radius: 3px;
        }}
        QListWidget::item:selected {{
            background-color: {tokens['panel_active']};
        }}
        QListWidget::item:hover {{
            background-color: {tokens['panel_hover']};
        }}
        {indicator_css}
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 6px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {tokens['scrollbar']};
            min-height: 15px;
            border-radius: 3px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """


def build_slider_stylesheet(tokens):
    return f"""
        QSlider::groove:horizontal {{
            border: 1px solid {tokens['border_soft']};
            height: 4px;
            background: {tokens['panel']};
            margin: 2px 0;
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {tokens['slider_handle']};
            border: 1px solid {tokens['slider_handle_border']};
            width: 10px;
            margin: -4px 0;
            border-radius: 5px;
        }}
    """


class StockRow(QWidget):
    """单只股票的显示行"""

    def __init__(self, symbol, name, market, parent=None, base_font_size=9):
        super().__init__(parent)
        self.symbol = symbol
        self.name = name
        self.market = market
        self.base_font_size = base_font_size
        self.privacy_mode = False
        self.show_code_in_label = False
        self._base_opacity = 1.0
        self._current_change_pct = None
        self._dot_color = '#888888'
        self._colors = None
        self._dark_mode = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 1, 8, 1)
        layout.setSpacing(4)

        self.name_label = QLabel(name)
        self.price_label = QLabel('--')
        self.price_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.change_label = QLabel('--')
        self.change_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.time_label = QLabel('')
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.dot_label = QLabel('●')
        self.dot_label.hide()

        layout.addWidget(self.dot_label)
        layout.addWidget(self.name_label)
        layout.addStretch()
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)
        layout.addWidget(self.time_label)

        self.set_font_size(base_font_size)
        self._apply_default_theme()
        self._update_primary_label()

    def _make_font(self, family, size, weight=QFont.Normal):
        font = QFont(family, size, weight)
        return font

    def set_font_size(self, base_font_size):
        """根据基础字号更新整行字体与尺寸。"""
        self.base_font_size = max(8, min(16, int(base_font_size)))
        name_size = self.base_font_size
        mono_main_size = self.base_font_size + 1
        mono_sub_size = self.base_font_size
        time_size = max(8, self.base_font_size - 1)

        self.name_label.setFont(self._make_font(UI_FONT_FAMILY, name_size))
        self.price_label.setFont(self._make_font(MONO_FONT_FAMILY, mono_main_size, QFont.DemiBold))
        self.change_label.setFont(self._make_font(MONO_FONT_FAMILY, mono_sub_size))
        self.time_label.setFont(self._make_font(MONO_FONT_FAMILY, time_size))
        self.dot_label.setFont(self._make_font(UI_FONT_FAMILY, name_size))

        self.dot_label.setFixedWidth(max(14, self.dot_label.fontMetrics().horizontalAdvance('●') + 4))
        self.price_label.setFixedWidth(max(62, self.price_label.fontMetrics().horizontalAdvance('-88888.88') + 8))
        self.change_label.setFixedWidth(max(58, self.change_label.fontMetrics().horizontalAdvance('-88.88%') + 8))
        self.time_label.setFixedWidth(max(52, self.time_label.fontMetrics().horizontalAdvance('00:00:00') + 6))

        content_height = max(
            self.name_label.fontMetrics().height(),
            self.price_label.fontMetrics().height(),
            self.change_label.fontMetrics().height(),
            self.time_label.fontMetrics().height(),
            self.dot_label.fontMetrics().height()
        )
        self.setFixedHeight(max(24, content_height + 8))
        self._update_primary_label()

    def _update_primary_label(self):
        text = self.symbol if self.show_code_in_label else self.name
        self.name_label.setText(text)
        label_width = self.name_label.fontMetrics().horizontalAdvance(text) + 12
        self.name_label.setFixedWidth(max(72, min(240, label_width)))

    def get_content_width(self):
        """按当前可见内容估算行宽，用于窗口自适应。"""
        margins = self.layout().contentsMargins()
        spacing = self.layout().spacing()
        total = margins.left() + margins.right()
        visible_count = 0

        def add_width(widget, extra=0):
            nonlocal visible_count
            nonlocal total
            if widget.isHidden():
                return
            text = widget.text() if hasattr(widget, 'text') else ''
            metrics = widget.fontMetrics()
            width = metrics.horizontalAdvance(text) + extra
            total += width
            if visible_count > 0:
                total += spacing
            visible_count += 1

        add_width(self.dot_label, 2)
        add_width(self.name_label, 10)
        add_width(self.price_label, 8)
        add_width(self.change_label, 8)
        add_width(self.time_label, 6)
        return total + 20

    def _apply_default_theme(self):
        """应用默认黑夜模式主题"""
        name_rgb = (180, 190, 200)
        self.name_label.setStyleSheet(f'color: rgba({name_rgb[0]}, {name_rgb[1]}, {name_rgb[2]}, 1);')
        self.price_label.setStyleSheet(f'color: rgba({name_rgb[0]}, {name_rgb[1]}, {name_rgb[2]}, 1);')
        self.change_label.setStyleSheet(f'color: rgba({name_rgb[0]}, {name_rgb[1]}, {name_rgb[2]}, 1);')
        self.time_label.setStyleSheet(f'color: rgba({name_rgb[0]}, {name_rgb[1]}, {name_rgb[2]}, 1);')
        self.dot_label.setStyleSheet(f'color: rgba({name_rgb[0]}, {name_rgb[1]}, {name_rgb[2]}, 1);')

    def apply_theme(self, dark_mode, colors, opacity):
        """应用主题颜色"""
        self._dark_mode = dark_mode
        self._colors = colors
        self._base_opacity = opacity
        name_rgb = colors['name']
        text_rgb = colors['text']
        status_rgb = colors['status']
        self.name_label.setStyleSheet(f'color: rgba({name_rgb[0]}, {name_rgb[1]}, {name_rgb[2]}, {opacity});')
        self.time_label.setStyleSheet(f'color: rgba({status_rgb[0]}, {status_rgb[1]}, {status_rgb[2]}, {opacity});')
        if self._current_change_pct is not None:
            self._apply_colors(self._current_change_pct)

    def _rgb_to_rgba(self, rgb, alpha):
        """将 rgb 元组转换为 rgba 字符串"""
        return f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})'

    def set_privacy_mode(self, enabled):
        """设置隐私模式"""
        self.privacy_mode = enabled
        if enabled:
            self.dot_label.show()
            self.time_label.hide()
        else:
            self.dot_label.hide()
            self.time_label.show()
        self._update_primary_label()
        if self._current_change_pct is not None:
            self._apply_colors(self._current_change_pct)

    def set_show_code_in_label(self, enabled):
        """设置主标签显示代码还是昵称"""
        self.show_code_in_label = enabled
        self._update_primary_label()

    def set_opacity(self, opacity):
        """根据透明度更新所有标签的颜色"""
        self._base_opacity = opacity
        if self._colors:
            self.apply_theme(self._dark_mode, self._colors, opacity)
        else:
            name_rgb = (180, 190, 200)
            self.name_label.setStyleSheet(f'color: rgba({name_rgb[0]}, {name_rgb[1]}, {name_rgb[2]}, {opacity});')
            self.price_label.setStyleSheet(f'color: rgba({name_rgb[0]}, {name_rgb[1]}, {name_rgb[2]}, {opacity});')
            self.change_label.setStyleSheet(f'color: rgba({name_rgb[0]}, {name_rgb[1]}, {name_rgb[2]}, {opacity});')
            self.time_label.setStyleSheet(f'color: rgba({name_rgb[0]}, {name_rgb[1]}, {name_rgb[2]}, {opacity});')
        if self.privacy_mode:
            self.dot_label.setStyleSheet(f'color: {self._rgb_to_rgba(self._dot_color, opacity)};')
        if self._current_change_pct is not None:
            self._apply_colors(self._current_change_pct)

    def _apply_colors(self, change_pct):
        """根据是否隐私模式应用颜色"""
        if self._colors:
            up_color = self._colors['up']
            down_color = self._colors['down']
            text_color = self._colors['text']
            status_color = self._colors['status']
        else:
            up_color = (255, 71, 87)
            down_color = (46, 213, 115)
            text_color = (180, 190, 200)
            status_color = (140, 150, 160)

        if self.privacy_mode:
            gray_rgba = self._rgb_to_rgba(status_color, self._base_opacity)
            self.price_label.setStyleSheet(f'color: {gray_rgba};')
            self.change_label.setStyleSheet(f'color: {gray_rgba};')
            if change_pct > 0:
                self._dot_color = up_color
            elif change_pct < 0:
                self._dot_color = down_color
            else:
                self._dot_color = status_color
            dot_rgba = self._rgb_to_rgba(self._dot_color, self._base_opacity)
            self.dot_label.setStyleSheet(f'color: {dot_rgba};')
        else:
            if change_pct > 0:
                color_rgb = up_color
            elif change_pct < 0:
                color_rgb = down_color
            else:
                color_rgb = text_color
            rgba_color = self._rgb_to_rgba(color_rgb, self._base_opacity)
            self.price_label.setStyleSheet(f'color: {rgba_color};')
            self.change_label.setStyleSheet(f'color: {rgba_color};')

    def update_data(self, price, change, change_pct, update_time=''):
        """更新价格和涨跌数据"""
        self._current_change_pct = change_pct
        if update_time:
            try:
                time_part = update_time.strip().split(' ')[-1]
                parts = time_part.split(':')
                if len(parts) >= 2:
                    self.time_label.setText(f'{parts[0]}:{parts[1]}')
                else:
                    self.time_label.setText(time_part[:5])
            except Exception:
                self.time_label.setText(update_time[:5])

        if price == 0:
            self.price_label.setText('--')
            self.change_label.setText('--')
            self._current_color = '#888888'
            rgba = self._hex_to_rgba('#888888', self._base_opacity)
            self.change_label.setStyleSheet(f'color: {rgba};')
            self.price_label.setStyleSheet(f'color: {rgba};')
            return

        if self.market == 'A':
            self.price_label.setText(f'¥{price:.2f}')
        elif self.market == 'US':
            self.price_label.setText(f'${price:.2f}')
        else:
            self.price_label.setText(f'{price:.2f}')

        if change_pct > 0:
            sign = '+'
        elif change_pct < 0:
            sign = ''
        else:
            sign = ''
        self.change_label.setText(f'{sign}{change_pct:.2f}%')
        self._apply_colors(change_pct)


class StockSearchThread(QThread):
    """股票搜索后台线程"""
    search_done = pyqtSignal(list)
    search_error = pyqtSignal(str)

    def __init__(self, keyword, local_candidates=None):
        super().__init__()
        self.keyword = keyword
        self.local_candidates = list(local_candidates or [])

    def run(self):
        try:
            results = search_stocks(
                self.keyword,
                cancel_check=lambda: self.isInterruptionRequested(),
                local_candidates=self.local_candidates
            )
            if not self.isInterruptionRequested():
                self.search_done.emit(results)
        except requests.exceptions.Timeout:
            if not self.isInterruptionRequested():
                self.search_error.emit('请求超时，请检查网络连接')
        except requests.exceptions.ConnectionError:
            if not self.isInterruptionRequested():
                self.search_error.emit('网络连接失败，请检查网络')
        except Exception as e:
            if not self.isInterruptionRequested():
                import traceback
                traceback.print_exc()
                self.search_error.emit(f'搜索失败: {str(e)}')

    def stop(self):
        """请求停止搜索"""
        self.requestInterruption()


class SearchResultItem(QtQWidget):
    """搜索结果项 - 可点击添加"""

    def __init__(self, stock_info, parent=None):
        super().__init__(parent)
        self.stock_info = stock_info
        self.setFixedHeight(36)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        name_label = QLabel(stock_info['name'])
        name_label.setStyleSheet('color: #e0e8f0; font-size: 9pt; font-weight: 500;')
        layout.addWidget(name_label)

        code_label = QLabel(stock_info['symbol'])
        code_label.setStyleSheet("color: #5a9eff; font-size: 8pt; font-family: 'Consolas';")
        layout.addWidget(code_label)

        market_map = {'A': 'A股', 'IDX': '指数', 'US': '美股', 'HK': '港股', 'FUTURE': '期货'}
        market_label = QLabel(market_map.get(stock_info['market'], stock_info['market']))
        market_label.setStyleSheet("""
            color: #3a4a5a;
            background-color: #2a3548;
            padding: 1px 6px;
            border-radius: 3px;
            font-size: 7pt;
        """)
        layout.addWidget(market_label)

        layout.addStretch()

        add_label = QLabel('+ 添加')
        add_label.setStyleSheet('color: #4a9eff; font-size: 8pt;')
        layout.addWidget(add_label)

    def mousePressEvent(self, event):
        """点击时通知父窗口"""
        if event.button() == Qt.LeftButton:
            self.window().add_search_result(self.stock_info)

    def enterEvent(self, event):
        """鼠标悬停效果"""
        self.setStyleSheet('background-color: #2a3548; border-radius: 4px;')
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开效果"""
        self.setStyleSheet('background-color: transparent;')
        super().leaveEvent(event)


class ReorderableListWidget(QListWidget):
    """跟手拖拽的可排序列表。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_row = -1
        self._drag_start_pos = None
        self._drag_item = None
        self._placeholder_item = None
        self._dragging = False
        self._drag_pixmap = None
        self._drag_hotspot = QPoint()
        self._drag_draw_pos = QPoint()
        self._insert_row = -1
        self._transition_overlays = []
        self._transition_groups = []
        self._suspend_drag_paint = False
        self.setMouseTracking(True)
        self.setAutoScroll(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_row = self.indexAt(event.pos()).row()
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_row >= 0 and self._drag_start_pos is not None and
                (event.pos() - self._drag_start_pos).manhattanLength() >= QApplication.startDragDistance()):
            if not self._dragging:
                self._begin_drag(event.pos())
            self._update_drag(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging:
            self._end_drag()
        else:
            self._reset_drag_state()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        if self._dragging and self._drag_pixmap is not None and not self._suspend_drag_paint:
            painter.setOpacity(0.92)
            painter.drawPixmap(self._drag_draw_pos, self._drag_pixmap)

    def _begin_drag(self, pos):
        item = self.item(self._drag_row)
        if item is None:
            return
        self._dragging = True
        item_rect = self.visualItemRect(item)
        self._drag_pixmap = self._build_drag_pixmap(item_rect)
        self._drag_hotspot = pos - item_rect.topLeft()
        self._drag_draw_pos = item_rect.topLeft()
        self._insert_row = self._drag_row
        self._drag_item = self.takeItem(self._drag_row)
        self._placeholder_item = QListWidgetItem('')
        self._placeholder_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsDropEnabled)
        self._placeholder_item.setData(Qt.UserRole, '__placeholder__')
        self._placeholder_item.setSizeHint(item.sizeHint())
        self.insertItem(self._drag_row, self._placeholder_item)
        self.viewport().update()

    def _update_drag(self, pos):
        if not self._dragging or self._drag_item is None or self._placeholder_item is None:
            return
        self._drag_draw_pos = pos - self._drag_hotspot
        self._auto_scroll_if_needed(pos)
        insert_row = self._calculate_insert_row(pos.y())
        self._insert_row = insert_row
        current_row = self.row(self._placeholder_item)
        target_row = insert_row
        if target_row > current_row:
            target_row -= 1
        if (0 <= current_row < self.count() and 0 <= target_row < self.count()
                and target_row != current_row):
            old_rects = self._capture_item_rects()
            item = self.takeItem(current_row)
            self.insertItem(target_row, item)
            self._placeholder_item = item
            self._animate_relayout(old_rects)
        self.viewport().update()

    def _build_drag_pixmap(self, item_rect):
        return self.viewport().grab(item_rect)

    def _auto_scroll_if_needed(self, pos):
        scrollbar = self.verticalScrollBar()
        edge_margin = 24
        step = 12
        if pos.y() < edge_margin:
            scrollbar.setValue(scrollbar.value() - step)
        elif pos.y() > self.viewport().height() - edge_margin:
            scrollbar.setValue(scrollbar.value() + step)

    def _calculate_insert_row(self, y_pos):
        for row in range(self.count()):
            rect = self.visualItemRect(self.item(row))
            if y_pos < rect.center().y():
                return row
        return self.count()

    def _end_drag(self):
        if self._drag_item is not None and self._placeholder_item is not None:
            placeholder_row = self.row(self._placeholder_item)
            self.takeItem(placeholder_row)
            self.insertItem(placeholder_row, self._drag_item)
            self.setCurrentItem(self._drag_item)
        self._reset_drag_state()
        self.viewport().update()

    def _reset_drag_state(self):
        self._drag_row = -1
        self._drag_start_pos = None
        self._drag_item = None
        self._placeholder_item = None
        self._dragging = False
        self._drag_pixmap = None
        self._insert_row = -1

    def _capture_item_rects(self):
        rects = {}
        self._suspend_drag_paint = True
        self.viewport().repaint()
        for row in range(self.count()):
            item = self.item(row)
            if item is None:
                continue
            symbol = item.data(Qt.UserRole)
            if symbol == '__placeholder__':
                continue
            rect = self.visualItemRect(item)
            if not rect.isValid():
                continue
            rects[symbol] = (QRect(rect), self.viewport().grab(rect))
        self._suspend_drag_paint = False
        self.viewport().update()
        return rects

    def _animate_relayout(self, old_rects):
        group = QParallelAnimationGroup(self)
        has_animation = False
        for row in range(self.count()):
            item = self.item(row)
            if item is None:
                continue
            symbol = item.data(Qt.UserRole)
            if not symbol or symbol == '__placeholder__' or symbol not in old_rects:
                continue
            old_rect, pixmap = old_rects[symbol]
            new_rect = self.visualItemRect(item)
            if old_rect.topLeft() == new_rect.topLeft():
                continue
            overlay = QLabel(self.viewport())
            overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
            overlay.setPixmap(pixmap)
            overlay.resize(pixmap.size())
            overlay.move(old_rect.topLeft())
            overlay.show()
            overlay.raise_()
            self._transition_overlays.append(overlay)
            anim = QPropertyAnimation(overlay, b'pos', self)
            anim.setDuration(140)
            anim.setStartValue(old_rect.topLeft())
            anim.setEndValue(new_rect.topLeft())
            anim.setEasingCurve(QEasingCurve.OutCubic)
            group.addAnimation(anim)
            has_animation = True

        if not has_animation:
            group.deleteLater()
            return

        self._transition_groups.append(group)

        def cleanup():
            while self._transition_overlays:
                overlay = self._transition_overlays.pop()
                overlay.deleteLater()
            if group in self._transition_groups:
                self._transition_groups.remove(group)
            group.deleteLater()
            self.viewport().update()

        group.finished.connect(cleanup)
        group.start()


class StockListDialog(QDialog):
    """指数显示设置对话框 - 支持勾选和拖拽排序、搜索添加"""
    _detached_search_threads = set()

    def __init__(self, all_stocks, visible_symbols, parent=None, dark_mode=True):
        super().__init__(parent)
        self.all_stocks = all_stocks
        self.visible_symbols = list(visible_symbols)
        self.result_symbols = None
        self.search_results = []
        self.search_thread = None
        self.dark_mode = dark_mode
        self.theme_tokens = get_theme_tokens(dark_mode)

        self.setWindowTitle('指数显示设置')
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(380, 400)

        self._fade_animation = QPropertyAnimation(self, b'windowOpacity')
        self._fade_animation.setDuration(150)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {self.theme_tokens['panel']};
                border: 1px solid {self.theme_tokens['border_soft']};
                border-radius: 10px;
            }}
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(6)

        # 标题栏
        title_layout = QHBoxLayout()
        title_layout.setSpacing(6)
        title_icon = QLabel('📊')
        title_icon.setStyleSheet('font-size: 14pt;')
        title = QLabel('指数显示')
        title.setStyleSheet(
            f"color: {self.theme_tokens['text_strong']}; font-size: 10pt; "
            f"font-weight: 600; font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;"
        )
        hint = QLabel('勾选 · 拖拽排序')
        hint.setStyleSheet(
            f"color: {self.theme_tokens['text_muted']}; font-size: 8pt; "
            f"font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;"
        )
        title_layout.addWidget(title_icon)
        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(hint)
        container_layout.addLayout(title_layout)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('搜索股票/指数名称或代码...')
        self.search_input.setStyleSheet(build_input_stylesheet(self.theme_tokens))
        self.search_input.setFixedHeight(28)
        self.search_input.returnPressed.connect(self._do_search)
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton('🔍')
        search_btn.setFixedSize(36, 28)
        search_btn.setStyleSheet(build_button_stylesheet(self.theme_tokens))
        search_btn.clicked.connect(self._do_search)
        search_layout.addWidget(search_btn)
        container_layout.addLayout(search_layout)

        # 搜索结果列表
        self.search_results_widget = QListWidget()
        self.search_results_widget.setStyleSheet(build_list_stylesheet(self.theme_tokens))
        self.search_results_widget.setMaximumHeight(120)
        self.search_results_widget.itemDoubleClicked.connect(self._add_selected_search_result)
        self.search_results_widget.hide()
        container_layout.addWidget(self.search_results_widget)

        # 分隔线
        line = QLabel()
        line.setStyleSheet(f"background-color: {self.theme_tokens['border']}; border: none;")
        line.setFixedHeight(1)
        container_layout.addWidget(line)

        # 股票列表
        self.list_widget = ReorderableListWidget()
        self.list_widget.setStyleSheet(build_list_stylesheet(self.theme_tokens, with_indicator=True))
        self.list_widget.setDragDropMode(QListWidget.NoDragDrop)
        self.list_widget.setDragEnabled(False)
        self.list_widget.setAcceptDrops(False)
        self.list_widget.viewport().setAcceptDrops(False)
        self.list_widget.setDropIndicatorShown(False)
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_list_context_menu)

        symbol_to_stock = {s.get('symbol'): s for s in all_stocks}
        visible_set = set(visible_symbols)
        for symbol in visible_symbols:
            if symbol in symbol_to_stock:
                stock = symbol_to_stock[symbol]
                self.list_widget.addItem(self._create_stock_item(stock, Qt.Checked))
        for stock in all_stocks:
            symbol = stock.get('symbol', '')
            if symbol not in visible_set:
                self.list_widget.addItem(self._create_stock_item(stock, Qt.Unchecked))
        container_layout.addWidget(self.list_widget)

        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        select_all_btn = QPushButton('全选')
        select_all_btn.setFixedHeight(24)
        select_all_btn.setStyleSheet(build_button_stylesheet(self.theme_tokens))
        select_all_btn.clicked.connect(self._select_all)

        select_none_btn = QPushButton('清空')
        select_none_btn.setFixedHeight(24)
        select_none_btn.setStyleSheet(build_button_stylesheet(self.theme_tokens))
        select_none_btn.clicked.connect(self._select_none)

        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(select_none_btn)
        btn_layout.addStretch()

        confirm_btn = QPushButton('确定')
        confirm_btn.setFixedHeight(24)
        confirm_btn.setFixedWidth(50)
        confirm_btn.setStyleSheet(build_button_stylesheet(self.theme_tokens, primary=True))
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)
        container_layout.addLayout(btn_layout)

        main_layout.addWidget(container)

    def _create_stock_item(self, stock, check_state):
        symbol = stock.get('symbol', '')
        name = stock.get('name', symbol)
        display_code = get_display_quote_code(stock)
        item = QListWidgetItem(f'{name} ({display_code})')
        item.setFlags(
            Qt.ItemIsEnabled | Qt.ItemIsSelectable |
            Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        )
        item.setData(Qt.UserRole, symbol)
        item.setCheckState(check_state)
        return item

    def showEvent(self, event):
        """显示时播放淡入动画"""
        super().showEvent(event)
        self.setWindowOpacity(0)
        self._fade_animation.start()

    def _done_with_animation(self):
        """动画结束后关闭对话框"""
        self.setResult(1)
        super().accept()

    def _select_all(self):
        """全选"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(Qt.Checked)

    def _select_none(self):
        """全不选"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(Qt.Unchecked)

    def _show_list_context_menu(self, pos):
        """显示列表项右键菜单"""
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        self.list_widget.setCurrentItem(item)
        menu = QMenu(self)
        menu.setStyleSheet(build_menu_stylesheet(self.theme_tokens))
        delete_action = menu.addAction('删除')
        delete_action.triggered.connect(self._delete_selected)
        menu.exec_(self.list_widget.viewport().mapToGlobal(pos))

    def _do_search(self):
        """执行搜索"""
        keyword = self.search_input.text().strip()
        if not keyword:
            return
        self._cleanup_thread()
        self.search_input.setEnabled(False)
        self.search_results_widget.clear()
        self.search_results_widget.show()
        loading_item = QListWidgetItem('搜索中...')
        self.search_results_widget.addItem(loading_item)
        self.search_thread = StockSearchThread(keyword, self.all_stocks)
        self.search_thread.search_done.connect(self._on_search_done)
        self.search_thread.search_error.connect(self._on_search_error)
        self.search_thread.finished.connect(self._on_search_finished)
        self.search_thread.start()

    def _on_search_finished(self):
        """搜索线程结束时的处理"""
        thread = self.sender()
        if thread is not self.search_thread:
            return
        self.search_input.setEnabled(True)
        self.search_thread = None
        thread.deleteLater()

    def _on_search_done(self, results):
        """搜索完成回调"""
        if self.sender() is not self.search_thread:
            return
        self.search_results_widget.clear()
        self.search_input.setEnabled(True)
        if not results:
            self.search_results_widget.addItem(QListWidgetItem('未找到相关股票/指数'))
            return
        self.search_results = results
        for stock in results[:10]:
            market_map = {'A': 'A股', 'IDX': '指数', 'US': '美股', 'HK': '港股', 'FUTURE': '期货'}
            market_text = market_map.get(stock['market'], stock['market'])
            display_code = get_display_quote_code(stock)
            display_text = f"{stock['name']} ({display_code}) [{market_text}]"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, stock)
            self.search_results_widget.addItem(item)

    def _on_search_error(self, error):
        """搜索错误回调"""
        if self.sender() is not self.search_thread:
            return
        self.search_results_widget.clear()
        self.search_input.setEnabled(True)
        self.search_results_widget.addItem(QListWidgetItem(f'搜索失败: {error}'))

    def add_search_result(self, stock_info):
        """添加搜索结果到配置"""
        symbol = stock_info['symbol']
        symbol_set = {s.get('symbol') for s in self.all_stocks}
        if symbol in symbol_set:
            return
        stored_stock = dict(stock_info)
        stored_stock.pop('sina_code', None)
        self.all_stocks.append(stored_stock)
        self.visible_symbols.append(symbol)
        self.list_widget.addItem(self._create_stock_item(stored_stock, Qt.Checked))
        self.list_widget.scrollToBottom()

    def _delete_selected(self):
        """删除当前右键选中的指数/股票"""
        row = self.list_widget.currentRow()
        if row < 0:
            return
        item = self.list_widget.takeItem(row)
        if not item:
            return
        symbol = item.data(Qt.UserRole)
        self.all_stocks[:] = [stock for stock in self.all_stocks if stock.get('symbol') != symbol]
        self.visible_symbols = [sym for sym in self.visible_symbols if sym != symbol]
        self.search_results = [stock for stock in self.search_results if stock.get('symbol') != symbol]
        del item

    def _add_selected_search_result(self, item):
        """双击搜索结果项添加"""
        stock_info = item.data(Qt.UserRole)
        if stock_info:
            self.add_search_result(stock_info)

    def get_ordered_visible_symbols(self):
        """获取排序后的可见股票列表"""
        result = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                symbol = item.data(Qt.UserRole)
                result.append(symbol)
        return result

    def accept(self):
        """确认时保存结果"""
        self.result_symbols = self.get_ordered_visible_symbols()
        fade_out = QPropertyAnimation(self, b'windowOpacity')
        fade_out.setDuration(100)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.finished.connect(self._done_with_animation)
        self._fade_out = fade_out
        fade_out.start()

    def done(self, result):
        """重写done方法，防止动画期间被关闭"""
        self._cleanup_thread()
        if hasattr(self, '_fade_out') and self._fade_out.state() == QPropertyAnimation.Running:
            return
        super().done(result)

    def closeEvent(self, event):
        """对话框关闭时清理资源"""
        self._cleanup_thread()
        super().closeEvent(event)

    def _cleanup_thread(self):
        """清理搜索线程"""
        if not self.search_thread:
            return
        thread = self.search_thread
        self.search_thread = None
        thread.stop()
        if thread.isRunning():
            StockListDialog._detached_search_threads.add(thread)
            thread.finished.connect(lambda t=thread: StockListDialog._detached_search_threads.discard(t))
            thread.finished.connect(thread.deleteLater)
        else:
            thread.deleteLater()


class GoldPriceFetchThread(QThread):
    """获取沪金、伦敦金、美元汇率数据的线程"""
    data_ready = pyqtSignal(float, float, float)  # 沪金, 伦敦金, 汇率

    def run(self):
        try:
            url = 'http://hq.sinajs.cn/list=nf_AU0,hf_XAU,fx_susdcny'
            headers = {'Referer': 'https://finance.sina.com.cn/'}
            resp = requests.get(url, headers=headers, timeout=8)
            resp.encoding = 'gbk'
            lines = resp.text.strip().split('\n')
            shanghai = london = rate = 0.0
            for line in lines:
                eq_idx = line.index('=')
                key = line[:eq_idx].rsplit('_', 1)[-1]
                val = line[eq_idx + 2:-1]  # strip '"...'
                parts = val.split(',')
                if key == 'AU0' and len(parts) > 8:
                    shanghai = _safe_float(parts[8])
                elif key == 'XAU' and len(parts) > 0:
                    london = _safe_float(parts[0])
                elif key == 'susdcny' and len(parts) > 1:
                    rate = _safe_float(parts[1])
            self.data_ready.emit(shanghai, london, rate)
        except Exception:
            self.data_ready.emit(0.0, 0.0, 0.0)


class GoldConverterDialog(QDialog):
    """金价换算器对话框"""
    TROY_OUNCE_TO_GRAM = 31.1035

    def __init__(self, parent=None, dark_mode=True):
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.theme_tokens = get_theme_tokens(dark_mode)
        self._drag_pos = None
        self._updating = None  # which input is being edited
        self.shanghai_gold = 0.0
        self.london_gold = 0.0
        self.usd_cny_rate = 0.0
        self._fetch_thread = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(340, 350)

        self._fade_animation = QPropertyAnimation(self, b'windowOpacity')
        self._fade_animation.setDuration(150)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)

        t = self.theme_tokens
        ff = "font-family: 'Microsoft YaHei', sans-serif;"
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {t['panel']};
                border: 1px solid {t['border_soft']};
                border-radius: 10px;
                {ff}
            }}
        """)
        cl = QVBoxLayout(container)
        cl.setContentsMargins(16, 10, 16, 12)
        cl.setSpacing(8)

        # --- 标题栏 ---
        title_bar = QHBoxLayout()
        title_bar.setSpacing(6)
        title_icon = QLabel('🥇')
        title_icon.setStyleSheet(f'font-size: 14pt; {ff}')
        title_label = QLabel('金价换算器')
        title_label.setStyleSheet(
            f"color: {t['text_strong']}; font-size: 10pt; font-weight: 600; {ff}"
        )
        title_bar.addWidget(title_icon)
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        close_btn = QLabel('✕')
        close_btn.setStyleSheet(
            f"color: {t['text_muted']}; font-size: 11pt; padding: 2px 6px; {ff}"
        )
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        close_btn.mousePressEvent = lambda e: self._close_with_animation()
        title_bar.addWidget(close_btn)
        cl.addLayout(title_bar)

        # --- 实时价格（仅伦敦金 + 汇率）---
        price_group = QWidget()
        price_group.setStyleSheet(
            f"background-color: {t['panel_alt']}; border-radius: 6px; {ff}"
        )
        pl = QVBoxLayout(price_group)
        pl.setContentsMargins(10, 8, 10, 8)
        pl.setSpacing(4)

        self._london_price_label = QLabel('伦敦金 (XAU)    -- 美元/盎司')
        self._rate_label = QLabel('美元汇率         --')
        for lbl in (self._london_price_label, self._rate_label):
            lbl.setStyleSheet(
                f"color: {t['text']}; font-size: 9pt; {ff}"
            )
            pl.addWidget(lbl)
        cl.addWidget(price_group)

        # --- 换算输入 ---
        input_style = (
            f"background-color: {t['panel_alt']}; color: {t['text_strong']}; "
            f"border: 1px solid {t['border']}; border-radius: 4px; padding: 4px 8px; "
            f"font-size: 10pt; {ff}"
        )
        label_style = f"color: {t['text']}; font-size: 9pt; {ff}"

        # 伦敦金输入
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        lbl1 = QLabel('伦敦金')
        lbl1.setFixedWidth(48)
        lbl1.setStyleSheet(label_style)
        self._london_input = QLineEdit()
        self._london_input.setPlaceholderText('美元/盎司')
        self._london_input.setStyleSheet(input_style)
        row1.addWidget(lbl1)
        row1.addWidget(self._london_input)
        cl.addLayout(row1)

        # 沪金输入
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        lbl2 = QLabel('沪金')
        lbl2.setFixedWidth(48)
        lbl2.setStyleSheet(label_style)
        self._shanghai_input = QLineEdit()
        self._shanghai_input.setPlaceholderText('元/克')
        self._shanghai_input.setStyleSheet(input_style)
        row2.addWidget(lbl2)
        row2.addWidget(self._shanghai_input)
        cl.addLayout(row2)

        # 升贴水输入
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        lbl3 = QLabel('升贴水')
        lbl3.setFixedWidth(48)
        lbl3.setStyleSheet(label_style)
        self._premium_input = QLineEdit()
        self._premium_input.setPlaceholderText('元/克 (可选)')
        self._premium_input.setStyleSheet(input_style)
        row3.addWidget(lbl3)
        row3.addWidget(self._premium_input)
        cl.addLayout(row3)

        # 银行积存金结果
        row4 = QHBoxLayout()
        row4.setSpacing(8)
        lbl4 = QLabel('积存金')
        lbl4.setFixedWidth(48)
        lbl4.setStyleSheet(label_style)
        self._bank_result = QLabel('-- 元/克')
        self._bank_result.setStyleSheet(
            f"color: {t['accent']}; font-size: 10pt; font-weight: 600; {ff}"
        )
        row4.addWidget(lbl4)
        row4.addWidget(self._bank_result)
        row4.addStretch()
        cl.addLayout(row4)

        self._london_input.textChanged.connect(self._on_london_input)
        self._shanghai_input.textChanged.connect(self._on_shanghai_input)
        self._premium_input.textChanged.connect(self._on_premium_input)

        # --- 刷新按钮 ---
        self._refresh_btn = QPushButton('🔄 刷新汇率')
        self._refresh_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t['surface']}; color: {t['text']};
                border: 1px solid {t['border']}; border-radius: 6px;
                padding: 6px 0; font-size: 9pt; {ff}
            }}
            QPushButton:hover {{
                background-color: {t['surface_hover']};
            }}
            QPushButton:pressed {{
                background-color: {t['surface_pressed']};
            }}
        """)
        self._refresh_btn.clicked.connect(self._fetch_data)
        cl.addWidget(self._refresh_btn)

        main_layout.addWidget(container)

    def _recalc_bank_result(self):
        """更新银行积存金 = 沪金 + 升贴水"""
        sh = _safe_float(self._shanghai_input.text())
        pr = _safe_float(self._premium_input.text())
        if sh > 0:
            self._bank_result.setText(f'{sh + pr:.2f} 元/克')
        else:
            self._bank_result.setText('-- 元/克')

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_animation.start()
        self._fetch_data()

    def _fetch_data(self):
        if self._fetch_thread and self._fetch_thread.isRunning():
            return
        self._refresh_btn.setText('🔄 加载中...')
        self._fetch_thread = GoldPriceFetchThread()
        self._fetch_thread.data_ready.connect(self._on_data_ready)
        self._fetch_thread.finished.connect(self._fetch_thread.deleteLater)
        self._fetch_thread.finished.connect(lambda: setattr(self, '_fetch_thread', None))
        self._fetch_thread.start()

    def _on_data_ready(self, shanghai, london, rate):
        self.shanghai_gold = shanghai
        self.london_gold = london
        self.usd_cny_rate = rate
        self._refresh_btn.setText('🔄 刷新汇率')

        if london > 0:
            self._london_price_label.setText(f'伦敦金 (XAU)    {london:.2f} 美元/盎司')
        else:
            self._london_price_label.setText('伦敦金 (XAU)    -- 美元/盎司')
        if rate > 0:
            self._rate_label.setText(f'美元汇率         {rate:.4f}')
        else:
            self._rate_label.setText('美元汇率         --')

        # 用实时伦敦金价格填充，自动触发沪金换算
        if london > 0 and self._updating != 'london':
            self._london_input.setText(f'{london:.2f}')

    def _on_london_input(self, text):
        if self._updating:
            return
        val = _safe_float(text)
        self._updating = 'london'
        if val > 0 and self.usd_cny_rate > 0:
            shanghai = val * self.usd_cny_rate / self.TROY_OUNCE_TO_GRAM
            self._shanghai_input.setText(f'{shanghai:.2f}')
        else:
            self._shanghai_input.clear()
        self._updating = None
        self._recalc_bank_result()

    def _on_shanghai_input(self, text):
        if self._updating:
            return
        val = _safe_float(text)
        self._updating = 'shanghai'
        if val > 0 and self.usd_cny_rate > 0:
            london = val * self.TROY_OUNCE_TO_GRAM / self.usd_cny_rate
            self._london_input.setText(f'{london:.2f}')
        else:
            self._london_input.clear()
        self._updating = None
        self._recalc_bank_result()

    def _on_premium_input(self, text):
        self._recalc_bank_result()

    # --- 拖动 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() < 35:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
        else:
            self._drag_pos = None

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _close_with_animation(self):
        fade_out = QPropertyAnimation(self, b'windowOpacity')
        fade_out.setDuration(100)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.finished.connect(self.close)
        fade_out.start()
        self._fade_out_anim = fade_out  # prevent GC


class StockWidget(QWidget):
    """主悬浮窗组件"""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.all_stocks = config.get('stocks', [])
        config_visible = config.get('visible_stocks', [])
        if config_visible:
            self.visible_symbols = config_visible
            symbol_to_stock = {s.get('symbol'): s for s in self.all_stocks}
            self.stock_list = [symbol_to_stock[sym] for sym in config_visible if sym in symbol_to_stock]
        else:
            self.visible_symbols = [s.get('symbol') for s in self.all_stocks]
            self.stock_list = self.all_stocks

        self.refresh_interval = config.get('refresh_interval', 2) * 1000
        self.bg_opacity = config.get('opacity', 0.85)
        self.text_opacity = config.get('text_opacity', 1.0)
        self.privacy_mode = config.get('privacy_mode', False)
        self.show_update_time = config.get('show_update_time', True)
        self.dark_mode = config.get('dark_mode', True)
        self.show_code_in_label = config.get('show_code_in_label', self.privacy_mode)
        self.base_font_size = config.get('font_size', 9)
        self.stock_rows = {}
        self._drag_pos = None
        self._fetcher = None
        self._finished_fetchers = []

        self._init_colors()

        self._hide_edge = None
        self._is_hidden = False
        self._normal_geometry = None
        self._animation = QPropertyAnimation(self, b'geometry')
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.InOutQuad)
        self._menu_open = False

        self._init_ui()
        self._init_timer()
        self._init_tray()
        QApplication.instance().aboutToQuit.connect(self._save_config)
        self._fetch_data()

    def _init_ui(self):
        """初始化界面"""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(120)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 4, 0, 2)
        self.main_layout.setSpacing(0)

        for stock in self.stock_list:
            row = StockRow(
                get_display_quote_code(stock), stock['name'], stock['market'],
                base_font_size=self.base_font_size
            )
            self.stock_rows[stock['symbol']] = row
            self.main_layout.addWidget(row)

        self.status_label = QLabel('加载中...')
        self._apply_status_font()
        self.status_label.setStyleSheet('color: #3A4A5A;')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setContentsMargins(0, 4, 0, 2)
        self.main_layout.addWidget(self.status_label)

        for row in self.stock_rows.values():
            row.set_privacy_mode(self.privacy_mode)
            row.set_show_code_in_label(self.show_code_in_label)
            row.apply_theme(self.dark_mode, self.colors, self.text_opacity)

        status_rgb = self.colors['status']
        self.status_label.setStyleSheet(
            f'color: rgba({status_rgb[0]}, {status_rgb[1]}, {status_rgb[2]}, {self.text_opacity});'
        )
        if not self.show_update_time:
            self.status_label.hide()

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 240, 60)
        self._adjust_window_size()

    def _init_timer(self):
        """初始化定时器"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._fetch_data)
        self.timer.start(self.refresh_interval)

    def _apply_status_font(self):
        status_size = max(8, self.base_font_size - 1)
        self.status_label.setFont(QFont(UI_FONT_FAMILY, status_size))

    def _init_colors(self):
        """初始化颜色主题"""
        if self.dark_mode:
            self.colors = {
                'bg': (26, 31, 46), 'name': (180, 190, 200),
                'text': (180, 190, 200), 'status': (140, 150, 160),
                'up': (255, 71, 87), 'down': (46, 213, 115),
                'border': (42, 48, 64)
            }
        else:
            self.colors = {
                'bg': (240, 242, 245), 'name': (74, 90, 106),
                'text': (42, 48, 64), 'status': (106, 122, 138),
                'up': (220, 53, 69), 'down': (40, 167, 69),
                'border': (208, 216, 224)
            }

    def _apply_theme(self):
        """应用当前主题到所有UI元素"""
        for row in self.stock_rows.values():
            row.apply_theme(self.dark_mode, self.colors, self.text_opacity)
        status_color = self.colors['status']
        self.status_label.setStyleSheet(
            f'color: rgba({status_color[0]}, {status_color[1]}, {status_color[2]}, {self.text_opacity});'
        )
        self.update()

    def _init_tray(self):
        """初始化系统托盘图标"""
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            from PyQt5.QtWidgets import QStyle
            icon = QApplication.instance().style().standardIcon(QStyle.SP_ComputerIcon)
            self.tray_icon.setIcon(icon)

        tray_menu = QMenu()
        show_action = tray_menu.addAction('显示/隐藏')
        show_action.triggered.connect(self._toggle_visibility)
        quit_action = tray_menu.addAction('退出')
        quit_action.triggered.connect(QApplication.instance().quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip('股票悬浮窗')
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _toggle_visibility(self):
        """切换窗口显示/隐藏"""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_tray_activated(self, reason):
        """托盘图标被激活（双击）"""
        if reason == QSystemTrayIcon.DoubleClick:
            self._toggle_visibility()

    def _fetch_data(self):
        """启动后台数据获取（如果上次还在跑则跳过）"""
        self._finished_fetchers = [f for f in self._finished_fetchers if f.isRunning()]
        if self._fetcher is not None and self._fetcher.isRunning():
            return
        self._fetcher = StockFetcher(self.all_stocks, 'sina')
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
                    info['price'], info['change'],
                    info['change_pct'], info.get('update_time', '')
                )
        now = datetime.datetime.now().strftime('%H:%M:%S')
        self.status_label.setText(f'更新于 {now}')
        self._adjust_window_size()

    def _on_error(self, msg):
        """显示错误信息"""
        now = datetime.datetime.now().strftime('%H:%M:%S')
        self.status_label.setText(f'{now} ⚠ {msg[:20]}')

    def _on_fetch_finished(self):
        """获取线程完成后清理"""
        return

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        shadow_offset = 4
        shadow_color = QColor(0, 0, 0, 15)
        for i in range(shadow_offset):
            offset = shadow_offset - i
            shadow_rect = rect.adjusted(offset, offset, -offset + 2, -offset + 2)
            painter.setBrush(QBrush(shadow_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(shadow_rect, 10, 10)
        bg_rgb = self.colors['bg']
        bg_color = QColor(bg_rgb[0], bg_rgb[1], bg_rgb[2], int(255 * self.bg_opacity))
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 10, 10)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
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
        margin = 10
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
            if not self.underMouse():
                self._hide_window()

    def enterEvent(self, event):
        """鼠标进入时展开"""
        if self._hide_edge and self._is_hidden:
            self._show_window()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开时隐藏"""
        if self._hide_edge and not self._is_hidden and not self._menu_open:
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
        show_width = 4
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

    def contextMenuEvent(self, event):
        self._menu_open = True
        menu = QMenu(self)
        menu_tokens = get_theme_tokens(self.dark_mode)
        menu.setStyleSheet(build_menu_stylesheet(menu_tokens))

        # 背景透明度
        bg_opacity_menu = menu.addMenu('🎨 背景透明度')
        bg_slider_action = QWidgetAction(bg_opacity_menu)
        bg_slider_widget = QWidget()
        bg_slider_layout = QHBoxLayout(bg_slider_widget)
        bg_slider_layout.setContentsMargins(10, 4, 10, 4)
        bg_opacity_slider = QSlider(Qt.Horizontal)
        bg_opacity_slider.setMinimum(1)
        bg_opacity_slider.setMaximum(100)
        bg_opacity_slider.setValue(int(self.bg_opacity * 100))
        bg_opacity_slider.setFixedWidth(100)
        bg_opacity_slider.setStyleSheet(build_slider_stylesheet(menu_tokens))
        bg_val_label = QLabel(f'{int(self.bg_opacity * 100)}%')
        bg_val_label.setFont(QFont('Consolas', 8))
        bg_val_label.setStyleSheet(f"color: {menu_tokens['text']};")
        bg_val_label.setFixedWidth(32)

        def on_bg_slider_changed(val):
            bg_val_label.setText(f'{val}%')
            self._set_bg_opacity(val / 100)

        bg_opacity_slider.valueChanged.connect(on_bg_slider_changed)
        bg_opacity_slider.sliderReleased.connect(self._save_config)
        bg_slider_layout.addWidget(bg_opacity_slider)
        bg_slider_layout.addWidget(bg_val_label)
        bg_slider_action.setDefaultWidget(bg_slider_widget)
        bg_opacity_menu.addAction(bg_slider_action)

        # 文字透明度
        text_opacity_menu = menu.addMenu('🔤 文字透明度')
        text_slider_action = QWidgetAction(text_opacity_menu)
        text_slider_widget = QWidget()
        text_slider_layout = QHBoxLayout(text_slider_widget)
        text_slider_layout.setContentsMargins(10, 4, 10, 4)
        text_opacity_slider = QSlider(Qt.Horizontal)
        text_opacity_slider.setMinimum(10)
        text_opacity_slider.setMaximum(100)
        text_opacity_slider.setValue(int(self.text_opacity * 100))
        text_opacity_slider.setFixedWidth(100)
        text_opacity_slider.setStyleSheet(build_slider_stylesheet(menu_tokens))
        text_val_label = QLabel(f'{int(self.text_opacity * 100)}%')
        text_val_label.setFont(QFont('Consolas', 8))
        text_val_label.setStyleSheet(f"color: {menu_tokens['text']};")
        text_val_label.setFixedWidth(32)

        def on_text_slider_changed(val):
            text_val_label.setText(f'{val}%')
            self._set_text_opacity(val / 100)

        text_opacity_slider.valueChanged.connect(on_text_slider_changed)
        text_opacity_slider.sliderReleased.connect(self._save_config)
        text_slider_layout.addWidget(text_opacity_slider)
        text_slider_layout.addWidget(text_val_label)
        text_slider_action.setDefaultWidget(text_slider_widget)
        text_opacity_menu.addAction(text_slider_action)

        # 刷新间隔
        current_sec = self.refresh_interval // 1000
        interval_menu = menu.addMenu(f'⏱ 刷新间隔 (当前 {current_sec} 秒)')
        for sec in [1, 2, 3, 5, 10]:
            label = f'✓ {sec} 秒' if sec == current_sec else f'  {sec} 秒'
            action = interval_menu.addAction(label)
            action.triggered.connect(lambda checked, s=sec: self._set_interval(s))

        menu.addSeparator()

        # 立即刷新
        refresh_action = menu.addAction('🔄 立即刷新')
        refresh_action.triggered.connect(self._fetch_data)

        menu.addSeparator()

        # 字号大小
        font_menu = menu.addMenu(f'🔠 字号大小 (当前 {self.base_font_size})')
        for size in [8, 9, 10, 11, 12]:
            label = f'✓ {size}' if size == self.base_font_size else f'  {size}'
            action = font_menu.addAction(label)
            action.triggered.connect(lambda checked, s=size: self._set_font_size(s))

        # 隐私模式
        privacy_action = menu.addAction('👁 隐私模式 (仅显示状态圆点)')
        privacy_action.setCheckable(True)
        privacy_action.setChecked(self.privacy_mode)
        privacy_action.triggered.connect(self._toggle_privacy_mode)

        # 名称显示
        label_menu = menu.addMenu('🏷 名称显示')
        nickname_action = label_menu.addAction('显示昵称')
        nickname_action.setCheckable(True)
        nickname_action.setChecked(not self.show_code_in_label)
        nickname_action.triggered.connect(lambda: self._set_label_display_mode(False))
        code_action = label_menu.addAction('显示代码')
        code_action.setCheckable(True)
        code_action.setChecked(self.show_code_in_label)
        code_action.triggered.connect(lambda: self._set_label_display_mode(True))

        # 显示更新时间
        time_action = menu.addAction('🕐 显示更新时间')
        time_action.setCheckable(True)
        time_action.setChecked(self.show_update_time)
        time_action.triggered.connect(self._toggle_show_time)

        # 主题切换
        theme_action = menu.addAction('🌙 黑夜模式' if self.dark_mode else '☀️ 白天模式')
        theme_action.triggered.connect(self._toggle_theme)

        menu.addSeparator()

        # 指数显示设置
        indices_action = menu.addAction('📊 指数显示设置')
        indices_action.triggered.connect(self._open_stock_settings)

        # 金价换算器
        gold_converter_action = menu.addAction('🥇 金价换算器')
        gold_converter_action.triggered.connect(self._open_gold_converter)

        menu.addSeparator()

        # 退出
        quit_action = menu.addAction('❌ 退出')
        quit_action.triggered.connect(QApplication.quit)

        menu.exec_(event.globalPos())
        QTimer.singleShot(100, lambda: setattr(self, '_menu_open', False))

    def _set_bg_opacity(self, val):
        self.bg_opacity = val
        self.update()

    def _set_text_opacity(self, val):
        self.text_opacity = val
        for row in self.stock_rows.values():
            row.set_opacity(val)
        self.status_label.setStyleSheet(f'color: rgba(58, 74, 90, {val});')

    def _set_interval(self, sec):
        self.refresh_interval = sec * 1000
        self.timer.setInterval(self.refresh_interval)
        self._save_config()

    def _set_font_size(self, size):
        self.base_font_size = size
        for row in self.stock_rows.values():
            row.set_font_size(size)
            row.set_show_code_in_label(self.show_code_in_label)
        self._apply_status_font()
        self._adjust_window_size()
        self._save_config()

    def _toggle_privacy_mode(self):
        self.privacy_mode = not self.privacy_mode
        for row in self.stock_rows.values():
            row.set_privacy_mode(self.privacy_mode)
        self._adjust_window_size()
        self._save_config()

    def _set_label_display_mode(self, show_code):
        self.show_code_in_label = show_code
        for row in self.stock_rows.values():
            row.set_show_code_in_label(show_code)
        self._adjust_window_size()
        self._save_config()

    def _toggle_show_time(self):
        self.show_update_time = not self.show_update_time
        if self.show_update_time:
            self.status_label.show()
        else:
            self.status_label.hide()
        self._adjust_window_size()
        self._save_config()

    def _toggle_theme(self):
        """切换黑夜/白天模式"""
        self.dark_mode = not self.dark_mode
        self._init_colors()
        self._apply_theme()
        self._save_config()

    def _open_stock_settings(self):
        """打开指数显示设置对话框"""
        dialog = StockListDialog(
            self.all_stocks, self.visible_symbols, self, dark_mode=self.dark_mode
        )
        dialog.exec_()
        if dialog.result_symbols is not None:
            self.visible_symbols = dialog.result_symbols
            self._refresh_all_rows()
            self._save_config()

    def _open_gold_converter(self):
        """打开金价换算器"""
        dialog = GoldConverterDialog(self, dark_mode=self.dark_mode)
        premium = self.config.get('gold_premium', '')
        if premium:
            dialog._premium_input.setText(str(premium))
        screen = QApplication.primaryScreen().geometry()
        dialog.move(
            screen.center().x() - 170,
            screen.center().y() - 175
        )
        dialog.exec_()
        # 保存升贴水
        self.config['gold_premium'] = dialog._premium_input.text()
        self._save_config()

    def _refresh_all_rows(self):
        """刷新所有股票行的显示（用于重新构建界面）"""
        for symbol, row in list(self.stock_rows.items()):
            self.main_layout.removeWidget(row)
            row.deleteLater()
        self.stock_rows.clear()
        symbol_to_stock = {s.get('symbol'): s for s in self.all_stocks}
        for symbol in self.visible_symbols:
            if symbol in symbol_to_stock:
                stock = symbol_to_stock[symbol]
                row = StockRow(
                    get_display_quote_code(stock), stock['name'], stock['market'],
                    base_font_size=self.base_font_size
                )
                row.set_privacy_mode(self.privacy_mode)
                row.set_show_code_in_label(self.show_code_in_label)
                row.apply_theme(self.dark_mode, self.colors, self.text_opacity)
                self.stock_rows[symbol] = row
                self.main_layout.insertWidget(self.main_layout.count() - 1, row)
        self._adjust_window_size()

    def _adjust_window_size(self):
        """根据当前显示内容动态调整窗口宽高"""
        margins = self.main_layout.contentsMargins()
        spacing = self.main_layout.spacing()
        row_height = sum(row.height() for row in self.stock_rows.values())
        row_count = len(self.stock_rows)
        gaps = max(0, row_count - 1) * spacing
        status_height = self.status_label.sizeHint().height() if self.show_update_time else 0
        status_gap = spacing if self.show_update_time and row_count > 0 else 0
        new_height = margins.top() + row_height + gaps + status_gap + status_height + margins.bottom()
        row_width = max((row.get_content_width() for row in self.stock_rows.values()), default=120)
        status_width = self.status_label.fontMetrics().horizontalAdvance(self.status_label.text()) + 40
        new_width = max(120, row_width, status_width)
        if self._normal_geometry:
            self._normal_geometry.setWidth(new_width)
            self._normal_geometry.setHeight(new_height)
        self.setFixedWidth(new_width)
        self.setFixedHeight(new_height)

    def _get_config_path(self, for_read=True):
        """获取配置文件的正确路径（兼容打包后）

        for_read=True: 读取配置，从 _internal 文件夹获取
        for_read=False: 保存配置，保存到 exe 目录
        """
        if getattr(sys, 'frozen', False):
            if for_read:
                base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            else:
                base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, 'config.json')

    def _save_config(self):
        """保存当前配置到文件"""
        try:
            config_path = self._get_config_path(for_read=False)
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                config_data = self.config.copy()
            config_data['opacity'] = self.bg_opacity
            config_data['text_opacity'] = self.text_opacity
            config_data['refresh_interval'] = self.refresh_interval // 1000
            config_data['privacy_mode'] = self.privacy_mode
            config_data['show_code_in_label'] = self.show_code_in_label
            config_data['show_update_time'] = self.show_update_time
            config_data['dark_mode'] = self.dark_mode
            config_data['font_size'] = self.base_font_size
            config_data['data_source'] = 'sina'
            config_data['visible_stocks'] = self.visible_symbols
            if 'gold_premium' in self.config:
                config_data['gold_premium'] = self.config['gold_premium']
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f'保存配置失败: {e}')

    def closeEvent(self, event):
        """窗口关闭时清理所有后台线程"""
        stuck_threads = []
        if self._fetcher and self._fetcher.isRunning():
            self._fetcher.terminate()
            if not self._fetcher.wait(500):
                stuck_threads.append('数据获取线程')
        for fetcher in self._finished_fetchers:
            if fetcher.isRunning():
                fetcher.terminate()
                if not fetcher.wait(500):
                    stuck_threads.append('后台数据线程')
        if hasattr(self, 'timer'):
            self.timer.stop()
        if stuck_threads:
            QMessageBox.warning(
                self, '程序退出异常',
                f"检测到以下线程未正常结束:\n{', '.join(stuck_threads)}\n\n"
                f"这通常是由于网络请求超时导致的。\n\n"
                f"如果窗口未关闭，请按 Ctrl+Alt+Delete 打开任务管理器，\n"
                f"找到 python.exe 或 StockTicker.exe 并结束任务。"
            )
            import os
            QApplication.quit()
            os._exit(0)
        else:
            super().closeEvent(event)