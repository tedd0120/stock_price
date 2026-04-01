"""
金价AI分析模块 - K线抓取、技术指标计算、AI分析
"""
import json
import datetime
import re
import requests


TWELVEDATA_API_URL = 'https://api.twelvedata.com/time_series'

GOLD_ANALYSIS_MODES = {
    '24h_hourly': {
        'interval': '1h',
        'outputsize': 24,
        'time_format': '%m-%d %H:%M',
        'period_text': '近24小时（60分钟周期）',
        'combined_title': '合并数据（60分钟周期，含OHLC与技术指标）',
        'raw_title': '合并数据（60分钟周期）',
        'ui_label': '近24小时（小时K）',
    },
    '30d_daily': {
        'interval': '1day',
        'outputsize': 30,
        'time_format': '%Y-%m-%d',
        'period_text': '近30日（日线周期）',
        'combined_title': '合并数据（日线周期，含OHLC与技术指标）',
        'raw_title': '合并数据（日线周期）',
        'ui_label': '近30日（日K）',
    },
}


def get_gold_analysis_mode_config(analysis_mode='24h_hourly'):
    key = analysis_mode if analysis_mode in GOLD_ANALYSIS_MODES else '24h_hourly'
    config = dict(GOLD_ANALYSIS_MODES[key])
    config['key'] = key
    return config


# ──────────────── 数据抓取 ────────────────

def _safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def fetch_london_gold_spot():
    """从新浪获取伦敦金现货(hf_XAU)实时价格，返回 float 或 0"""
    try:
        url = 'http://hq.sinajs.cn/list=hf_XAU'
        headers = {'Referer': 'https://finance.sina.com.cn/'}
        resp = requests.get(url, headers=headers, timeout=8)
        resp.encoding = 'gbk'
        line = resp.text.strip()
        val = line.split('"')[1]
        parts = val.split(',')
        return _safe_float(parts[0])
    except Exception:
        return 0.0


def fetch_gold_kline(datalen=None, twelvedata_api_key='', analysis_mode='24h_hourly'):
    """获取伦敦金(XAU/USD) K 线数据。
    优先使用 Twelve Data 的 XAU/USD Gold Spot K线。
    返回 (candles, source_name):
        candles: list[dict]，每根 {'time', 'open', 'high', 'low', 'close', 'volume'}
        source_name: str, 'Twelve Data XAU/USD Gold Spot' 或 ''
    """
    mode_config = get_gold_analysis_mode_config(analysis_mode)
    outputsize = datalen or mode_config['outputsize']
    candles = _fetch_twelvedata_kline(outputsize, twelvedata_api_key, analysis_mode=mode_config['key'])
    if candles:
        return candles, 'Twelve Data XAU/USD Gold Spot'
    return None, ''


def _fetch_twelvedata_kline(datalen, api_key, analysis_mode='24h_hourly'):
    if not api_key:
        return None
    mode_config = get_gold_analysis_mode_config(analysis_mode)
    try:
        params = {
            'symbol': 'XAU/USD',
            'interval': mode_config['interval'],
            'outputsize': datalen or mode_config['outputsize'],
            'timezone': 'Asia/Shanghai',
            'apikey': api_key,
        }
        resp = requests.get(TWELVEDATA_API_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') != 'ok':
            return None
        values = list(reversed(data.get('values') or []))
        candles = []
        for row in values:
            dt_text = (row.get('datetime') or '').strip()
            if not dt_text:
                continue
            if ' ' in dt_text:
                dt = datetime.datetime.strptime(dt_text, '%Y-%m-%d %H:%M:%S')
            else:
                dt = datetime.datetime.strptime(dt_text, '%Y-%m-%d')
            candles.append({
                'time': dt.strftime(mode_config['time_format']),
                'open': _safe_float(row.get('open')),
                'high': _safe_float(row.get('high')),
                'low': _safe_float(row.get('low')),
                'close': _safe_float(row.get('close')),
                'volume': 0,
            })
        outputsize = datalen or mode_config['outputsize']
        return candles[-outputsize:] if candles else None
    except Exception:
        return None


def _parse_sina_minline_rows(rows):
    points = []
    for row in rows or []:
        if not row:
            continue
        try:
            timestamp_text = row[-1]
            price = _safe_float(row[1])
            if not timestamp_text or price <= 0:
                continue
            dt = datetime.datetime.strptime(timestamp_text, '%Y-%m-%d %H:%M:%S')
            points.append({'dt': dt, 'price': round(price, 2)})
        except Exception:
            continue
    return points


def _aggregate_minline_to_hourly(points, datalen):
    buckets = {}
    for point in points:
        bucket = point['dt'].replace(minute=0, second=0, microsecond=0)
        price = point['price']
        if bucket not in buckets:
            buckets[bucket] = {
                'time': bucket.strftime('%m-%d %H:%M'),
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': 0,
            }
        else:
            buckets[bucket]['high'] = max(buckets[bucket]['high'], price)
            buckets[bucket]['low'] = min(buckets[bucket]['low'], price)
            buckets[bucket]['close'] = price
    candles = [buckets[key] for key in sorted(buckets.keys())]
    return candles[-datalen:] if candles else None


def _fetch_sina_kline(datalen):
    """从新浪获取伦敦金(XAU)分时数据并聚合成 60 分钟 K 线。"""
    try:
        url = 'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_XAU_MIN=/GlobalFuturesService.getGlobalFuturesMinLine'
        params = {
            'symbol': 'XAU',
            '_': f'{datetime.datetime.now().year}_{datetime.datetime.now().month}_{datetime.datetime.now().day}',
            'source': 'web',
        }
        headers = {
            'Referer': 'https://finance.sina.com.cn/money/future/hf.html',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        }
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        text = resp.text
        json_str = text[text.find('(') + 1:text.rfind(')')]
        if not json_str or '"__ERROR"' in json_str:
            return None
        data = json.loads(json_str)
        points = _parse_sina_minline_rows(data.get('minLine_1d', []))
        if not points:
            return None
        return _aggregate_minline_to_hourly(points, datalen)
    except Exception:
        return None


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
    """计算所有技术指标，返回最新摘要和完整序列"""
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

    idx = len(kline_data) - 1

    series = []
    for i, candle in enumerate(kline_data):
        series.append({
            'time': candle['time'],
            'close': round(closes[i], 2),
            'macd_dif': round(dif[i], 2),
            'macd_dea': round(dea[i], 2),
            'macd_hist': round(macd_hist[i], 2),
            'rsi': round(rsi[i], 1),
            'boll_upper': round(boll_upper[i], 2) if boll_upper[i] is not None else None,
            'boll_mid': round(boll_mid[i], 2) if boll_mid[i] is not None else None,
            'boll_lower': round(boll_lower[i], 2) if boll_lower[i] is not None else None,
            'kdj_k': round(k_vals[i], 1),
            'kdj_d': round(d_vals[i], 1),
            'kdj_j': round(j_vals[i], 1),
            'atr': round(atr[i], 2),
            'ma5': round(ma5[i], 2) if ma5[i] is not None else None,
            'ma10': round(ma10[i], 2) if ma10[i] is not None else None,
        })

    latest = series[idx]
    return {
        'current_price': closes[idx],
        'macd': {
            'dif': latest['macd_dif'],
            'dea': latest['macd_dea'],
            'histogram': latest['macd_hist'],
        },
        'rsi': latest['rsi'],
        'bollinger': {
            'upper': latest['boll_upper'],
            'mid': latest['boll_mid'],
            'lower': latest['boll_lower'],
        },
        'kdj': {
            'k': latest['kdj_k'],
            'd': latest['kdj_d'],
            'j': latest['kdj_j'],
        },
        'atr': latest['atr'],
        'ma5': latest['ma5'],
        'ma10': latest['ma10'],
        'price_change_5': round(closes[idx] - closes[max(0, idx - 4)], 2),
        'series': series,
    }


# ──────────────── AI 分析调用 ────────────────

PROMPT_SOURCE_NOTE = '{{source_note}}'
PROMPT_COMBINED_TABLE = '{{combined_table}}'
PROMPT_INDICATORS = '{{indicators_text}}'
PROMPT_PERIOD_TEXT = '{{period_text}}'
PROMPT_COMBINED_TITLE = '{{combined_title}}'


def get_default_analysis_prompt():
    """返回默认的金价分析提示词模板。"""
    return f"""你是一位专业的黄金市场分析师。请根据以下黄金{PROMPT_PERIOD_TEXT}的合并行情与技术指标数据，提供一份简洁的分析报告。
{PROMPT_SOURCE_NOTE}

## {PROMPT_COMBINED_TITLE}
{PROMPT_COMBINED_TABLE}

## 指标摘要
{PROMPT_INDICATORS}

请用中文提供以下分析（使用Markdown格式）：
1. **短期趋势判断**（多头/空头/震荡）及理由
2. **关键支撑位和阻力位**（基于当前分析标的价格体系）
3. **技术指标综合解读**（每个指标说明了什么）
4. **具体买卖建议**（做多/做空/观望，入场价位，止损建议）
5. **风险提示**

要求：分析简明扼要，重点突出可操作性建议。所有价位以当前分析标的价格体系为准。不要用表格。"""


def normalize_prompt_template(prompt_template=''):
    """规范化用户保存的提示词模板，兼容旧的附加提示词写法。"""
    text = (prompt_template or '').strip()
    if not text:
        return get_default_analysis_prompt()

    text = re.sub(
        r'请根据以下黄金.+?的合并行情与技术指标数据',
        f'请根据以下黄金{PROMPT_PERIOD_TEXT}的合并行情与技术指标数据',
        text,
        count=1,
    )
    text = re.sub(
        r'##\s*合并数据（.*?）',
        f'## {PROMPT_COMBINED_TITLE}',
        text,
        count=1,
    )

    if any(token in text for token in (
        PROMPT_SOURCE_NOTE,
        PROMPT_COMBINED_TABLE,
        PROMPT_INDICATORS,
        PROMPT_PERIOD_TEXT,
        PROMPT_COMBINED_TITLE,
    )):
        return text
    if '## 指标摘要' in text and '## 合并数据（' in text:
        return text
    return get_default_analysis_prompt() + f'\n\n## 附加要求\n{text}'


def render_prompt_template(prompt_template, source_note, combined_table, indicators_text,
                           period_text, combined_title):
    """将提示词模板中的占位符替换为实际分析数据。"""
    template = normalize_prompt_template(prompt_template)
    return (template
            .replace(PROMPT_SOURCE_NOTE, source_note)
            .replace(PROMPT_COMBINED_TABLE, combined_table)
            .replace(PROMPT_INDICATORS, indicators_text)
            .replace(PROMPT_PERIOD_TEXT, period_text)
            .replace(PROMPT_COMBINED_TITLE, combined_title))


def build_analysis_prompt(kline_data, indicators, prompt_template='', spot_price=0, kline_source='',
                          analysis_mode='24h_hourly'):
    """构造 AI 分析用的 prompt。prompt_template 为用户可覆盖编辑的完整提示词模板。"""
    mode_config = get_gold_analysis_mode_config(analysis_mode)
    ind = indicators
    latest_summary = '\n'.join([
        f"- 最新 MACD: DIF={ind['macd']['dif']}, DEA={ind['macd']['dea']}, MACD柱={ind['macd']['histogram']}",
        f"- 最新 RSI(14): {ind['rsi']}",
        f"- 最新布林带: 上轨={ind['bollinger']['upper']}, 中轨={ind['bollinger']['mid']}, 下轨={ind['bollinger']['lower']}",
        f"- 最新 KDJ: K={ind['kdj']['k']}, D={ind['kdj']['d']}, J={ind['kdj']['j']}",
        f"- 最新 MA5={ind['ma5']}, MA10={ind['ma10']}",
        f"- 最新 ATR(14)={ind['atr']}",
        f"- 近5根K线价格变化: {ind['price_change_5']}",
    ])
    combined_lines = [
        '| 时间 | 开盘 | 最高 | 最低 | 收盘 | 成交量 | DIF | DEA | MACD柱 | RSI | Boll上 | Boll中 | Boll下 | K | D | J | ATR | MA5 | MA10 |',
        '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|'
    ]
    for candle, row in zip(kline_data, ind.get('series', [])):
        combined_lines.append(
            f"| {candle['time']} | {candle['open']} | {candle['high']} | {candle['low']} | {candle['close']} | {candle['volume']} | {row['macd_dif']} | {row['macd_dea']} | {row['macd_hist']} | {row['rsi']} | {row['boll_upper']} | {row['boll_mid']} | {row['boll_lower']} | {row['kdj_k']} | {row['kdj_d']} | {row['kdj_j']} | {row['atr']} | {row['ma5']} | {row['ma10']} |"
        )
    combined_table = '\n'.join(combined_lines)

    source_note = ''
    if kline_source:
        source_note = f'\n当前分析K线数据来源：{kline_source}。'
    if spot_price > 0:
        source_note += f'\n\n## 伦敦金(XAU/USD)实时现货价\n{spot_price} 美元/盎司'

    return render_prompt_template(
        prompt_template,
        source_note,
        combined_table,
        latest_summary,
        mode_config['period_text'],
        mode_config['combined_title'],
    )


def _build_ai_headers(api_url, api_key):
    if 'openrouter.ai' in api_url:
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
    return {
        'Content-Type': 'application/json',
        'anthropic-version': '2023-06-01',
        'x-api-key': api_key,
    }


def _is_openrouter(api_url):
    return 'openrouter.ai' in api_url


def _extract_openrouter_text(data):
    choices = data.get('choices', [])
    if not choices:
        return ''
    message = choices[0].get('message', {})
    content = message.get('content', '')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text_parts.append(item.get('text', ''))
        return '\n'.join(part for part in text_parts if part)
    return ''


def _extract_anthropic_text(data):
    content_blocks = data.get('content', [])
    text_parts = []
    for block in content_blocks:
        if block.get('type') == 'text':
            text_parts.append(block['text'])
    return '\n'.join(text_parts)


def _normalize_chat_messages(messages):
    normalized = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = (message.get('role') or 'user').strip() or 'user'
        content = message.get('content', '')
        if isinstance(content, (str, list)):
            normalized_content = content
        else:
            normalized_content = str(content)
        normalized.append({'role': role, 'content': normalized_content})
    return normalized



def _split_anthropic_messages(messages):
    system_parts = []
    payload_messages = []
    for message in messages:
        role = message.get('role', 'user')
        content = message.get('content', '')
        if role == 'system':
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        system_parts.append(item.get('text', ''))
            else:
                system_parts.append(str(content))
            continue
        payload_messages.append({'role': role, 'content': content})
    return payload_messages, '\n\n'.join(part for part in system_parts if part)



def analyze_with_ai(api_url, api_key, model, messages):
    """调用 AI 接口进行多轮消息分析，返回分析文本"""
    normalized_messages = _normalize_chat_messages(messages)
    if not normalized_messages:
        raise ValueError('AI 消息不能为空')

    if _is_openrouter(api_url):
        url = f"{api_url.rstrip('/')}/v1/chat/completions"
        headers = _build_ai_headers(api_url, api_key)
        payload = {
            'model': model,
            'max_tokens': 2048,
            'messages': normalized_messages,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        text = _extract_openrouter_text(data)
        return text if text else 'AI 未返回有效内容。'

    anthropic_messages, system_text = _split_anthropic_messages(normalized_messages)
    if not anthropic_messages:
        raise ValueError('Anthropic 消息不能为空')

    url = f"{api_url.rstrip('/')}/v1/messages"
    headers = _build_ai_headers(api_url, api_key)
    payload = {
        'model': model,
        'max_tokens': 2048,
        'messages': anthropic_messages,
    }
    if system_text:
        payload['system'] = system_text

    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    text = _extract_anthropic_text(data)
    return text if text else 'AI 未返回有效内容。'


def test_api_connection(api_url, api_key, model):
    """测试 AI API 连通性，返回 (success: bool, message: str)"""
    try:
        headers = _build_ai_headers(api_url, api_key)
        payload = {
            'model': model,
            'max_tokens': 64,
            'messages': [{'role': 'user', 'content': '回复OK'}],
        }
        if _is_openrouter(api_url):
            url = f"{api_url.rstrip('/')}/v1/chat/completions"
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            text = _extract_openrouter_text(data)
            if text.strip() or data.get('choices'):
                return True, f'连接成功！模型: {model}'
            return False, 'API 返回了空内容'

        url = f"{api_url.rstrip('/')}/v1/messages"
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        text = _extract_anthropic_text(data)
        if text.strip() or data.get('content'):
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
