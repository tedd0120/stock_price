# 实时分析金价 - 实现计划

## 概述
在右键菜单中添加"📈 实时分析金价"选项。点击后自动抓取伦敦金(XAU)过去24小时的60分钟K线数据，计算常用技术指标，然后调用用户配置的AI模型（OpenAI兼容接口）生成分析报告，包含趋势解读和买卖建议。

---

## 新增文件

### 1. `gold_analyzer.py` — 核心分析模块

#### 1.1 K线数据抓取
- **API**: 新浪财经K线接口
  `https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData?symbol=hf_XAU&scale=60&ma=no&datalen=24`
- 返回24根60分钟K线，每根包含: `day`(时间), `open`, `high`, `low`, `close`, `volume`
- 封装为 `fetch_gold_kline(datalen=24)` 函数，返回 `list[dict]`

#### 1.2 技术指标计算（纯Python，无需第三方库）
- **MACD** (12, 26, 9): DIF, DEA, MACD柱
- **RSI** (14): 相对强弱指标
- **布林带** (20, 2): 上轨、中轨、下轨
- **KDJ** (9, 3, 3): K值、D值、J值
- **MA5 / MA10**: 移动平均线
- **ATR** (14): 平均真实波幅

封装为 `calculate_indicators(kline_data: list[dict]) -> dict`，返回所有指标的最新值及近期趋势。

#### 1.3 AI分析调用
- 封装 `analyze_with_ai(api_url, api_key, model, kline_data, indicators) -> str`
- 构造结构化prompt，包含：
  - 24根K线的OHLCV数据
  - 所有技术指标数值
  - 当前价格
- 使用 `requests` 调用OpenAI兼容接口（`/v1/chat/completions`）
- 返回AI生成的分析文本

---

## 修改文件

### 2. `stock_widget.py` — UI集成

#### 2.1 新增 `GoldAnalysisDialog` 类（约200行）
参照 `GoldConverterDialog` 的设计模式：
- **窗口**: Frameless + translucent，固定尺寸约 520×600
- **标题栏**: "📈 金价AI分析" + 关闭按钮
- **设置区**: 可折叠的AI配置面板
  - API URL 输入框（默认: `https://api.openai.com`）
  - API Key 输入框（密码模式）
  - Model 输入框（默认: `gpt-4o-mini`）
  - "保存设置"按钮
- **分析按钮**: "开始分析"（醒目样式）
- **加载状态**: 按钮变为"分析中..."并禁用，或显示loading动画
- **结果区**: QTextBrowser（支持HTML渲染），显示：
  - K线数据摘要表格
  - 技术指标数值
  - AI分析报告（Markdown渲染为HTML）
  - 买卖建议高亮显示
- **主题**: 复用 `get_theme_tokens()` 支持深色/浅色模式

#### 2.2 右键菜单集成
在 `contextMenuEvent` 中（约1762行），在"金价换算器"下方添加：
```python
# 实时分析金价
gold_analysis_action = menu.addAction('📈 实时分析金价')
gold_analysis_action.triggered.connect(self._open_gold_analysis)
```

#### 2.3 新增 `_open_gold_analysis` 方法
参照 `_open_gold_converter` 模式：
```python
def _open_gold_analysis(self):
    dialog = GoldAnalysisDialog(self, dark_mode=self.dark_mode)
    # 从config加载AI设置
    ai_config = self.config.get('ai_settings', {})
    dialog.load_settings(ai_config)
    # 居中显示
    screen = QApplication.primaryScreen().geometry()
    dialog.move(screen.center().x() - 260, screen.center().y() - 300)
    dialog.exec_()
    # 保存AI设置到config
    self.config['ai_settings'] = dialog.save_settings()
    self._save_config()
```

### 3. `config.json` — 新增AI配置字段
```json
{
    "ai_settings": {
        "api_url": "https://api.openai.com",
        "api_key": "",
        "model": "gpt-4o-mini"
    }
}
```

---

## 技术细节

### K线API响应格式（新浪）
```json
{
    "day": "2026-03-31 09:00:00",
    "open": "3100.50",
    "high": "3105.20",
    "low": "3098.30",
    "close": "3102.80",
    "volume": "12345"
}
```

### AI Prompt模板
```
你是一位专业的黄金市场分析师。请根据以下伦敦金(XAU/USD)过去24小时的60分钟K线数据和技术指标，提供一份简洁的分析报告。

## K线数据（最近24小时，60分钟周期）
[OHLCV表格]

## 技术指标
- MACD: DIF=xx, DEA=xx, MACD柱=xx
- RSI(14): xx
- 布林带: 上轨=xx, 中轨=xx, 下轨=xx
- KDJ: K=xx, D=xx, J=xx
- MA5=xx, MA10=xx
- ATR(14)=xx

## 当前价格
xxxx 美元/盎司

请提供：
1. 短期趋势判断（多头/空头/震荡）
2. 关键支撑位和阻力位
3. 技术指标综合解读
4. 具体的买卖建议（做多/做空/观望，入场价位，止损建议）
5. 风险提示

注意：分析需简明扼要，重点突出可操作性建议。
```

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `gold_analyzer.py` | 新建 | K线抓取 + 技术指标计算 + AI调用 |
| `stock_widget.py` | 修改 | 添加菜单项 + `GoldAnalysisDialog` + `_open_gold_analysis` |
| `config.json` | 修改 | 新增 `ai_settings` 字段（首次使用时自动创建） |

## 依赖
- 无新增第三方依赖。K线获取和AI调用均使用已有的 `requests` 库，技术指标纯Python计算。

## 用户体验流程
1. 用户右键 → 点击"📈 实时分析金价"
2. 首次使用：填写AI API URL/Key/Model → 点保存
3. 点击"开始分析"
4. 显示加载中...
5. 自动抓取K线 → 计算指标 → 调用AI → 展示分析报告
6. 用户可随时修改AI设置或重新分析
