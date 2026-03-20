# 实时股价悬浮窗 - 开发过程总结 (dev.md)

本项目是一个基于 Python 和 PyQt5 构建的桌面半透明无边框悬浮窗应用，旨在为用户提供一个无干扰、可高度自定义的实时市场行情监控工具。

## 一、需求分析与技术选型

**核心需求：**
1. 实时显示国内（A股）和国外（美股、各类指数、商品）的最新行情。
2. 界面极致精简：深色半透明、无边框、不占任务栏、始终置顶。
3. 交互便捷：鼠标可任意拖动，具有快捷菜单调整使用偏好。

**技术选型：**
- **GUI 框架**：`PyQt5`（成熟稳定，对透明窗口和无边框窗口支持极佳）。
- **国内数据源**：`akshare`（开源且免费的东方财富接口）。
- **海外/指数数据源**：`yfinance`（Yahoo Finance 获取欧美及全球指数和商品）。

---

## 二、开发过程按步拆解

### Step 1. 构建基础架构与 UI 原型
- 设计了项目的基本目录结构：`main.py`（入口）、`stock_widget.py`（主要 UI）、`stock_fetcher.py`（获取数据的后台线程）和 `config.json`（外部配置）。
- 利用 PyQt5 设置窗口属性：`Qt.FramelessWindowHint`（无边框）、`Qt.WindowStaysOnTopHint`（置顶）、`Qt.Tool`（隐藏任务栏图标），并重写 `paintEvent` 绘制自带圆角的半透明纯色背景。

### Step 2. 实现实时数据获取模块
- 在 `stock_fetcher.py` 中，使用 `QThread` 创建了一个异步加载线程，避免网络请求导致 UI 界面卡顿。
- 初步整合了 `akshare.stock_zh_a_spot_em()` 和 `yfinance.Ticker().fast_info`，提取 “最新价”、“涨跌额”和“涨跌幅”。
- **问题及优化 1**：频繁轮询导致后台堆积。我们添加了阻塞判断与线程回收机制：如果上一个两秒请求尚未结束（因为网络拥堵等），自动跳过本次请求。

### Step 3. 解决网络与系统代理冲突
- **问题及优化 2**：用户本地运行了 Clash 等代理（例如 `127.0.0.1:7897` 甚至是 Fake-IP 模式），导致 `akshare` 默认拉取整个 A 股市场全部 5000+ 股票分页数据（58 页并发请求）时，连接池被代理耗尽/拒绝，触发 `Connection aborted, RemoteDisconnected` 错误。
- **最终方案**：彻底放弃全量请求，将 A 股数据获取变更为精确调用个股盘口接口 `ak.stock_bid_ask_em(symbol)`，按需获取单只标的，完美避免代理连接超载与风控阻断。

### Step 4. 丰富用户交互设计
- **拖动功能**：重写 `mousePressEvent` 和 `mouseMoveEvent` 获取相对坐标实现任意拖动。
- **右键菜单**：引入 `QMenu` 对 `QTimer` 的刷新间隔（1s~10s）以及窗体透明度进行配置。

### Step 5. 增强功能：边缘自动隐藏 (Edge Auto-hide)
- 用户希望悬浮窗具备像 QQ 那样的边缘自动隐藏行为。
- **实现逻辑**：
  1. 在 `mouseReleaseEvent` 触发后，判断窗体是否靠近屏幕的左/右/上边界（`< 10px`），如果是则吸附到边界上，并记录当前 `_normal_geometry`。
  2. 重写 `leaveEvent` 和 `enterEvent`：鼠标离开窗体时触发 `QPropertyAnimation` 平滑收起窗体，仅留 4px 细线；鼠标重新进入 4px 触发区时，执行展开动画，实现丝滑体验。

### Step 6. 增强功能：配置持久化与滑块调整
- 将原来的百分比菜单改为 10%~100% 的 `QSlider` 连续调节，并利用 `QWidgetAction` 嵌入。
- 引入更改实时写回机制（`opacity_slider.sliderReleased` 与 刷新时间修改后立刻调用 `_save_config` 覆写 `config.json`），退出应用时也会再保存一次以确保持久化，下次启动继承最后的操作习惯。

### Step 7. 指数与商品数据扩展
- 为满足用户同时关注 A 股指数和海外指数及商品的需求，由于 `akshare` 个股接口获取指数易出错，重新划分了市场字段。
- 将传统的 `A`（国内）和 `US`（海外个股）扩展出了 `IDX` 市场。
- 在 `stock_fetcher.py` 中将 `IDX` 类型交由更全能的 `yfinance` 处理，并在 `stock_widget.py` 取消了 `IDX` 的多余货币符号（如 `$`, `¥`），展示纯数字点位。

### Step 8. 打包分发与 `FileNotFoundError` 修复
- 尝试使用 PyInstaller 将应用打包为无控制台的脱离环境独立 `.exe` 文件（`--noconsole --onefile`）。
- **问题及优化 3**：打包后启动存在报错（`FileNotFoundError`）。发现是由于打包工具漏掉了 `akshare` 内部需要的 JS 或静态文本。
- **最终方案**：使用 `python -m PyInstaller --collect-all akshare` 强加载全部数据包以及自动兼容生成 `config.json` 的代码机制，完成最终交付件。
