"""
金价AI分析模块 - K线抓取、技术指标计算、AI分析
"""
import json
import requests


# ──────────────── K线数据抓取 ────────────────

def fetch_gold_kline(datalen=24):
    """从 Yahoo Finance 获取 COMEX 黄金期货 60 分钟 K 线数据，返回最近 datalen 根有效 K 线。
    每根 K 线: {'time': str, 'open': float, 'high': float, 'low': float, 'close': float, 'volume': int}
    """
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/GC=F'
    params = {'interval': '1h', 'range': '3d'}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    result = data['chart']['result'][0]
    ts = result['timestamp']
    q = result['indicators']['quote'][0]

    import datetime
    candles = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q['open'][i], q['high'][i], q['low'][i], q['close'][i], q['volume'][i]
        if c is None or c == 0:
            continue
        dt = datetime.datetime.fromtimestamp(t)
        candles.append({
            'time': dt.strftime('%m-%d %H:%M'),
            'open': round(float(o), 2),
            'high': round(float(h), 2),
            'low': round(float(l), 2),
            'close': round(float(c), 2),
            'volume': int(v or 0),
        })
    return candles[-datalen:]


# ──────────────── 技术指标计算（纯 Python） ────────────────

def _ema(data, period):
    """计算指数移动平均"""
    if not data:
        return []
    k = 2.0 / (period + 1)
    result = [data[0]]
    for val in data[1:]:
        result.append(val * k + result[-1] * (1 - k))
    return result


def _sma(data, period):
    """简单移动平均，返回与 data 等长的列表（不足 period 的位置为 None）"""
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(data[i - period + 1:i + 1]) / period)
    return result


def calc_macd(closes, fast=12, slow=26, signal=9):
    """MACD 指标，返回 (dif_list, dea_list, macd_hist_list)"""
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = _ema(dif, signal)
    macd_hist = [2 * (d - e) for d, e in zip(dif, dea)]
    return dif, dea, macd_hist


def calc_rsi(closes, period=14):
    """RSI 指标"""
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result = [None]  # 第一个无 RSI
    for i in range(1, period):
        result.append(None)
    if avg_loss == 0:
        rsi_val = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_val = 100 - 100 / (1 + rs)
    result.append(rsi_val)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_val = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_val = 100 - 100 / (1 + rs)
        result.append(rsi_val)
    # 把 None 替换为 50
    return [v if v is not None else 50.0 for v in result]


def calc_bollinger(closes, period=20, nbdev=2):
    """布林带，返回 (upper, middle, lower)"""
    mid = _sma(closes, period)
    upper, lower = [], []
    for i in range(len(closes)):
        if mid[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            window = closes[i - period + 1:i + 1]
            std = (sum((x - mid[i]) ** 2 for x in window) / period) ** 0.5
            upper.append(mid[i] + nbdev * std)
            lower.append(mid[i] - nbdev * std)
    return upper, mid, lower


def calc_kdj(highs, lows, closes, n=9, m1=3, m2=3):
    """KDJ 指标"""
    k_list, d_list, j_list = [50.0], [50.0], [50.0]
    for i in range(1, len(closes)):
        start = max(0, i - n + 1)
        hh = max(highs[start:i + 1])
        ll = min(lows[start:i + 1])
        if hh == ll:
            rsv = 50.0
        else:
            rsv = (closes[i] - ll) / (hh - ll) * 100
        k = (2 / m1) * k_list[-1] + (1 / m1) * rsv
        d = (2 / m2) * d_list[-1] + (1 / m2) * k
        j = 3 * k - 2 * d
        k_list.append(k)
        d_list.append(d)
        j_list.append(j)
    return k_list, d_list, j_list


def calc_atr(highs, lows, closes, period=14):
    """ATR 平均真实波幅"""
    tr_list = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        tr_list.append(tr)
    atr_vals = _sma(tr_list, period)
    return [v if v is not None else tr_list[i] for i, v in enumerate(atr_vals)]


def calculate_indicators(kline_data):
    """计算所有技术指标，返回指标摘要字典"""
    closes = [c['close'] for c in kline_data]
    highs = [c['high'] for c in kline_data]
    lows = [c['low'] for c in kline_data]

    dif, dea, macd_hist = calc_macd(closes)
    rsi = calc_rsi(closes)
    boll_upper, boll_mid, boll_lower = calc_bollinger(closes)
    k_vals, d_vals, j_vals = calc_kdj(highs, lows, closes)
    atr = calc_atr(highs, lows, closes)
    ma5 = _sma(closes, 5)
    ma10 = _sma(closes, 10)

    idx = len(kline_data) - 1  # 最新一根
    return {
        'current_price': closes[idx],
        'macd': {
            'dif': round(dif[idx], 2),
            'dea': round(dea[idx], 2),
            'histogram': round(macd_hist[idx], 2),
        },
        'rsi': round(rsi[idx], 1),
        'bollinger': {
            'upper': round(boll_upper[idx], 2) if boll_upper[idx] else None,
            'mid': round(boll_mid[idx], 2) if boll_mid[idx] else None,
            'lower': round(boll_lower[idx], 2) if boll_lower[idx] else None,
        },
        'kdj': {
            'k': round(k_vals[idx], 1),
            'd': round(d_vals[idx], 1),
            'j': round(j_vals[idx], 1),
        },
        'atr': round(atr[idx], 2),
        'ma5': round(ma5[idx], 2) if ma5[idx] else None,
        'ma10': round(ma10[idx], 2) if ma10[idx] else None,
        # 近 5 根趋势
        'price_change_5': round(closes[idx] - closes[max(0, idx - 4)], 2),
    }


# ──────────────── AI 分析调用 ────────────────

def build_analysis_prompt(kline_data, indicators, custom_prompt=''):
    """构造 AI 分析用的 prompt。custom_prompt 为用户自定义提示词（附加到末尾）。"""
    # K线表格
    kline_table = '| 时间 | 开盘 | 最高 | 最低 | 收盘 | 成交量 |\n|---|---|---|---|---|---|\n'
    for c in kline_data:
        kline_table += f"| {c['time']} | {c['open']} | {c['high']} | {c['low']} | {c['close']} | {c['volume']} |\n"

    ind = indicators
    prompt = f"""你是一位专业的黄金市场分析师。请根据以下 COMEX 黄金期货(GC=F) 过去约24小时的60分钟K线数据和技术指标，提供一份简洁的分析报告。

## K线数据（60分钟周期）
{kline_table}

## 技术指标
- MACD: DIF={ind['macd']['dif']}, DEA={ind['macd']['dea']}, MACD柱={ind['macd']['histogram']}
- RSI(14): {ind['rsi']}
- 布林带: 上轨={ind['bollinger']['upper']}, 中轨={ind['bollinger']['mid']}, 下轨={ind['bollinger']['lower']}
- KDJ: K={ind['kdj']['k']}, D={ind['kdj']['d']}, J={ind['kdj']['j']}
- MA5={ind['ma5']}, MA10={ind['ma10']}
- ATR(14)={ind['atr']}
- 近5根K线价格变化: {ind['price_change_5']}

## 当前价格
{ind['current_price']} 美元/盎司

请用中文提供以下分析（使用Markdown格式）：
1. **短期趋势判断**（多头/空头/震荡）及理由
2. **关键支撑位和阻力位**
3. **技术指标综合解读**（每个指标说明了什么）
4. **具体买卖建议**（做多/做空/观望，入场价位，止损建议）
5. **风险提示**

要求：分析简明扼要，重点突出可操作性建议。不要用表格。"""
    if custom_prompt and custom_prompt.strip():
        prompt += f'\n\n## 附加要求\n{custom_prompt.strip()}'
    return prompt


def analyze_with_ai(api_url, api_key, model, kline_data, indicators, custom_prompt=''):
    """调用 Anthropic 兼容接口进行金价分析，返回分析文本"""
    prompt = build_analysis_prompt(kline_data, indicators, custom_prompt)

    # Anthropic Messages API
    url = f"{api_url.rstrip('/')}/v1/messages"
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
    }
    payload = {
        'model': model,
        'max_tokens': 2048,
        'messages': [{'role': 'user', 'content': prompt}],
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    # 解析 Anthropic Messages 响应
    content_blocks = data.get('content', [])
    text_parts = []
    for block in content_blocks:
        if block.get('type') == 'text':
            text_parts.append(block['text'])
    return '\n'.join(text_parts) if text_parts else 'AI 未返回有效内容。'


def test_api_connection(api_url, api_key, model):
    """测试 AI API 连通性，返回 (success: bool, message: str)"""
    try:
        url = f"{api_url.rstrip('/')}/v1/messages"
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
        }
        payload = {
            'model': model,
            'max_tokens': 64,
            'messages': [{'role': 'user', 'content': '回复OK'}],
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # 检查是否有 text 或 thinking 内容
        for block in data.get('content', []):
            btype = block.get('type', '')
            if btype == 'text' and block.get('text', '').strip():
                return True, f'连接成功！模型: {data.get("model", model)}'
            if btype == 'thinking' and block.get('thinking', '').strip():
                return True, f'连接成功！模型: {data.get("model", model)}'
        # 即使没有 text 内容，只要没报错就算连通
        if data.get('content'):
            return True, f'连接成功！模型: {data.get("model", model)}'
        return False, 'API 返回了空内容'
    except requests.exceptions.ConnectionError:
        return False, '连接失败：无法连接到服务器'
    except requests.exceptions.Timeout:
        return False, '连接超时（20秒）'
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else '?'
        try:
            detail = e.response.json() if e.response else {}
        except Exception:
            detail = {}
        msg = detail.get('error', {}).get('message', str(e)) if isinstance(detail, dict) else str(e)
        return False, f'HTTP {code}: {msg}'
    except Exception as e:
        return False, str(e)
