"""
股价数据获取模块 - 统一使用新浪财经 API
不再依赖 akshare 和 yfinance
"""
import os
import re
import time
import requests
from PyQt5.QtCore import QThread, pyqtSignal

LOCAL_SEARCH_INDEXES = [
    {'symbol': 'sh000001', 'market': 'IDX', 'name': '上证指数',
     'aliases': ['上证', '上证综指', 'sh000001', '000001', '000001.SS']},
    {'symbol': 'sh000016', 'market': 'IDX', 'name': '上证50',
     'aliases': ['上证50', 'sz50', '000016', '000016.SS']},
    {'symbol': 'sh000300', 'market': 'IDX', 'name': '沪深300',
     'aliases': ['沪深', 'hs300', '300', '000300', '000300.SS']},
    {'symbol': 'sh000510', 'market': 'IDX', 'name': '中证A500',
     'aliases': ['a500', 'a50', '000510', '000510.SS']},
    {'symbol': 'sh000688', 'market': 'IDX', 'name': '科创50',
     'aliases': ['科创', 'kc50', '000688', '000688.SS']},
    {'symbol': 'sh000852', 'market': 'IDX', 'name': '中证1000',
     'aliases': ['1000', '000852', '000852.SS']},
    {'symbol': 'sh000905', 'market': 'IDX', 'name': '中证500',
     'aliases': ['500', 'zz500', '000905', '000905.SS']},
    {'symbol': 'sz399001', 'market': 'IDX', 'name': '深证成指',
     'aliases': ['深成指', '深证', '399001', 'sz399001', '399001.SZ']},
    {'symbol': 'sz399006', 'market': 'IDX', 'name': '创业板指',
     'aliases': ['创业板', 'cyb', '399006', 'sz399006', '399006.SZ']},
]

NF_FUTURE_SINA_CODES = {'im0', 'ih0', 'ic0', 'if0'}
HF_FUTURE_SINA_CODES = {'si', 'gc', 'cl', 'es', 'vx', 'ym', 'nq'}

JOINQUANT_FUTURES_URL = 'https://www.joinquant.com/data/dict/commodityFutures'
JOINQUANT_FUTURES_CACHE_TTL = 21600

_joinquant_futures_cache = []
_joinquant_futures_cache_ts = 0.0


class StockFetcher(QThread):
    """在后台线程中获取股价数据 (统一使用新浪财经)"""
    data_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, stock_list, source='sina'):
        super().__init__()
        self.stock_list = stock_list
        self.source = source
        self._running = True

    def run(self):
        try:
            results = self._fetch_all_sina(self.stock_list)
            if results:
                self.data_ready.emit(results)
        except Exception:
            import traceback
            self.error_occurred.emit(f'Fetch Error: {traceback.format_exc().splitlines()[-1]}')

    def _fetch_all_sina(self, stocks):
        try:
            results = {}
            headers = {'Referer': 'https://finance.sina.com.cn/'}
            mapping = []
            for s in stocks:
                sym = s['symbol']
                parsed = self._map_symbol(s)
                if parsed:
                    mapping.append((sym, parsed[0], parsed[1]))
            if not mapping:
                return {}
            url = f"http://hq.sinajs.cn/list={','.join([m[1] for m in mapping])}"
            resp = requests.get(url, headers=headers, timeout=5)
            text = resp.content.decode('gbk', errors='replace')
            lines = [line for line in text.strip().split('\n') if line.strip()]
            for i, line in enumerate(lines):
                if i >= len(mapping):
                    return results
                orig_sym, sina_code, p_type = mapping[i]
                if '"' not in line:
                    continue
                data_str = line.split('"')[1]
                if not data_str:
                    continue
                parts = data_str.split(',')
                parsed_data = self._parse_data(parts, p_type, orig_sym)
                if parsed_data:
                    results[orig_sym] = parsed_data
            return results
        except Exception as e:
            print(f'Sina Fetch Error: {e}')
            return results

    def _map_symbol(self, s):
        """将原始符号映射为新浪代码和解析类型"""
        return map_stock_to_sina_code(s)

    def _parse_data(self, parts, p_type, orig_sym):
        """根据不同类型解析数据"""
        try:
            update_time = ''
            price = 0.0
            prev = 0.0
            name = ''
            market = 'IDX'

            if p_type == 'A' and len(parts) > 3:
                name = parts[0]
                price = _safe_float(parts[3])
                prev = _safe_float(parts[2])
                market = 'A'
                if len(parts) > 31:
                    update_time = f'{parts[30]} {parts[31]}'
            elif p_type == 'US' and len(parts) > 1:
                name = parts[0]
                price = _safe_float(parts[1])
                if len(parts) > 26:
                    prev = _safe_float(parts[26])
                elif len(parts) > 10:
                    prev = _safe_float(parts[10])
                else:
                    prev = price
                market = 'US'
                if len(parts) > 3:
                    update_time = parts[3].strip()
            elif p_type == 'HK' and len(parts) > 6:
                name = parts[1]
                price = _safe_float(parts[6])
                prev = _safe_float(parts[3])
                market = 'HK'
                if len(parts) > 18:
                    update_time = f'{parts[17]} {parts[18]}'
            elif p_type == 'FUTURE' and len(parts) > 7:
                if not _is_number_text(parts[0]):
                    # 国内期货格式
                    name = parts[0] if parts[0] else orig_sym
                    price = _safe_float(parts[8]) or _safe_float(parts[6]) or _safe_float(parts[5])
                    prev = _safe_float(parts[27]) if len(parts) > 27 else 0.0
                    if prev == 0:
                        prev = _safe_float(parts[9]) or _safe_float(parts[10])
                    if len(parts) > 17:
                        update_time = parts[17]
                else:
                    # 国际期货格式（hf_开头）
                    name = parts[13] if len(parts) > 13 else orig_sym
                    price = _safe_float(parts[0])
                    prev = _safe_float(parts[7])
                    if len(parts) > 12:
                        update_time = f'{parts[12]} {parts[6]}'
                market = 'IDX'
            else:
                return None

            if prev == 0:
                prev = price
            change = price - prev
            pct = change / prev * 100 if prev != 0 else 0
            return {
                'name': name if name else orig_sym,
                'price': price,
                'change': change,
                'change_pct': pct,
                'market': market,
                'update_time': update_time.strip()
            }
        except Exception:
            return None

    def stop(self):
        self._running = False


def _safe_float(val):
    try:
        if not val or val == 'None':
            return 0.0
        f = float(val)
        return 0.0 if f != f else f
    except (ValueError, TypeError):
        return 0.0


def _is_number_text(value):
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _normalize_search_text(value):
    return ''.join((value or '').strip().lower().split())


def map_stock_to_sina_code(stock):
    """将配置项映射为新浪行情请求代码和解析类型"""
    sym = stock['symbol'].upper()
    market = stock['market']
    sina_code = stock.get('sina_code', '')
    code_lower = sina_code.lower()
    symbol_lower = stock['symbol'].lower()

    if re.match('^(sh|sz)\\d{6}$', symbol_lower):
        return (symbol_lower, 'A')
    elif symbol_lower.startswith('rt_hk'):
        return (symbol_lower, 'HK')
    elif symbol_lower.startswith('gb_'):
        return (symbol_lower, 'US')
    elif symbol_lower.startswith('hf_'):
        prefix, raw_code = symbol_lower.split('_', 1)
        return (f'{prefix}_{raw_code.upper()}', 'FUTURE')
    elif symbol_lower.startswith('nf_'):
        prefix, raw_code = symbol_lower.split('_', 1)
        return (f'{prefix}_{raw_code.upper()}', 'FUTURE')
    elif sina_code:
        if code_lower.startswith(('sh', 'sz')) and len(code_lower) == 8:
            return (code_lower, 'A')
        elif code_lower.startswith('rt_hk'):
            return (code_lower, 'HK')
        elif code_lower.startswith('gb_'):
            return (code_lower, 'US')
        elif code_lower.startswith('hf_') or code_lower.startswith('nf_'):
            prefix, raw_code = code_lower.split('_', 1)
            return (f'{prefix}_{raw_code.upper()}', 'FUTURE')
        elif code_lower in HF_FUTURE_SINA_CODES:
            return (f'hf_{code_lower.upper()}', 'FUTURE')
        elif code_lower in NF_FUTURE_SINA_CODES or re.match('^[a-z]{1,4}\\d+$', code_lower):
            return (f'nf_{code_lower.upper()}', 'FUTURE')
        elif code_lower.startswith('hk'):
            return (f'rt_hk{code_lower[2:].zfill(5)}', 'HK')
        elif re.match('^[a-z]{1,5}$', code_lower):
            return (f'gb_{code_lower}', 'US')
        else:
            return (code_lower, 'A')
    else:
        if market == 'A' or (market == 'IDX' and ('.SS' in sym or '.SZ' in sym)):
            code = sym.split('.')[0]
            if code.startswith('6') or sym.endswith('.SS'):
                return (f'sh{code}', 'A')
            else:
                return (f'sz{code}', 'A')
        elif market == 'IDX' and sym == '3032.HK':
            return ('rt_hk03032', 'HK')
        elif '.HK' in sym:
            code = sym.split('.')[0].zfill(5)
            return (f'rt_hk{code}', 'HK')
        elif market == 'US' or (market == 'IDX' and sym.startswith('^')):
            if sym == '^IXIC':
                return ('gb_ixic', 'US')
            elif sym == '^DJI':
                return ('gb_dji', 'US')
            elif sym == '^GSPC':
                return ('gb_inx', 'US')
            else:
                return (f'gb_{sym.lower()}', 'US')
        elif market == 'IDX':
            if sym == 'IF=F':
                return ('nf_IF0', 'FUTURE')
            elif sym == 'IH=F':
                return ('nf_IH0', 'FUTURE')
            elif sym == 'IC=F':
                return ('nf_IC0', 'FUTURE')
            elif sym == 'IM=F':
                return ('nf_IM0', 'FUTURE')
            elif sym == 'NQ=F':
                return ('hf_NQ0', 'FUTURE')
            elif sym == 'ES=F':
                return ('hf_ES0', 'FUTURE')
            elif sym == 'YM=F':
                return ('hf_YM0', 'FUTURE')
            elif sym == 'VX=F':
                return ('hf_VX0', 'FUTURE')
            elif sym in ['GC=F', 'XAU']:
                return ('hf_XAU', 'FUTURE')
            elif sym == 'BZ=F':
                return ('hf_OIL', 'FUTURE')
            elif sym == 'CL=F':
                return ('hf_CL', 'FUTURE')
    return None


def get_display_quote_code(stock):
    """获取界面展示用代码，尽量贴近新浪代码命名"""
    parsed = map_stock_to_sina_code(stock)
    if not parsed:
        return stock.get('symbol', '')
    return parsed[0]


def _dedupe_search_results(results):
    deduped = []
    seen = set()
    for item in results:
        symbol = item.get('symbol')
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        deduped.append(item)
    return deduped


def _build_local_search_candidates(local_candidates=None):
    candidates = []
    if local_candidates:
        candidates.extend(local_candidates)
    merged = []
    seen = set()
    for candidate in candidates:
        symbol = candidate.get('symbol')
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        merged.append(candidate)
    return merged


def _get_joinquant_futures_candidates():
    global _joinquant_futures_cache_ts
    global _joinquant_futures_cache
    now = time.time()
    if _joinquant_futures_cache and now - _joinquant_futures_cache_ts < JOINQUANT_FUTURES_CACHE_TTL:
        return _joinquant_futures_cache
    try:
        resp = requests.get(JOINQUANT_FUTURES_URL, timeout=(3, 5))
        resp.encoding = 'utf-8'
        rows = re.findall(
            '<tr>\\s*<td>(.*?)</td>\\s*<td>([A-Z0-9]+9999\\.[A-Z]+)</td>\\s*<td>([A-Z0-9]+8888\\.[A-Z]+)</td>\\s*</tr>',
            resp.text, re.S
        )
        candidates = []
        for raw_name, main_code, _ in rows:
            name = re.sub('<[^>]+>', '', raw_name).strip()
            base_name = name[:-2] if name.endswith('合约') else name
            code_prefix = main_code.split('9999', 1)[0]
            candidates.append({
                'symbol': f'nf_{code_prefix.upper()}0',
                'name': f'{base_name}主连',
                'market': 'IDX',
                'sina_code': f'nf_{code_prefix.upper()}0',
                'aliases': [name, base_name, main_code, code_prefix,
                           code_prefix.lower(), f'{code_prefix.upper()}9999']
            })
        _joinquant_futures_cache = candidates
        _joinquant_futures_cache_ts = now
    except Exception:
        return _joinquant_futures_cache
    return _joinquant_futures_cache


def _search_joinquant_futures(keyword):
    return _search_local_candidates(keyword, _get_joinquant_futures_candidates())


def _expand_results_with_related_futures(results):
    if not results:
        return []
    jq_candidates = _get_joinquant_futures_candidates()
    related = []
    primary_sina_code = results[0].get('sina_code', '').lower()
    if not primary_sina_code:
        return []
    symbols = {item.get('symbol', '') for item in results}
    for candidate in jq_candidates:
        candidate_sina = candidate.get('sina_code', '').lower()
        if not candidate_sina or candidate.get('symbol', '') in symbols:
            continue
        if candidate_sina == primary_sina_code:
            related.append({
                'symbol': candidate.get('symbol', ''),
                'name': candidate.get('name', ''),
                'market': candidate.get('market', 'IDX'),
                'sina_code': candidate.get('sina_code', '')
            })
    return related


def _score_local_candidate(keyword_norm, candidate):
    fields = [
        candidate.get('name', ''),
        candidate.get('symbol', ''),
        candidate.get('sina_code', ''),
        *candidate.get('aliases', [])
    ]
    matches = []
    for idx, field in enumerate(fields):
        normalized = _normalize_search_text(field)
        if not normalized:
            continue
        if normalized == keyword_norm:
            matches.append((0, idx, len(normalized)))
        elif normalized.startswith(keyword_norm):
            matches.append((1, idx, len(normalized)))
        elif keyword_norm in normalized:
            matches.append((2, idx, len(normalized)))
    if not matches:
        return None
    best = min(matches)
    return best + (candidate.get('name', ''),)


def _search_local_candidates(keyword, local_candidates=None):
    keyword_norm = _normalize_search_text(keyword)
    if not keyword_norm:
        return []
    scored = []
    for candidate in _build_local_search_candidates(local_candidates):
        score = _score_local_candidate(keyword_norm, candidate)
        if score is None:
            continue
        result = {
            'symbol': candidate.get('symbol', ''),
            'name': candidate.get('name', ''),
            'market': candidate.get('market', 'IDX')
        }
        if candidate.get('sina_code'):
            result['sina_code'] = candidate['sina_code']
        scored.append((score, result))
    scored.sort(key=lambda item: item[0])
    return [item[1] for item in scored]


def _should_use_local_only(keyword, local_results):
    if not local_results:
        return False
    keyword_norm = _normalize_search_text(keyword)
    if not keyword_norm:
        return False
    if re.search('[\\u4e00-\\u9fff]', keyword):
        return True
    return keyword_norm.isdigit() or any(ch in keyword_norm for ch in ['.', '^', '='])


def search_stocks(keyword, cancel_check=None, local_candidates=None):
    """使用新浪 suggest API 搜索股票/指数

    Args:
        keyword: 搜索关键词（支持股票名称、代码、拼音）
        cancel_check: 取消检查函数，返回 True 时停止搜索

    Returns:
        list: 匹配的股票列表，每项包含 symbol, name, market, sina_code
    """
    if not keyword or len(keyword.strip()) < 1:
        return []
    if cancel_check and cancel_check():
        return []

    user_local_results = _search_local_candidates(keyword, local_candidates)
    builtin_local_results = _search_local_candidates(keyword, LOCAL_SEARCH_INDEXES)
    futures_local_results = _search_joinquant_futures(keyword)
    local_results = _dedupe_search_results(
        user_local_results + builtin_local_results + futures_local_results
    )
    local_only_results = _dedupe_search_results(
        builtin_local_results + futures_local_results
    )

    if _should_use_local_only(keyword, local_only_results):
        return local_results

    try:
        from urllib.parse import quote
        encoded_keyword = quote(keyword)
        url = f'http://suggest3.sinajs.cn/suggest/key={encoded_keyword}'
        headers = {'Referer': 'https://finance.sina.com.cn/'}
        resp = requests.get(url, headers=headers, timeout=(2, 2))

        if cancel_check and cancel_check():
            return []

        text = resp.content.decode('gbk', errors='replace')
        match = re.search('var suggestvalue="([^"]*)"', text)
        if not match:
            return local_results

        content = match.group(1)
        if not content:
            return local_results

        results = []
        for item in content.split(';'):
            if not item.strip():
                continue
            parts = item.split(',')
            if len(parts) < 4:
                continue
            name = parts[0].strip()
            sina_code = parts[3].strip() if len(parts) > 3 else ''
            if not name or not sina_code:
                continue
            item_type = parts[1].strip() if len(parts) > 1 else ''
            short_code = parts[2].strip() if len(parts) > 2 else ''
            market, symbol = _parse_sina_code_to_symbol(
                sina_code, item_type=item_type,
                short_code=short_code, name=name
            )
            if symbol:
                results.append({
                    'symbol': symbol, 'name': name,
                    'market': market, 'sina_code': sina_code
                })

        def sort_key(item):
            symbol = item['symbol']
            if symbol.startswith(('sh', 'sz')):
                return (0, symbol)
            elif symbol.startswith('rt_hk'):
                return (1, symbol)
            elif symbol.startswith(('nf_', 'hf_')):
                return (2, symbol)
            elif symbol.startswith('gb_'):
                return (3, symbol)
            else:
                return (4, symbol)

        results.sort(key=sort_key)
        related_futures = _expand_results_with_related_futures(results)
        return _dedupe_search_results(local_results + related_futures + results)

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        if local_results:
            return local_results
        else:
            raise
    except Exception as e:
        print(f'搜索股票失败: {e}')
        return local_results


def _parse_sina_code_to_symbol(sina_code, item_type='', short_code='', name=''):
    """将新浪代码转换为标准 symbol 和 market

    Args:
        sina_code: 新浪返回的代码（如 sh000001, sz000002, hk00700 等）

    Returns:
        tuple: (market, symbol)
    """
    code_lower = sina_code.lower().strip()
    item_type = (item_type or '').strip()
    short_code = (short_code or '').strip().lower()
    name = (name or '').strip()

    if code_lower.isdigit():
        if len(code_lower) <= 5:
            code = code_lower.zfill(5)
            return ('HK', f'rt_hk{code}')
        elif len(code_lower) == 6:
            if item_type in {'31', '33'}:
                code = code_lower[-5:]
                return ('HK', f'rt_hk{code}')
            elif code_lower.startswith(('399', '159')):
                return ('IDX', f'sz{code_lower}')
            elif code_lower.startswith(('000', '001', '002', '003')):
                return ('IDX', f'sh{code_lower}')
            elif code_lower.startswith('6'):
                return ('A', f'sh{code_lower}')
            else:
                return ('A', f'sz{code_lower}')

    if code_lower.startswith('sh'):
        code = code_lower[2:]
        if code.startswith(('000', '001', '002', '003')):
            return ('IDX', f'sh{code}')
        else:
            return ('A', f'sh{code}')
    elif code_lower.startswith('sz'):
        code = code_lower[2:]
        if code.startswith(('000', '399')):
            return ('IDX', f'sz{code}')
        else:
            return ('A', f'sz{code}')
    elif code_lower.startswith('hk'):
        code = code_lower[2:].zfill(5)
        return ('HK', f'rt_hk{code}')
    elif code_lower.startswith('rt_hk'):
        code = code_lower[5:].zfill(5)
        return ('HK', f'rt_hk{code}')
    elif code_lower and code_lower[0].isalpha():
        futures_map = {
            'if0': ('IDX', 'nf_IF0'), 'ih0': ('IDX', 'nf_IH0'),
            'ic0': ('IDX', 'nf_IC0'), 'im0': ('IDX', 'nf_IM0'),
            'nq': ('IDX', 'hf_NQ0'), 'es': ('IDX', 'hf_ES0'),
            'ym': ('IDX', 'hf_YM0'), 'cl': ('IDX', 'hf_CL'),
            'gc': ('IDX', 'hf_XAU'), 'vx': ('IDX', 'hf_VX0'),
            'si': ('IDX', 'hf_SI')
        }
        if code_lower in futures_map:
            return futures_map[code_lower]
        elif re.match('^[a-z]{1,4}\\d+$', code_lower):
            return ('IDX', f'nf_{code_lower.upper()}')
        else:
            return ('US', f'gb_{code_lower}')
    else:
        return ('A', sina_code)