import csv
import glob
import json
import os
import re
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
from flask import Blueprint, Response, jsonify, request
from supabase import create_client, Client

from app.utils.price_cache import PriceCache

kr_bp = Blueprint('kr', __name__)

_cache = {}
_TICKER_MARKET_MAP = {}

# Supabase 클라이언트 초기화
_supabase_url = os.environ.get("SUPABASE_URL")
_supabase_key = os.environ.get("SUPABASE_KEY")
_supabase: Client = create_client(_supabase_url, _supabase_key) if _supabase_url and _supabase_key else None


def _ensure_market_map():
    """종목별 거래소 접미사(.KS/.KQ) 맵을 구축한다."""
    global _TICKER_MARKET_MAP
    if _TICKER_MARKET_MAP:
        return
    try:
        universe = _build_stock_universe()
        for s in universe:
            ticker = s['ticker'].upper()
            market = s['market'].upper() if s.get('market') else ''
            # KOSPI면 .KS, 그 외(KOSDAQ)는 .KQ
            suffix = '.KS' if 'KOSPI' in market else '.KQ'
            _TICKER_MARKET_MAP[ticker] = suffix
    except Exception:
        pass


def _cached_response(ttl_seconds=300):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = f"{fn.__name__}:{request.full_path}"
            now = time.time()
            if key in _cache:
                data, expires_at = _cache[key]
                if now < expires_at:
                    return data
            result = fn(*args, **kwargs)
            _cache[key] = (result, now + ttl_seconds)
            return result
        return wrapper
    return decorator


DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'kr_market', 'data')


@kr_bp.route('/health')
def health():
    return jsonify({"status": "ok"})


_STOP_PCT   = 0.05   # 손절 -5%
_TARGET_PCT = 0.15   # 목표 +15%

def _normalize_vcp(s, signal_date=''):
    """VCP 시그널 필드를 프론트엔드 공통 포맷으로 정규화."""
    pivot = s.get('pivot_high') or 0
    entry = int(s.get('entry_price') or pivot)   # pivot_high를 진입가 fallback으로 사용

    # 손절/목표가 — 원본 값 우선, 없으면 5%/15% 공식 적용
    stop   = int(s.get('stop_price')   or (entry * (1 - _STOP_PCT)))
    target = int(s.get('target_price') or (entry * (1 + _TARGET_PCT)))

    # VCP 수축 정보
    c1  = round(s.get('c1',  0) or 0, 1)
    c2  = round(s.get('c2',  0) or 0, 1)
    c3  = round(s.get('c3',  0) or 0, 1)
    r12 = round(s.get('r12', 0) or 0, 2)
    r23 = round(s.get('r23', 0) or 0, 2)
    atrp = round(s.get('atrp', 0) or 0, 2)

    return {
        'stock_code':   s.get('code', ''),
        'stock_name':   s.get('name', ''),
        'market':       s.get('market', ''),
        'grade':        s.get('grade', ''),
        'score':        s.get('score', 0),
        'entry_price':  entry,
        'stop_price':   stop,
        'target_price': target,
        'current_price':s.get('current_price', 0),
        'return_pct':   s.get('return_pct', 0),
        'status':       s.get('status', 'OPEN'),
        'signal_date':  signal_date,
        'pivot_high':   pivot,
        'atrp':         atrp,
        'c1': c1, 'c2': c2, 'c3': c3,
        'r12': r12, 'r23': r23,
        'foreign_5d':   s.get('foreign_5d', 0),
        'inst_5d':      s.get('inst_5d', 0),
    }


def _find_latest_vcp_file():
    """vcp_signals.json vs vcp_signals_YYYYMMDD.json 중 시그널이 있는 최신 파일 경로 반환."""
    main = os.path.join(DATA_DIR, 'vcp_signals.json')
    dated = sorted(glob.glob(os.path.join(DATA_DIR, 'vcp_signals_[0-9]*.json')), reverse=True)

    main_date = ''
    if os.path.exists(main):
        try:
            main_date = json.load(open(main, encoding='utf-8')).get('date', '')
        except Exception:
            pass

    if dated:
        m = re.search(r'vcp_signals_(\d{8})\.json$', dated[0])
        if m:
            d = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
            if d > main_date:
                try:
                    content = json.load(open(dated[0], encoding='utf-8'))
                    sigs = content.get('signals', []) if isinstance(content, dict) else content
                    if sigs:  # 시그널이 있을 때만 dated 파일 사용
                        return dated[0]
                except Exception:
                    pass

    return main if os.path.exists(main) else None


@kr_bp.route('/signals')
@_cached_response(ttl_seconds=300)
def signals():
    try:
        filepath = _find_latest_vcp_file()
        if not filepath:
            return jsonify({"signals": [], "count": 0, "message": "VCP 시그널 데이터가 없습니다."})

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        signal_date = data.get('date', '')
        raw_list    = data.get('signals', [])
        signal_list = [_normalize_vcp(s, signal_date) for s in raw_list]

        # 현재가 보완: daily_prices → yfinance 순으로 시도
        try:
            dp = _load_daily_prices()
            missing = []
            for sig in signal_list:
                rows = dp.get(sig['stock_code'], [])
                if rows:
                    sig['current_price'] = rows[-1].get('close', 0)
                else:
                    missing.append(sig)

            if missing:
                import yfinance as yf
                tickers_yf = [
                    f"{s['stock_code']}.{'KS' if 'KOSPI' in s['market'].upper() else 'KQ'}"
                    for s in missing
                ]
                try:
                    batch = yf.download(tickers_yf, period='2d', progress=False, auto_adjust=True)
                    close = batch['Close'] if 'Close' in batch else batch
                    for sig, tf in zip(missing, tickers_yf):
                        try:
                            if len(tickers_yf) == 1:
                                price = float(close.dropna().iloc[-1])
                            else:
                                price = float(close[tf].dropna().iloc[-1])
                            sig['current_price'] = int(price)
                        except Exception:
                            pass
                except Exception:
                    pass

            for sig in signal_list:
                entry = sig['entry_price'] or 0
                cur   = sig['current_price'] or 0
                if entry > 0 and cur > 0:
                    sig['return_pct'] = round((cur - entry) / entry * 100, 2)
        except Exception:
            pass

        signal_list.sort(key=lambda s: s['score'], reverse=True)

        return jsonify({
            "signals": signal_list,
            "count": len(signal_list),
            "generated_at": signal_date,
            "source": "vcp_live",
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kr_bp.route('/vcp/dates')
@_cached_response(ttl_seconds=300)
def vcp_dates():
    """vcp_signals_YYYYMMDD.json 파일명에서 날짜 목록 + 시그널 수를 반환."""
    try:
        files = glob.glob(os.path.join(DATA_DIR, 'vcp_signals_[0-9]*.json'))
        dates = []
        counts = {}
        for f in files:
            m = re.search(r'vcp_signals_(\d{8})\.json$', f)
            if m:
                d = m.group(1)
                dates.append(d)
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    counts[d] = len(data.get('signals', [])) if isinstance(data, dict) else len(data)
                except Exception:
                    counts[d] = 0
        dates = [d for d in dates if counts.get(d, 0) > 0]
        dates.sort(reverse=True)
        return jsonify({"dates": dates, "count": len(dates), "counts": counts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kr_bp.route('/vcp/history/<date_str>')
@_cached_response(ttl_seconds=300)
def vcp_history(date_str):
    """특정 날짜의 VCP 시그널을 반환."""
    try:
        if not re.match(r'^\d{8}$', date_str):
            return jsonify({"error": "Invalid date format. Use YYYYMMDD."}), 400

        filepath = os.path.join(DATA_DIR, f'vcp_signals_{date_str}.json')
        if not os.path.exists(filepath):
            return jsonify({"error": f"No data for date {date_str}"}), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 리스트 형태(구버전) 호환
        if isinstance(data, list):
            iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            signal_list = [_normalize_vcp(s, iso) for s in data]
            return jsonify({"signals": signal_list, "count": len(signal_list), "generated_at": iso})

        signal_date = data.get('date', '')
        raw_list    = data.get('signals', [])
        signal_list = [_normalize_vcp(s, signal_date) for s in raw_list]
        signal_list.sort(key=lambda s: s['score'], reverse=True)
        return jsonify({"signals": signal_list, "count": len(signal_list), "generated_at": signal_date})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _find_latest_results_file():
    """jongga_v2_results_*.json 중 최신 파일 경로를 반환."""
    pattern = os.path.join(DATA_DIR, 'jongga_v2_results_*.json')
    files = glob.glob(pattern)
    if not files:
        return None
    files.sort(reverse=True)
    return files[0]


def _extract_dates_from_results():
    """jongga_v2_results_*.json 파일명에서 날짜를 추출하여 최신순 반환."""
    pattern = os.path.join(DATA_DIR, 'jongga_v2_results_*.json')
    files = glob.glob(pattern)
    dates = []
    for f in files:
        m = re.search(r'jongga_v2_results_(\d{8})\.json$', f)
        if m:
            dates.append(m.group(1))
    dates.sort(reverse=True)
    return dates


@kr_bp.route('/jongga-v2/latest')
@_cached_response(ttl_seconds=300)
def jongga_v2_latest():
    try:
        latest_fp = os.path.join(DATA_DIR, 'jongga_v2_latest.json')
        dated_fp  = _find_latest_results_file()

        # 두 파일 모두 없으면 빈 응답
        if not os.path.exists(latest_fp) and not dated_fp:
            return jsonify({"signals": [], "message": "No data"})

        filepath = latest_fp if os.path.exists(latest_fp) else dated_fp

        # dated 파일이 latest.json보다 더 최신이면 dated 파일 사용
        if dated_fp and os.path.exists(latest_fp):
            m = re.search(r'jongga_v2_results_(\d{8})\.json$', dated_fp)
            if m:
                dated_date = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
                try:
                    latest_date = json.load(open(latest_fp, encoding='utf-8')).get('date', '')
                    if dated_date > latest_date:
                        filepath = dated_fp
                except Exception:
                    filepath = dated_fp

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kr_bp.route('/jongga-v2/dates')
@_cached_response(ttl_seconds=300)
def jongga_v2_dates():
    try:
        files = glob.glob(os.path.join(DATA_DIR, 'jongga_v2_results_[0-9]*.json'))
        dates = []
        counts = {}
        for f in files:
            m = re.search(r'jongga_v2_results_(\d{8})\.json$', f)
            if m:
                d = m.group(1)
                dates.append(d)
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    counts[d] = len(data.get('signals', [])) if isinstance(data, dict) else len(data)
                except Exception:
                    counts[d] = 0
        dates = [d for d in dates if counts.get(d, 0) > 0]
        dates.sort(reverse=True)
        return jsonify({"dates": dates, "count": len(dates), "counts": counts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kr_bp.route('/jongga-v2/history/<date_str>')
@_cached_response(ttl_seconds=300)
def jongga_v2_history(date_str):
    try:
        if not re.match(r'^\d{8}$', date_str):
            return jsonify({"error": "Invalid date format. Use YYYYMMDD."}), 400

        filepath = os.path.join(DATA_DIR, f'jongga_v2_results_{date_str}.json')

        if not os.path.exists(filepath):
            return jsonify({"error": f"No data for date {date_str}"}), 404

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _strategy_dates(prefix: str):
    """날짜별 파일 목록 + 시그널 수 반환 헬퍼."""
    files = glob.glob(os.path.join(DATA_DIR, f'{prefix}_[0-9]*.json'))
    dates = []
    counts = {}
    for f in files:
        m = re.search(rf'{prefix}_(\d{{8}})\.json$', f)
        if m:
            d = m.group(1)
            dates.append(d)
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                counts[d] = len(data.get('signals', [])) if isinstance(data, dict) else len(data)
            except Exception:
                counts[d] = 0
    dates = [d for d in dates if counts.get(d, 0) > 0]
    dates.sort(reverse=True)
    return jsonify({"dates": dates, "count": len(dates), "counts": counts})


def _strategy_history(prefix: str, date_str: str):
    """특정 날짜 전략 파일 반환 헬퍼."""
    if not re.match(r'^\d{8}$', date_str):
        return jsonify({"error": "Invalid date format. Use YYYYMMDD."}), 400
    filepath = os.path.join(DATA_DIR, f'{prefix}_{date_str}.json')
    if not os.path.exists(filepath):
        return jsonify({"error": f"No data for date {date_str}"}), 404
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kr_bp.route('/flow-momentum/dates')
@_cached_response(ttl_seconds=300)
def flow_momentum_dates():
    return _strategy_dates('flow_momentum')


@kr_bp.route('/flow-momentum/history/<date_str>')
@_cached_response(ttl_seconds=300)
def flow_momentum_history(date_str):
    return _strategy_history('flow_momentum', date_str)


@kr_bp.route('/narrative-momentum/dates')
@_cached_response(ttl_seconds=300)
def narrative_momentum_dates():
    return _strategy_dates('narrative_momentum')


@kr_bp.route('/narrative-momentum/history/<date_str>')
@_cached_response(ttl_seconds=300)
def narrative_momentum_history(date_str):
    return _strategy_history('narrative_momentum', date_str)


@kr_bp.route('/sector-rotation/dates')
@_cached_response(ttl_seconds=300)
def sector_rotation_dates():
    return _strategy_dates('sector_rotation')


@kr_bp.route('/sector-rotation/history/<date_str>')
@_cached_response(ttl_seconds=300)
def sector_rotation_history(date_str):
    return _strategy_history('sector_rotation', date_str)


@kr_bp.route('/contrarian/dates')
@_cached_response(ttl_seconds=300)
def contrarian_dates():
    return _strategy_dates('contrarian')


@kr_bp.route('/contrarian/history/<date_str>')
@_cached_response(ttl_seconds=300)
def contrarian_history(date_str):
    return _strategy_history('contrarian', date_str)


@kr_bp.route('/vcp-cumulative')
@_cached_response(ttl_seconds=120)
def vcp_cumulative():
    try:
        # 모든 vcp_signals*.json 에서 시그널 수집
        results = []
        # 날짜별 파일 (파일명에서 날짜 추출)
        for fp in sorted(glob.glob(os.path.join(DATA_DIR, 'vcp_signals_*.json'))):
            m = re.search(r'vcp_signals_(\d{8})\.json$', fp)
            signal_date = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else ''
            raw = json.load(open(fp, 'r', encoding='utf-8'))
            sigs = raw if isinstance(raw, list) else raw.get('signals', [])
            for s in sigs:
                results.append(_normalize_vcp(s, signal_date))
        # 최신 vcp_signals.json (중복 제거: stock_code+signal_date 기준)
        main_path = os.path.join(DATA_DIR, 'vcp_signals.json')
        if os.path.exists(main_path):
            d = json.load(open(main_path, 'r', encoding='utf-8'))
            signal_date = d.get('date', '')
            existing = {(r['stock_code'], r['signal_date']) for r in results}
            for s in d.get('signals', []):
                norm = _normalize_vcp(s, signal_date)
                if (norm['stock_code'], norm['signal_date']) not in existing:
                    results.append(norm)

        # 통계
        closed = [r for r in results if r['status'] == 'CLOSED']
        wins   = [r for r in closed if r['return_pct'] > 0]
        win_rate  = round(len(wins) / len(closed) * 100, 2) if closed else 0.0
        avg_return= round(sum(r['return_pct'] for r in closed) / len(closed), 2) if closed else 0.0
        total_return = round(sum(r['return_pct'] for r in closed), 2)

        grade_stats = {}
        for r in closed:
            g = r.get('grade', '')
            grade_stats.setdefault(g, []).append(r['return_pct'])
        grade_stats = {
            g: {
                'count': len(v),
                'win_rate': round(len([x for x in v if x > 0]) / len(v) * 100, 2),
                'avg_return': round(sum(v) / len(v), 2),
            }
            for g, v in sorted(grade_stats.items())
        }

        # 페이지네이션 (최신순)
        results.sort(key=lambda r: r['signal_date'], reverse=True)
        page     = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 30, type=int)
        total    = len(results)
        paged    = results[(page - 1) * per_page: page * per_page]

        return jsonify({
            'stats': {
                'total': total,
                'closed': len(closed),
                'open': len(results) - len(closed),
                'win_rate': win_rate,
                'avg_return': avg_return,
                'total_return': total_return,
                'grade_stats': grade_stats,
            },
            'signals': paged,
            'page': page,
            'per_page': per_page,
            'total_pages': max(1, (total + per_page - 1) // per_page),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@kr_bp.route('/backtest-summary')
@_cached_response(ttl_seconds=300)
def backtest_summary():
    try:
        # VCP 통계
        vcp_signals = []
        for fp in glob.glob(os.path.join(DATA_DIR, 'vcp_signals*.json')):
            raw = json.load(open(fp, 'r', encoding='utf-8'))
            sigs = raw if isinstance(raw, list) else raw.get('signals', [])
            vcp_signals.extend(sigs)
        vcp_closed = [s for s in vcp_signals if s.get('status') == 'CLOSED']
        vcp_wins   = [s for s in vcp_closed if s.get('return_pct', 0) > 0]
        vcp_wr     = round(len(vcp_wins) / len(vcp_closed) * 100, 2) if vcp_closed else 0.0
        vcp_avg    = round(sum(s.get('return_pct', 0) for s in vcp_closed) / len(vcp_closed), 2) if vcp_closed else 0.0
        gross_win  = sum(s.get('return_pct', 0) for s in vcp_wins)
        gross_loss = abs(sum(s.get('return_pct', 0) for s in vcp_closed if s.get('return_pct', 0) <= 0))
        vcp_pf     = round(gross_win / gross_loss, 2) if gross_loss else None

        # 종가베팅 통계 (jongga-v2/cumulative 로직 재활용)
        all_jongga = []
        for fp in glob.glob(os.path.join(DATA_DIR, 'jongga_v2_results_*.json')):
            d = json.load(open(fp, 'r', encoding='utf-8'))
            all_jongga.extend(d.get('signals', []))
        daily_prices = _load_daily_prices()
        cb_results = []
        for s in all_jongga:
            outcome, roi_pct, _ = _judge_outcome(s, daily_prices.get(s.get('stock_code', ''), []))
            cb_results.append({'outcome': outcome, 'roi_pct': roi_pct})
        cb_closed = [r for r in cb_results if r['outcome'] != 'OPEN']
        cb_wins   = [r for r in cb_closed if r['outcome'] == 'TARGET_HIT']
        cb_wr     = round(len(cb_wins) / len(cb_closed) * 100, 2) if cb_closed else 0.0
        cb_avg    = round(sum(r['roi_pct'] for r in cb_closed) / len(cb_closed), 2) if cb_closed else 0.0

        return jsonify({
            'vcp': {
                'count': len(vcp_closed),
                'win_rate': vcp_wr,
                'avg_return': vcp_avg,
                'profit_factor': vcp_pf,
                'status': 'ok' if vcp_closed else 'Accumulating',
            },
            'closing_bet': {
                'count': len(cb_closed),
                'win_rate': cb_wr,
                'avg_return': cb_avg,
                'status': 'ok' if cb_closed else 'Accumulating',
            },
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── market-gate helpers ──────────────────────────────────────────

_NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _parse_int(val):
    try:
        return int(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _fetch_index_yf(yf_code: str):
    """yfinance로 지수 직전 종가와 등락률을 반환한다."""
    try:
        hist = yf.Ticker(yf_code).history(period='5d')
        if len(hist) < 2:
            return None
        close_today = round(float(hist['Close'].iloc[-1]), 2)
        close_prev  = round(float(hist['Close'].iloc[-2]), 2)
        change_pct  = round((close_today - close_prev) / close_prev * 100, 2) if close_prev else 0.0
        return {'close': close_today, 'change_pct': change_pct}
    except Exception:
        return None


def _fetch_kodex200_yf(days: int = 220):
    """yfinance로 KODEX200(069500.KS) 일봉 종가를 가져온다 (날짜 오름차순)."""
    try:
        hist = yf.Ticker('069500.KS').history(period='1y')
        if hist.empty:
            return []
        return [
            {"date": str(idx.date()), "close": round(float(row['Close']))}
            for idx, row in hist.tail(days).iterrows()
        ]
    except Exception:
        return []


def _fetch_chart_closes(code, days=220):
    """네이버 금융에서 일봉 종가 리스트를 가져온다 (날짜 오름차순)."""
    base_url = f"https://finance.naver.com/item/sise_day.naver?code={code}"
    headers = {**_NAVER_HEADERS, "Referer": base_url}
    rows = []
    page = 1

    while len(rows) < days:
        resp = requests.get(f"{base_url}&page={page}", headers=headers, timeout=5)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="type2")
        if not table:
            break

        found = False
        for tr in table.find_all("tr"):
            cols = tr.find_all("td")
            if len(cols) < 7:
                continue
            date_text = cols[0].get_text(strip=True)
            if not date_text:
                continue
            found = True
            rows.append({
                "date": date_text,
                "close": _parse_int(cols[1].get_text()),
            })
            if len(rows) >= days:
                break

        if not found:
            break
        page += 1
        time.sleep(0.15)

    rows.reverse()
    return rows


def _calc_ma(closes, window):
    """종가 리스트에서 이동평균 계산."""
    if len(closes) < window:
        return None
    return round(sum(closes[-window:]) / window)


def _fetch_sector_changes():
    """네이버 증권 업종별 시세에서 섹터 등락률을 가져온다."""
    url = "https://finance.naver.com/sise/sise_group.naver?type=upjong"
    resp = requests.get(url, headers=_NAVER_HEADERS, timeout=5)
    resp.encoding = "euc-kr"
    soup = BeautifulSoup(resp.text, "html.parser")

    sectors = []
    table = soup.find("table", class_="type_1")
    if not table:
        return sectors

    for tr in table.find_all("tr"):
        cols = tr.find_all("td")
        if len(cols) < 2:
            continue
        a_tag = cols[0].find("a")
        if not a_tag:
            continue
        name = a_tag.get_text(strip=True)
        if not name:
            continue
        change_text = cols[1].get_text(strip=True).replace("%", "").replace(",", "")
        try:
            change_pct = float(change_text)
        except ValueError:
            change_pct = 0.0
        sectors.append({"name": name, "change_pct": change_pct})

    sectors.sort(key=lambda s: s["change_pct"], reverse=True)
    return sectors


# ── market-gate endpoint ─────────────────────────────────────────

@kr_bp.route('/market-gate')
@_cached_response(ttl_seconds=300)
def market_gate():
    try:
        # KODEX200 · 섹터 · KOSPI · KOSDAQ 4개 동시 수집
        with ThreadPoolExecutor(max_workers=4) as ex:
            f_kodex   = ex.submit(_fetch_kodex200_yf, 220)
            f_sectors = ex.submit(_fetch_sector_changes)
            f_kospi   = ex.submit(_fetch_index_yf, '^KS11')
            f_kosdaq  = ex.submit(_fetch_index_yf, '^KQ11')

        rows    = f_kodex.result()
        sectors = f_sectors.result()
        kospi   = f_kospi.result()
        kosdaq  = f_kosdaq.result()

        if rows:
            closes        = [r["close"] for r in rows]
            current_price = closes[-1]
            ma20  = _calc_ma(closes, 20)
            ma50  = _calc_ma(closes, 50)
            ma200 = _calc_ma(closes, 200)

            if ma200 is None or ma50 is None or ma20 is None:
                regime = "UNKNOWN"
            elif current_price > ma200 and ma20 > ma50:
                regime = "RISK_ON"
            elif current_price < ma200 and ma20 < ma50:
                regime = "RISK_OFF"
            else:
                regime = "NEUTRAL"

            kodex200 = {"code": "069500", "price": current_price,
                        "ma20": ma20, "ma50": ma50, "ma200": ma200}
            date         = rows[-1]["date"]
            regime_detail = {
                "price_above_ma200": current_price > ma200 if ma200 else None,
                "ma20_above_ma50":   ma20 > ma50 if (ma20 and ma50) else None,
            }
        else:
            kodex200      = None
            date          = None
            regime        = "UNKNOWN"
            regime_detail = {"price_above_ma200": None, "ma20_above_ma50": None}

        return jsonify({
            "date": date,
            "kodex200": kodex200,
            "regime": regime,
            "regime_detail": regime_detail,
            "sectors": sectors,
            "kospi": kospi,
            "kosdaq": kosdaq,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── realtime price helpers ───────────────────────────────────────

def _yfinance_suffix(code: str) -> str:
    """한국 종목코드를 yfinance 티커로 변환 (e.g. 005930 → 005930.KS)."""
    _ensure_market_map()
    suffix = _TICKER_MARKET_MAP.get(code.upper(), '.KS')
    return f"{code}{suffix}"


def _fetch_yfinance_fallback(tickers: list[str]) -> dict[str, dict]:
    """캐시 미스 ticker들을 yfinance로 조회하여 PriceCache에 저장 후 반환."""
    if not tickers:
        return {}

    yf_symbols = [_yfinance_suffix(t) for t in tickers]
    result = {}

    try:
        data = yf.download(
            yf_symbols,
            period="1d",
            group_by="ticker",
            progress=False,
            threads=True,
        )

        for ticker, yf_sym in zip(tickers, yf_symbols):
            try:
                # group_by="ticker" 인 경우 columns는 (Ticker, Attribute) MultiIndex
                column_tickers = []
                if isinstance(data.columns, pd.MultiIndex):
                    column_tickers = data.columns.levels[0].tolist()
                else:
                    column_tickers = [yf_symbols[0]] if len(yf_symbols) == 1 else []

                if yf_sym not in column_tickers:
                    continue
                
                row = data[yf_sym] if isinstance(data.columns, pd.MultiIndex) else data
                if row.empty:
                    continue

                last = row.iloc[-1]
                # Series에서 'Close' 등이 있는지 확인
                if 'Close' not in last or pd.isna(last['Close']):
                    continue

                close = float(last["Close"])
                prev_close = float(last["Open"]) if ("Open" in last and not pd.isna(last["Open"])) else close
                change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0.0
                volume = int(last["Volume"]) if ("Volume" in last and not pd.isna(last["Volume"])) else 0

                result[ticker.upper()] = {
                    "price": int(close),
                    "change_pct": change_pct,
                    "volume": volume,
                }
            except Exception:
                continue
    except Exception:
        pass

    if result:
        cache = PriceCache.get_instance()
        cache.bulk_update(result)

    return result


# ── realtime price endpoints ─────────────────────────────────────

@kr_bp.route('/realtime-prices', methods=['POST'])
def realtime_prices():
    body = request.get_json(silent=True) or {}
    tickers = body.get("tickers", [])

    if not tickers or not isinstance(tickers, list):
        return jsonify({"error": "tickers list is required"}), 400

    cache = PriceCache.get_instance()
    cache.register_tickers(tickers)
    cached = cache.get_prices(tickers)

    missing = [t for t in tickers if t.upper() not in cached]

    if missing:
        fallback = _fetch_yfinance_fallback(missing)
        cached.update(fallback)

    return jsonify({
        "prices": cached,
        "version": cache.get_version(),
    })


@kr_bp.route('/price-stream')
def price_stream():
    tickers_param = request.args.get("tickers", "")
    tickers = [t.strip() for t in tickers_param.split(",") if t.strip()] or []
    
    if tickers:
        PriceCache.get_instance().register_tickers(tickers)

    def generate():
        cache = PriceCache.get_instance()
        last_version = -1

        while True:
            current_version = cache.get_version()

            if current_version != last_version:
                prices = cache.get_prices(tickers)
                payload = json.dumps({
                    "prices": prices,
                    "version": current_version,
                })
                yield f"data: {payload}\n\n"
                last_version = current_version

            time.sleep(5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Stock summary (chart history) ────────────────────────────────

DAILY_PRICES_PATH = os.path.join(DATA_DIR, 'daily_prices.csv')


def _build_stock_universe() -> list[dict]:
    """모든 전략 파일에서 종목 목록 수집 → [{ticker, name, market}]."""
    seen: set[str] = set()
    universe: list[dict] = []

    def _add(code, name, market):
        code = (code or '').upper()
        if not code or code in seen:
            return
        seen.add(code)
        universe.append({'ticker': code, 'name': name or '', 'market': market or ''})

    # 1) jongga 시그널
    for s in _load_all_jongga_signals():
        _add(s.get('stock_code'), s.get('stock_name'), s.get('market'))

    # 2) VCP 시그널 (vcp_signals.json 및 과거 파일)
    vcp_files = [os.path.join(DATA_DIR, 'vcp_signals.json')] + \
                glob.glob(os.path.join(DATA_DIR, 'vcp_signals_*.json'))
    for vf in vcp_files:
        if os.path.exists(vf):
            try:
                with open(vf, 'r', encoding='utf-8') as f:
                    vc = json.load(f)
                sigs = vc.get('signals', []) if isinstance(vc, dict) else vc
                for s in (sigs or []):
                    _add(s.get('code') or s.get('stock_code'), s.get('name') or s.get('stock_name'), s.get('market'))
            except Exception:
                pass

    # 3) 기타 전략 파일들
    for fname in ['flow_momentum_latest.json', 'narrative_momentum_latest.json',
                  'sector_rotation_latest.json', 'contrarian_latest.json']:
        fpath = os.path.join(DATA_DIR, fname)
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = json.load(f)
            for s in content.get('signals', []):
                _add(s.get('ticker') or s.get('stock_code'), s.get('name') or s.get('stock_name'), s.get('market'))
        except Exception:
            pass

    return universe


@kr_bp.route('/stock-search')
def stock_search():
    try:
        q = (request.args.get('q') or '').strip()
        if len(q) < 1:
            return jsonify([])

        results = []

        # 1) Naver 자동완성 API (전체 상장 종목 대상)
        try:
            naver_url = f'https://ac.stock.naver.com/ac?q={requests.utils.quote(q)}&target=stock'
            resp = requests.get(naver_url, headers=_NAVER_HEADERS, timeout=5)
            if resp.ok:
                data = resp.json()
                seen: set[str] = set()
                for entry in data.get('items', []):
                    if not isinstance(entry, dict):
                        continue
                    code   = entry.get('code', '')
                    name   = entry.get('name', '')
                    market = entry.get('typeCode', 'KOSPI')  # 'KOSPI' or 'KOSDAQ'
                    if code and code not in seen:
                        seen.add(code)
                        results.append({'ticker': code, 'name': name, 'market': market})
        except Exception:
            pass

        # 2) 결과 없으면 로컬 유니버스 폴백
        if not results:
            ql = q.lower()
            universe = _build_stock_universe()
            results = [s for s in universe if ql in s['name'].lower() or ql in s['ticker'].lower()]

        return jsonify(results[:20])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/stock-summary/<ticker>')
@_cached_response(ttl_seconds=300)
def stock_summary(ticker: str):
    try:
        ticker_upper = ticker.upper()

        # ── 1) jongga 시그널에서 종목 메타 조회 ──────────────────
        sig_meta: dict = {}
        for s in _load_all_jongga_signals():
            if (s.get('stock_code') or '').upper() == ticker_upper:
                sig_meta = s
                break

        # ── 2) price_history 수집 ────────────────────────────────
        rows: list[dict] = []
        if os.path.exists(DAILY_PRICES_PATH):
            with open(DAILY_PRICES_PATH, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    if row.get('stock_code', '').upper() == ticker_upper:
                        entry = {'date': row['date'], 'close': int(row['close'])}
                        if 'open'   in row: entry['open']   = int(row['open'])
                        if 'high'   in row: entry['high']   = int(row['high'])
                        if 'low'    in row: entry['low']    = int(row['low'])
                        if 'volume' in row: entry['volume'] = int(row['volume'])
                        rows.append(entry)
            rows.sort(key=lambda r: r['date'])

        # 항상 yfinance 1년치 데이터를 시도하여 더 풍부한 데이터를 확보
        base_ticker = re.sub(r'\.(KS|KQ)$', '', ticker, flags=re.IGNORECASE)
        for suffix in ('.KS', '.KQ'):
            try:
                hist = yf.Ticker(f"{base_ticker}{suffix}").history(period='1y')
                if not hist.empty:
                    yf_rows = [{'date': str(i.date()), 'open': round(float(r['Open'])),
                                'high': round(float(r['High'])), 'low': round(float(r['Low'])),
                                'close': round(float(r['Close'])), 'volume': int(r['Volume'])}
                               for i, r in hist.iterrows()]
                    yf_rows.sort(key=lambda r: r['date'])
                    # yfinance 데이터가 더 풍부하면 교체 (일관된 차트 제공)
                    if len(yf_rows) > len(rows):
                        rows = yf_rows
                    break
            except Exception:
                pass

        # ── 3) 현재가 · 등락률 계산 ──────────────────────────────
        current_price = 0
        change_pct    = 0.0
        volume        = 0
        if rows:
            last = rows[-1]
            current_price = last.get('close', 0)
            volume = last.get('volume', 0)
            if len(rows) >= 2:
                prev = rows[-2].get('close', 1) or 1
                change_pct = round((last['close'] - prev) / prev * 100, 2)
        
        # 로컬 데이터에 가격 정보가 전혀 없을 경우 시그널 메타데이터 활용
        if not current_price:
            current_price = sig_meta.get('current_price', 0)
        if not change_pct:
            change_pct    = sig_meta.get('change_pct', 0.0)

        # ── 4) factors (jongga score 분해) ───────────────────────
        score_raw = sig_meta.get('score', {})
        if isinstance(score_raw, dict):
            factors = {k: v for k, v in score_raw.items() if k != 'llm_reason'}
        else:
            factors = {'total': score_raw if isinstance(score_raw, (int, float)) else 0}
        # 0~3 점수를 0~100 척도로 변환 (max per factor varies)
        _max_map = {'news': 3, 'volume': 3, 'chart': 3, 'candle': 1,
                    'consolidation': 1, 'supply': 2, 'retracement': 1, 'pullback_support': 1, 'total': 15}
        factors_pct = {k: round(v / _max_map.get(k, 3) * 100) for k, v in factors.items() if isinstance(v, (int, float))}

        # ── 5) Naver 실시간 지표 (시총·PER·PBR·거래량·등락률) ────
        market_cap  = 0
        per = 'N/A'  # float or 'N/A'
        pbr: float       = 0.0
        try:
            nav_url  = f'https://m.stock.naver.com/api/stock/{ticker_upper}/integration'
            nav_resp = requests.get(nav_url, headers=_NAVER_HEADERS, timeout=5)
            if nav_resp.status_code == 200:
                nav_data   = nav_resp.json()
                total_info = {item['code']: item.get('value', '')
                              for item in nav_data.get('totalInfos', [])}

                # 시가총액 "3,260억" → int 원
                raw_cap = str(total_info.get('marketValue', '') or '')
                raw_cap = raw_cap.replace(',', '').strip()
                if raw_cap:
                    _cap = 0
                    if '조' in raw_cap:
                        parts = raw_cap.split('조')
                        _cap += int(parts[0].strip()) * 1_000_000_000_000
                        raw_cap = parts[1].strip()
                    if '억' in raw_cap:
                        n = raw_cap.replace('억', '').strip()
                        _cap += int(float(n)) * 100_000_000 if n else 0
                    market_cap = _cap

                # PER "17.58배" → float
                raw_per = str(total_info.get('per', '') or '').replace('배', '').replace(',', '').strip()
                if raw_per and raw_per not in ('N/A', '-', ''):
                    try:
                        per = round(float(raw_per), 2)
                    except ValueError:
                        per = 'N/A'

                # PBR "1.39배" → float
                raw_pbr = str(total_info.get('pbr', '') or '').replace('배', '').replace(',', '').strip()
                if raw_pbr and raw_pbr not in ('N/A', '-', ''):
                    try:
                        pbr = round(float(raw_pbr), 2)
                    except ValueError:
                        pbr = 0.0

                # 거래량 "595,703" → int (로컬 데이터가 없을 때)
                if not volume:
                    raw_vol = str(total_info.get('accumulatedTradingVolume', '') or '').replace(',', '').strip()
                    if raw_vol.isdigit():
                        volume = int(raw_vol)

                # 등락률 "6.41" → float (로컬 데이터가 없을 때)
                if not change_pct:
                    raw_chg = str(total_info.get('fluctuationsRatio', '') or '').replace('%', '').replace('+', '').strip()
                    if raw_chg and raw_chg not in ('-', ''):
                        try:
                            change_pct = round(float(raw_chg), 2)
                        except ValueError:
                            pass

                # 현재가 (로컬 데이터가 없을 때)
                if not current_price:
                    raw_cp = str(total_info.get('closePrice', '') or '').replace(',', '').strip()
                    if raw_cp.isdigit():
                        current_price = int(raw_cp)

                # 종목명 보완 (jongga에 없는 종목)
                if not sig_meta:
                    stock_name = nav_data.get('stockName', '') or nav_data.get('name', '') or ticker_upper
                    nav_market = nav_data.get('marketType', '') or ''
                    sig_meta['stock_name'] = stock_name
                    sig_meta['market']     = 'KOSPI' if 'KOSPI' in nav_market.upper() else 'KOSDAQ' if 'KOSDAQ' in nav_market.upper() else ''
        except Exception:
            pass

        # ── 6) signal 상태 ───────────────────────────────────────
        vcp_file = os.path.join(DATA_DIR, 'vcp_signals.json')
        vcp_tickers: set[str] = set()
        if os.path.exists(vcp_file):
            for sv in json.load(open(vcp_file, encoding='utf-8')).get('signals', []):
                vcp_tickers.add((sv.get('stock_code') or sv.get('ticker', '')).upper())

        return jsonify({
            'ticker':        ticker_upper,
            'name':          sig_meta.get('stock_name', ticker_upper),
            'market':        sig_meta.get('market', ''),
            'current_price': current_price,
            'change_pct':    change_pct,
            'volume':        volume,
            'market_cap':    market_cap,
            'per':           per,
            'pbr':           pbr,
            'factors':       factors_pct,
            'signals': {
                'vcp':         ticker_upper in vcp_tickers,
                'closing_bet': bool(sig_meta),
            },
            'price_history': rows,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/stock-ai-summary/<ticker>')
@_cached_response(ttl_seconds=600)
def stock_ai_summary(ticker: str):
    try:
        ticker_upper = ticker.upper()

        # jongga 시그널에서 최신 데이터 조회
        sig: dict = {}
        for s in _load_all_jongga_signals():
            if (s.get('stock_code') or '').upper() == ticker_upper:
                sig = s
                break

        name   = sig.get('stock_name', ticker_upper)
        grade  = sig.get('grade', '--')
        themes = sig.get('themes') or []
        news   = sig.get('news_items') or []
        score  = sig.get('score', {})
        total  = score.get('total', 0) if isinstance(score, dict) else 0

        # GeminiAnalyzer 시도
        try:
            import sys, os as _os
            engine_dir = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..', '..', 'kr_market', 'engine'))
            if engine_dir not in sys.path:
                sys.path.insert(0, engine_dir)
            from llm_analyzer import GeminiAnalyzer  # type: ignore

            analyzer = GeminiAnalyzer()
            if analyzer.client and news:
                import asyncio
                result = asyncio.run(analyzer.analyze_news(name, news[:3]))
                llm_score = result.get('score', 0)
                llm_reason = result.get('reason', '')
                llm_themes = result.get('themes', themes)
            else:
                raise ValueError('no client or no news')
        except Exception:
            llm_score  = 0
            llm_reason = ''
            llm_themes = themes

        # 팩터 품질 기반 요약 생성
        score_map = score if isinstance(score, dict) else {}
        strength  = '우수' if total >= 10 else '양호' if total >= 7 else '보통'
        sup_score = score_map.get('supply', 0)
        sup_txt   = '외국인/기관 수급이 긍정적' if sup_score >= 2 else '수급 중립'
        theme_txt = f"주요 테마는 {', '.join(llm_themes[:3])}" if llm_themes else '특정 테마 없음'

        summary = (
            f"{name}({ticker_upper})은 종합 점수 {total}점으로 {strength} 등급을 기록 중입니다. "
            f"{sup_txt}이며, {theme_txt}입니다."
        )
        if llm_reason:
            summary += f" {llm_reason}"

        outlook = f"등급 {grade} — 기술적 지표와 수급 흐름을 종합한 신뢰도 기반 분석입니다."

        risk_factors = []
        if score_map.get('supply', 0) < 1:
            risk_factors.append('수급 지표 약세 — 외국인/기관 순매도 구간')
        if score_map.get('chart', 0) < 2:
            risk_factors.append('차트 패턴 미완성 — 돌파 확인 필요')
        if not risk_factors:
            risk_factors.append('급격한 시장 변동 시 단기 조정 가능성')

        catalysts = []
        if llm_themes:
            catalysts.append(f"테마 모멘텀: {', '.join(llm_themes[:2])}")
        if score_map.get('news', 0) >= 2:
            catalysts.append('강한 뉴스 재료 보유')
        if score_map.get('volume', 0) >= 2:
            catalysts.append('거래대금 급증 — 기관/외국인 관심 집중')
        if not catalysts:
            catalysts.append('추가 재료 발굴 시 상승 모멘텀 확보 가능')

        return jsonify({
            'ticker':       ticker_upper,
            'summary':      summary,
            'outlook':      outlook,
            'risk_factors': risk_factors,
            'catalysts':    catalysts,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Jongga V2 cumulative performance ────────────────────────────


def _load_daily_prices():
    """daily_prices.csv → {stock_code: [{date, open, high, low, close}, ...]} 딕셔너리."""
    prices = {}
    if not os.path.exists(DAILY_PRICES_PATH):
        return prices
    with open(DAILY_PRICES_PATH, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            code = row['stock_code']
            entry = {'date': row['date'], 'close': int(row['close'])}
            # OHLC + volume 컬럼이 있으면 추가 (구버전 CSV 호환)
            if 'open' in row:
                entry['open']   = int(row['open'])
                entry['high']   = int(row['high'])
                entry['low']    = int(row['low'])
            if 'volume' in row:
                entry['volume'] = int(row['volume'])
            prices.setdefault(code, []).append(entry)
    for v in prices.values():
        v.sort(key=lambda r: r['date'])
    return prices


def _judge_outcome(signal, daily_rows):
    """시그널의 성과를 판정한다. (outcome, roi_pct, days_held)"""
    entry = signal.get('entry_price') or signal.get('current_price', 0)
    target = signal.get('target_price', entry * 1.09)
    stop = signal.get('stop_price', entry * 0.95)
    sig_date = signal.get('signal_date', '')

    if not entry or not daily_rows:
        return 'OPEN', 0.0, 0

    for i, row in enumerate(daily_rows):
        if row['date'] <= sig_date:
            continue
        close = row['close']
        if close >= target:
            roi = round((target - entry) / entry * 100, 2)
            return 'TARGET_HIT', roi, i + 1
        if close <= stop:
            roi = round((stop - entry) / entry * 100, 2)
            return 'STOP_HIT', roi, i + 1

    # 미결 — 마지막 종가 기준
    last_close = daily_rows[-1]['close']
    roi = round((last_close - entry) / entry * 100, 2)
    return 'OPEN', roi, len(daily_rows)


@kr_bp.route('/jongga-v2/cumulative')
@_cached_response(ttl_seconds=120)
def jongga_v2_cumulative():
    try:
        # 1. 전체 시그널 로드
        pattern = os.path.join(DATA_DIR, 'jongga_v2_results_*.json')
        files = sorted(glob.glob(pattern))
        all_signals = []
        for fp in files:
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
            all_signals.extend(data.get('signals', []))

        # 2. 일별 가격 로드
        daily_prices = _load_daily_prices()

        # 3. 각 시그널 판정
        results = []
        for s in all_signals:
            code = s.get('stock_code', '')
            daily_rows = daily_prices.get(code, [])
            outcome, roi_pct, days_held = _judge_outcome(s, daily_rows)
            results.append({
                'stock_code': code,
                'stock_name': s.get('stock_name', ''),
                'signal_date': s.get('signal_date', ''),
                'grade': s.get('grade', ''),
                'entry_price': s.get('entry_price', 0),
                'target_price': s.get('target_price', 0),
                'stop_price': s.get('stop_price', 0),
                'outcome': outcome,
                'roi_pct': roi_pct,
                'days_held': days_held,
            })

        # 4. 통계 계산
        closed = [r for r in results if r['outcome'] != 'OPEN']
        wins = [r for r in closed if r['outcome'] == 'TARGET_HIT']
        win_rate = round(len(wins) / len(closed) * 100, 2) if closed else 0.0
        avg_roi = round(sum(r['roi_pct'] for r in closed) / len(closed), 2) if closed else 0.0

        # 등급별 통계
        grade_map = {}
        for r in closed:
            grade_map.setdefault(r['grade'], []).append(r['roi_pct'])

        grade_roi = {}
        for grade, rois in sorted(grade_map.items()):
            w = [v for v in rois if v > 0]
            grade_roi[grade] = {
                'count': len(rois),
                'win_rate': round(len(w) / len(rois) * 100, 2),
                'avg_roi': round(sum(rois) / len(rois), 2),
            }

        # 5. 페이지네이션
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        total_count = len(results)
        start = (page - 1) * per_page
        paged = results[start:start + per_page]

        return jsonify({
            'stats': {
                'total': total_count,
                'wins': len(wins),
                'losses': len([r for r in closed if r['outcome'] == 'STOP_HIT']),
                'open': len([r for r in results if r['outcome'] == 'OPEN']),
                'win_rate': win_rate,
                'avg_roi': avg_roi,
                'grade_roi': grade_roi,
            },
            'signals': paged,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Strategy endpoints ───────────────────────────────────────────

def _load_latest_jongga_signals() -> list:
    import glob as _glob
    latest_fp = os.path.join(DATA_DIR, 'jongga_v2_latest.json')
    if os.path.exists(latest_fp):
        return json.load(open(latest_fp, encoding='utf-8')).get('signals', [])
    files = sorted(_glob.glob(os.path.join(DATA_DIR, 'jongga_v2_results_*.json')), reverse=True)
    if files:
        return json.load(open(files[0], encoding='utf-8')).get('signals', [])
    return []

def _load_all_jongga_signals() -> list:
    import glob as _glob
    results = []
    for fp2 in sorted(_glob.glob(os.path.join(DATA_DIR, 'jongga_v2_results_*.json')), reverse=True):
        d = json.load(open(fp2, encoding='utf-8'))
        for s in d.get('signals', []):
            results.append(s)
    return results


@kr_bp.route('/strategies/<strategy_name>')
@_cached_response(ttl_seconds=180)
def strategy(strategy_name: str):
    try:
        if strategy_name == 'flow-momentum':
            # ── 엔진 결과 파일 우선 사용 ────────────────────────────
            fm_path = os.path.join(DATA_DIR, 'flow_momentum_latest.json')
            if os.path.exists(fm_path):
                fm = json.load(open(fm_path, encoding='utf-8'))
                raw_signals = fm.get('signals', [])
                if raw_signals:
                    # flow_momentum.py FlowSignal 필드 → 프론트엔드 필드 정규화
                    signals = []
                    for s in raw_signals:
                        signals.append({
                            'ticker':           s.get('ticker', ''),
                            'name':             s.get('name', ''),
                            'market':           s.get('market', ''),
                            'score':            s.get('score', 0),
                            'foreign_flow':     s.get('foreign_flow', 0),
                            'institution_flow': s.get('institution_flow', 0),
                            'volume_ratio':     s.get('volume_ratio', 0),
                            'signal_strength':  s.get('signal_strength', 'weak'),
                            'signal_date':      s.get('signal_date', ''),
                        })
                    stats = fm.get('stats', {})
                    return jsonify({
                        'strategy':    'flow-momentum',
                        'description': '외국인/기관 수급 기반 모멘텀',
                        'signals':     signals,
                        'stats': {
                            'total':    stats.get('total', len(signals)),
                            'avg_score': stats.get('avg_score', 0),
                        },
                        'updated_at': fm.get('updated_at', ''),
                    })

            # ── fallback: jongga 시그널 기반 임시 계산 ──────────────
            sigs = _load_all_jongga_signals()
            seen = set()
            signals = []
            for s in sigs:
                code = s.get('stock_code', '')
                if code in seen:
                    continue
                seen.add(code)
                foreign_5d  = s.get('foreign_5d', 0) or 0
                inst_5d     = s.get('inst_5d', 0) or 0
                entry       = s.get('entry_price', 0) or 1
                trading_val = s.get('trading_value', 0) or 0
                score_obj   = s.get('score', {})
                total_score = score_obj.get('total', 0) if isinstance(score_obj, dict) else (score_obj or 0)
                foreign_flow  = round(foreign_5d * entry / 1e8, 1)
                inst_flow     = round(inst_5d * entry / 1e8, 1)
                volume_ratio  = round(min(trading_val / 10e9, 9.9), 2)
                pos_count = (1 if foreign_flow > 0 else 0) + (1 if inst_flow > 0 else 0)
                strength = (
                    'strong'   if pos_count == 2 and total_score >= 8 else
                    'moderate' if pos_count >= 1 else
                    'weak'
                )
                signals.append({
                    'ticker':           code,
                    'name':             s.get('stock_name', ''),
                    'market':           s.get('market', ''),
                    'score':            total_score,
                    'foreign_flow':     foreign_flow,
                    'institution_flow': inst_flow,
                    'volume_ratio':     volume_ratio,
                    'signal_strength':  strength,
                    'signal_date':      s.get('signal_date', ''),
                })
            signals.sort(key=lambda x: x['score'], reverse=True)
            avg_score = round(sum(x['score'] for x in signals) / len(signals), 1) if signals else 0
            return jsonify({
                'strategy':    'flow-momentum',
                'description': '외국인/기관 수급 기반 모멘텀 (fallback)',
                'signals':     signals,
                'stats': {'total': len(signals), 'avg_score': avg_score},
            })

        # ── JSON 파일 기반 전략 (엔진 결과를 직접 서빙) ────────────────
        _STRATEGY_FILES = {
            'narrative-momentum':  ('narrative_momentum_latest.json',  '뉴스/SNS 기반 테마 분석'),
            'sector-rotation':     ('sector_rotation_latest.json',     '업종 순환 기반 전략'),
            'contrarian-reversal': ('contrarian_latest.json',          '과매도 반전 시그널'),
        }

        if strategy_name == 'best':
            _ALL = {
                'flow-momentum':       'flow_momentum_latest.json',
                'narrative-momentum':  'narrative_momentum_latest.json',
                'sector-rotation':     'sector_rotation_latest.json',
                'contrarian-reversal': 'contrarian_latest.json',
            }
            merged = []
            for strat, fname in _ALL.items():
                fpath = os.path.join(DATA_DIR, fname)
                if not os.path.exists(fpath):
                    continue
                d = json.load(open(fpath, encoding='utf-8'))
                for s in d.get('signals', []):
                    entry = {k: v for k, v in s.items()}
                    if 'ticker' not in entry and 'stock_code' in entry:
                        entry['ticker'] = entry.pop('stock_code')
                    entry['source_strategy'] = strat
                    if strat == 'flow-momentum':
                        fgn = entry.get('foreign_flow', 0) or 0
                        ins = entry.get('institution_flow', 0) or 0
                        entry['key_metric_label'] = '수급'
                        entry['key_metric_value'] = f'외{fgn:+.0f}/기{ins:+.0f}억'
                    elif strat == 'narrative-momentum':
                        entry['key_metric_label'] = '테마'
                        entry['key_metric_value'] = entry.get('theme', '--')
                    elif strat == 'sector-rotation':
                        rs = entry.get('relative_strength', 0) or 0
                        entry['key_metric_label'] = 'RS'
                        entry['key_metric_value'] = f'{rs:.0f}'
                    elif strat == 'contrarian-reversal':
                        prob = entry.get('reversal_probability', 0) or 0
                        entry['key_metric_label'] = '반전확률'
                        entry['key_metric_value'] = f'{prob:.0%}'
                    merged.append(entry)
            merged.sort(key=lambda x: x.get('score', 0), reverse=True)
            merged = merged[:30]
            cnt = len(merged)
            avg_s = round(sum(x.get('score', 0) for x in merged) / cnt, 1) if merged else 0
            return jsonify({
                'strategy':    'best',
                'description': '전 전략 통합 최상위 랭킹',
                'signals':     merged,
                'stats':       {'total': cnt, 'avg_score': avg_s},
            })

        if strategy_name in _STRATEGY_FILES:
            fname, desc = _STRATEGY_FILES[strategy_name]
            fpath = os.path.join(DATA_DIR, fname)
            if os.path.exists(fpath):
                d = json.load(open(fpath, encoding='utf-8'))
                raw = d.get('signals', [])
                raw_stats = d.get('stats', {})

                # 공통 정규화 (프론트엔드 인터페이스 일치)
                signals = []
                for s in raw:
                    entry = {k: v for k, v in s.items()}
                    # ticker 필드 통일 (flow_momentum은 'ticker', 나머지도 동일)
                    if 'ticker' not in entry and 'stock_code' in entry:
                        entry['ticker'] = entry.pop('stock_code')
                    signals.append(entry)

                return jsonify({
                    'strategy':    strategy_name,
                    'description': desc,
                    'signals':     signals,
                    'stats': {
                        'total':     raw_stats.get('total', len(signals)),
                        'avg_score': raw_stats.get('avg_score', 0),
                    },
                    'updated_at': d.get('updated_at', ''),
                })
            # 파일 없으면 빈 응답
            return jsonify({
                'strategy':    strategy_name,
                'description': desc,
                'signals':     [],
                'stats':       {'total': 0, 'avg_score': 0},
                'message':     f'엔진을 먼저 실행하세요: python run_{strategy_name.replace("-", "_")}.py',
            })

        return jsonify({'strategy': strategy_name, 'description': '', 'signals': [], 'stats': {'total': 0, 'avg_score': 0}})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Position Sizer ────────────────────────────────────────────────

@kr_bp.route('/position-size', methods=['POST'])
def position_size():
    """포지션 사이징 계산 (Fixed Fractional / ATR / Kelly)."""
    try:
        body        = request.get_json(silent=True) or {}
        method      = body.get('method', 'fixed')
        capital     = float(body.get('capital', 0))
        entry_price = float(body.get('entry_price', 0))
        stop_price  = float(body.get('stop_price', 0))

        if capital <= 0 or entry_price <= 0:
            return jsonify({'error': '자본금과 진입가를 입력하세요.'}), 400

        risk_pct    = float(body.get('risk_pct', 1.0)) / 100
        risk_amount = capital * risk_pct

        if method == 'kelly':
            win_rate     = float(body.get('win_rate', 55.0)) / 100
            avg_win_pct  = float(body.get('avg_win_pct', 9.0)) / 100
            avg_loss_pct = float(body.get('avg_loss_pct', 5.0)) / 100
            if avg_loss_pct <= 0:
                return jsonify({'error': 'avg_loss_pct > 0 이어야 합니다.'}), 400
            b           = avg_win_pct / avg_loss_pct
            kelly_f     = max(0.0, min(win_rate - (1 - win_rate) / b, 0.25))
            half_kelly  = kelly_f / 2
            pos_value   = capital * half_kelly
            if stop_price <= 0:
                stop_price = entry_price * (1 - avg_loss_pct)
            target_price  = entry_price * (1 + avg_win_pct)
            kelly_detail  = {'b': round(b, 2), 'full_kelly_pct': round(kelly_f * 100, 1), 'half_kelly_pct': round(half_kelly * 100, 1)}
        elif method == 'atr':
            atr      = float(body.get('atr', 0))
            atr_mult = float(body.get('atr_multiplier', 2.0))
            if atr <= 0:
                return jsonify({'error': 'ATR 값을 입력하세요.'}), 400
            stop_dist    = atr * atr_mult
            stop_price   = entry_price - stop_dist
            target_price = entry_price + stop_dist * 2
            pos_value    = (risk_amount / stop_dist * entry_price) if stop_dist else 0
            kelly_detail = None
        else:  # fixed
            if stop_price <= 0:
                stop_price = entry_price * 0.95
            stop_dist    = entry_price - stop_price
            if stop_dist <= 0:
                return jsonify({'error': '손절가는 진입가보다 낮아야 합니다.'}), 400
            target_price = float(body.get('target_price', entry_price * 1.15))
            pos_value    = risk_amount / stop_dist * entry_price
            kelly_detail = None

        # 50% 상한 적용
        pos_value = min(pos_value, capital * 0.50)
        shares    = int(pos_value / entry_price) if entry_price else 0
        pos_value = shares * entry_price

        actual_risk    = shares * abs(entry_price - stop_price)
        pot_profit     = shares * abs(target_price - entry_price)
        stop_dist_pct  = abs(entry_price - stop_price) / entry_price * 100 if entry_price else 0
        rr_ratio       = round(pot_profit / actual_risk, 2) if actual_risk else 0

        result = {
            'method':             method,
            'shares':             shares,
            'entry_price':        round(entry_price),
            'stop_price':         round(stop_price),
            'target_price':       round(target_price),
            'position_value':     round(pos_value),
            'actual_risk':        round(actual_risk),
            'potential_profit':   round(pot_profit),
            'portfolio_risk_pct': round(actual_risk / capital * 100, 2) if capital else 0,
            'position_pct':       round(pos_value / capital * 100, 1) if capital else 0,
            'risk_reward_ratio':  rr_ratio,
            'stop_distance_pct':  round(stop_dist_pct, 2),
            'risk_warning':       (actual_risk / capital * 100 > 2.0) if capital else False,
        }
        if kelly_detail:
            result['kelly'] = kelly_detail
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Market Top Detector (KR) ──────────────────────────────────────

@kr_bp.route('/market-top')
@_cached_response(ttl_seconds=600)
def market_top():
    """KR 시장 고점 위험도 복합 점수 (0~100)."""
    try:
        daily_prices = _load_daily_prices()
        components   = {}

        # 1. Distribution Days (25pt) ──────────────────────────────
        try:
            hist = yf.Ticker('^KS11').history(period='2mo')
            dd_count = 0
            if len(hist) >= 2:
                closes  = list(hist['Close'])
                volumes = list(hist['Volume'])
                for i in range(1, len(closes)):
                    change = (closes[i] - closes[i-1]) / closes[i-1] if closes[i-1] else 0
                    if change < -0.002 and volumes[i] > volumes[i-1]:
                        dd_count += 1
            dd_count = min(dd_count, 6)
            dd_score = min(25, int(dd_count * 4.2))
            components['distribution_days'] = {
                'label': '배분일 (Distribution Days)', 'count': dd_count,
                'score': dd_score, 'weight': 25, 'detail': f'최근 2개월 배분일 {dd_count}개',
            }
        except Exception:
            components['distribution_days'] = {
                'label': '배분일', 'count': 0, 'score': 0, 'weight': 25, 'detail': '데이터 없음',
            }

        # 2. Leading Stock Deterioration (20pt) ───────────────────
        try:
            vcp_files  = sorted(glob.glob(os.path.join(DATA_DIR, 'vcp_signals_[0-9]*.json')), reverse=True)
            below, total = 0, 0
            for fp2 in vcp_files[:3]:
                raw = json.load(open(fp2, encoding='utf-8'))
                for sig in (raw if isinstance(raw, list) else raw.get('signals', [])):
                    code, pivot = sig.get('code', ''), sig.get('pivot_high', 0)
                    if not code or not pivot:
                        continue
                    rows = daily_prices.get(code, [])
                    if not rows:
                        continue
                    total += 1
                    if rows[-1]['close'] < pivot * 0.95:
                        below += 1
            below_pct = below / total if total else 0
            det_score = min(20, int(below_pct * 40))
            components['leading_deterioration'] = {
                'label': '선도주 약세', 'below_pct': round(below_pct * 100, 1),
                'total': total, 'score': det_score, 'weight': 20,
                'detail': f'VCP {total}종목 중 {below_pct*100:.0f}% 피벗 하회',
            }
        except Exception:
            components['leading_deterioration'] = {
                'label': '선도주 약세', 'below_pct': 0, 'score': 0, 'weight': 20, 'detail': '데이터 없음',
            }

        # 3. Defensive Sector Rotation (15pt) ─────────────────────
        try:
            sectors   = _fetch_sector_changes()
            DEFENSIVE = ['의약품', '음식료품', '통신업', '전기가스업', '보험']
            OFFENSIVE = ['전기전자', '반도체', '증권', '철강금속', '화학']
            def_avgs  = [s['change_pct'] for s in sectors if any(d in s['name'] for d in DEFENSIVE)]
            off_avgs  = [s['change_pct'] for s in sectors if any(d in s['name'] for d in OFFENSIVE)]
            def_avg   = sum(def_avgs) / len(def_avgs) if def_avgs else 0
            off_avg   = sum(off_avgs) / len(off_avgs) if off_avgs else 0
            spread    = def_avg - off_avg
            def_score = 15 if spread > 1.5 else (10 if spread > 0.5 else (5 if spread > 0 else 0))
            components['defensive_rotation'] = {
                'label': '방어섹터 로테이션', 'def_avg': round(def_avg, 2),
                'off_avg': round(off_avg, 2), 'spread': round(spread, 2),
                'score': def_score, 'weight': 15,
                'detail': f'방어 {def_avg:+.1f}% / 공격 {off_avg:+.1f}%',
            }
        except Exception:
            components['defensive_rotation'] = {
                'label': '방어섹터 로테이션', 'spread': 0, 'score': 0, 'weight': 15, 'detail': '데이터 없음',
            }

        # 4. Market Breadth — MA60 (15pt) ─────────────────────────
        try:
            below_ma60, total_t = 0, 0
            for code, rows in daily_prices.items():
                if len(rows) < 65:
                    continue
                closes = [r['close'] for r in rows[-65:]]
                ma60   = sum(closes[-60:]) / 60
                total_t += 1
                if closes[-1] < ma60:
                    below_ma60 += 1
            breadth_pct = below_ma60 / total_t if total_t else 0
            br_score = (15 if breadth_pct > 0.60 else 12 if breadth_pct > 0.50
                        else 8 if breadth_pct > 0.40 else 4 if breadth_pct > 0.30 else 0)
            components['market_breadth'] = {
                'label': '시장 폭 (MA60 하회)', 'below_pct': round(breadth_pct * 100, 1),
                'total': total_t, 'score': br_score, 'weight': 15,
                'detail': f'{total_t}종목 중 {breadth_pct*100:.0f}% MA60 하회',
            }
        except Exception:
            components['market_breadth'] = {
                'label': '시장 폭', 'below_pct': 0, 'score': 0, 'weight': 15, 'detail': '데이터 없음',
            }

        # 5. Index Technical — KODEX200 (15pt) ────────────────────
        try:
            rows = _fetch_kodex200_yf(220)
            if rows:
                closes      = [r['close'] for r in rows]
                price       = closes[-1]
                ma20        = sum(closes[-20:]) / 20  if len(closes) >= 20  else None
                ma50        = sum(closes[-50:]) / 50  if len(closes) >= 50  else None
                ma200       = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
                below_cnt   = sum([1 if (ma20  and price < ma20)  else 0,
                                   1 if (ma50  and price < ma50)  else 0,
                                   1 if (ma200 and price < ma200) else 0])
                it_score    = below_cnt * 5
                detail      = f'현재가 {price:,.0f} | MA20 {round(ma20) if ma20 else "--"} MA50 {round(ma50) if ma50 else "--"} MA200 {round(ma200) if ma200 else "--"} | {below_cnt}개 하회'
            else:
                it_score, detail = 0, 'KODEX200 데이터 없음'
            components['index_technical'] = {
                'label': '지수 기술 조건', 'score': it_score, 'weight': 15, 'detail': detail,
            }
        except Exception:
            components['index_technical'] = {
                'label': '지수 기술 조건', 'score': 0, 'weight': 15, 'detail': '데이터 없음',
            }

        # 6. Sentiment Proxy — 역발상 시그널 수 (10pt) ────────────
        try:
            ct_path  = os.path.join(DATA_DIR, 'contrarian_latest.json')
            ct_count = len(json.load(open(ct_path, encoding='utf-8')).get('signals', [])) if os.path.exists(ct_path) else 0
            sent_score = 10 if ct_count >= 20 else (7 if ct_count >= 10 else (4 if ct_count >= 5 else 0))
            components['sentiment'] = {
                'label': '시장 센티먼트', 'contrarian_count': ct_count,
                'score': sent_score, 'weight': 10, 'detail': f'역발상 시그널 {ct_count}개',
            }
        except Exception:
            components['sentiment'] = {
                'label': '시장 센티먼트', 'contrarian_count': 0, 'score': 0, 'weight': 10, 'detail': '데이터 없음',
            }

        total = sum(c.get('score', 0) for c in components.values())
        risk_level, risk_label = (
            ('green',    '정상 (매수 우호)')   if total <= 20 else
            ('yellow',   '조기 경고')          if total <= 40 else
            ('orange',   '위험 상승')          if total <= 60 else
            ('red',      '고점 가능성 높음')   if total <= 80 else
            ('critical', '고점 형성 중')
        )
        return jsonify({
            'score': total, 'risk_level': risk_level, 'risk_label': risk_label,
            'components': components, 'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Signal Postmortem ─────────────────────────────────────────────

def _fwd_return(rows: list, sig_date: str, n: int):
    """sig_date 이후 n 영업일 수익률 (없으면 None)."""
    idx = next((i for i, r in enumerate(rows) if r['date'] >= sig_date), None)
    if idx is None or idx + n >= len(rows):
        return None
    base = rows[idx]['close']
    return round((rows[idx + n]['close'] - base) / base * 100, 2) if base else None


def _pm_analyze(pattern: str, ticker_field: str, daily_prices: dict):
    """단일 전략 파일 패턴 → 포스트모템 집계."""
    results = []
    for fp2 in sorted(glob.glob(os.path.join(DATA_DIR, pattern))):
        raw      = json.load(open(fp2, encoding='utf-8'))
        file_date = raw.get('date', '') if isinstance(raw, dict) else ''
        signals  = raw.get('signals', []) if isinstance(raw, dict) else raw
        for sig in signals:
            ticker   = sig.get(ticker_field) or sig.get('code') or sig.get('stock_code', '')
            sig_date = (sig.get('signal_date') or file_date or '').replace('/', '-')
            if not ticker or not sig_date:
                continue
            rows = daily_prices.get(ticker, [])
            results.append({
                'ticker':     ticker,
                'name':       sig.get('name') or sig.get('stock_name', ''),
                'signal_date': sig_date,
                'score':      sig.get('score', 0),
                'return_5d':  _fwd_return(rows, sig_date, 5),
                'return_20d': _fwd_return(rows, sig_date, 20),
            })

    c5  = [r for r in results if r['return_5d']  is not None]
    c20 = [r for r in results if r['return_20d'] is not None]
    return {
        'total':          len(results),
        'evaluated_5d':   len(c5),
        'evaluated_20d':  len(c20),
        'win_rate_5d':    round(len([r for r in c5  if r['return_5d']  > 0]) / len(c5)  * 100, 1) if c5  else 0.0,
        'win_rate_20d':   round(len([r for r in c20 if r['return_20d'] > 0]) / len(c20) * 100, 1) if c20 else 0.0,
        'avg_return_5d':  round(sum(r['return_5d']  for r in c5)  / len(c5),  2) if c5  else 0.0,
        'avg_return_20d': round(sum(r['return_20d'] for r in c20) / len(c20), 2) if c20 else 0.0,
        'recent':         sorted(results, key=lambda x: x['signal_date'], reverse=True)[:5],
    }


@kr_bp.route('/postmortem')
@_cached_response(ttl_seconds=300)
def postmortem():
    """전략별 시그널 사후 성과 분석."""
    try:
        daily_prices = _load_daily_prices()
        STRATEGIES   = [
            ('vcp',             'vcp_signals_[0-9]*.json',        'code'),
            ('closing_bet',     'jongga_v2_results_[0-9]*.json',  'stock_code'),
            ('flow_momentum',   'flow_momentum_[0-9]*.json',      'ticker'),
            ('narrative',       'narrative_momentum_[0-9]*.json', 'ticker'),
            ('sector_rotation', 'sector_rotation_[0-9]*.json',    'ticker'),
            ('contrarian',      'contrarian_[0-9]*.json',         'ticker'),
        ]
        return jsonify({
            'strategies': {k: _pm_analyze(p, tf, daily_prices) for k, p, tf in STRATEGIES},
            'updated_at':  datetime.now().strftime('%Y-%m-%d %H:%M'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── PEAD / Gap Screener ───────────────────────────────────────────

def _avg_volume(rows, before_idx, window=20):
    start = max(0, before_idx - window)
    vols  = [r['volume'] for r in rows[start:before_idx] if r.get('volume', 0) > 0]
    return sum(vols) / len(vols) if vols else 0


def _closes_ma(closes, window):
    return sum(closes[-window:]) / window if len(closes) >= window else None


def _gap_ma_score(closes):
    """현재가 기준 MA 위치 점수 (0~2)."""
    price = closes[-1]
    score = 0
    ma20  = _closes_ma(closes, 20)
    ma60  = _closes_ma(closes, 60)
    if ma20  and price > ma20:  score += 1
    if ma60  and price > ma60:  score += 1
    return score


def _gap_trend_score(closes_before):
    """갭 이전 추세 점수 (0~2)."""
    n = len(closes_before)
    if n < 10:
        return 0
    half = n // 2
    a1   = sum(closes_before[:half]) / half
    a2   = sum(closes_before[half:]) / (n - half)
    return 2 if a2 > a1 * 1.05 else (1 if a2 > a1 else 0)


@kr_bp.route('/pead')
@_cached_response(ttl_seconds=300)
def pead_screener():
    """갭 상승 후 드리프트 스크리닝 (PEAD proxy, daily_prices.csv 기반)."""
    try:
        min_gap    = float(request.args.get('min_gap', 3.0))
        min_vol    = float(request.args.get('min_vol', 1.5))
        lookback   = int(request.args.get('lookback', 60))

        daily_prices = _load_daily_prices()
        universe     = {u['ticker']: u for u in _build_stock_universe()}

        best: dict = {}

        for code, rows in daily_prices.items():
            if len(rows) < 22:
                continue
            start_i = max(1, len(rows) - lookback)

            for i in range(start_i, len(rows)):
                prev_close = rows[i-1]['close']
                if not prev_close:
                    continue
                open_p  = rows[i].get('open') or rows[i]['close']
                gap_pct = (open_p - prev_close) / prev_close * 100
                if gap_pct < min_gap:
                    continue
                avg_vol   = _avg_volume(rows, i, 20)
                vol_ratio = rows[i].get('volume', 0) / avg_vol if avg_vol else 0
                if vol_ratio < min_vol:
                    continue

                closes_all    = [r['close'] for r in rows[:i+1]]
                closes_before = [r['close'] for r in rows[max(0,i-20):i]]

                # 5요소 점수
                f_gap   = 2.0 if gap_pct >= 10 else (1.5 if gap_pct >= 6 else 1.0)
                f_vol   = 2.0 if vol_ratio >= 4 else (1.5 if vol_ratio >= 3 else (1.0 if vol_ratio >= 2 else 0.5))
                f_ma    = float(_gap_ma_score(closes_all))
                f_trend = float(_gap_trend_score(closes_before))

                post = rows[i+1:] if i + 1 < len(rows) else []
                if post:
                    drift   = (post[-1]['close'] - rows[i]['close']) / rows[i]['close'] * 100
                    f_drift = 2.0 if drift >= 5 else (1.0 if drift >= 0 else 0.0)
                else:
                    drift, f_drift = 0.0, 1.0   # 당일 갭, 중립

                score = round(f_gap + f_vol + f_ma + f_trend + f_drift, 1)

                entry = {
                    'ticker':     code,
                    'name':       universe.get(code, {}).get('name', code),
                    'market':     universe.get(code, {}).get('market', ''),
                    'gap_date':   rows[i]['date'],
                    'gap_pct':    round(gap_pct, 1),
                    'vol_ratio':  round(vol_ratio, 1),
                    'post_drift': round(drift, 1) if post else None,
                    'score':      min(score, 10.0),
                    'factors':    {'gap': f_gap, 'volume': f_vol, 'ma': f_ma, 'trend': f_trend, 'drift': f_drift},
                }
                # 종목당 최고 점수 이벤트만 유지
                if code not in best or score > best[code]['score']:
                    best[code] = entry

        signals = sorted(best.values(), key=lambda x: x['score'], reverse=True)[:50]
        return jsonify({
            'signals': signals,
            'total':   len(signals),
            'params':  {'min_gap_pct': min_gap, 'min_vol_ratio': min_vol, 'lookback_days': lookback},
            'universe_size': len(daily_prices),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Market Breadth ────────────────────────────────────────────────

def _fetch_naver_ad():
    """Naver 증권 KOSPI/KOSDAQ 등락 종목 수 수집."""
    result = {}
    for market, sosok in [('KOSPI', '0'), ('KOSDAQ', '1')]:
        try:
            url  = f'https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}'
            resp = requests.get(url, headers=_NAVER_HEADERS, timeout=5)
            resp.encoding = 'euc-kr'
            soup = BeautifulSoup(resp.text, 'html.parser')
            tbl  = soup.find('table', class_='type_2')
            if not tbl:
                continue
            # 상단 요약 행 파싱
            summary = soup.find('table', class_='summary_info')
            if not summary:
                continue
            tds = summary.find_all('td')
            vals = [td.get_text(strip=True).replace(',', '') for td in tds]
            # 구조: 거래량, 거래대금, 상승, 보합, 하락, 상한, 하한
            if len(vals) >= 7:
                result[market] = {
                    'advances':    int(vals[2]) if vals[2].isdigit() else 0,
                    'unchanged':   int(vals[3]) if vals[3].isdigit() else 0,
                    'declines':    int(vals[4]) if vals[4].isdigit() else 0,
                    'upper_limit': int(vals[5]) if vals[5].isdigit() else 0,
                    'lower_limit': int(vals[6]) if vals[6].isdigit() else 0,
                }
        except Exception:
            pass
    return result


@kr_bp.route('/breadth')
@_cached_response(ttl_seconds=600)
def market_breadth():
    """시장 폭 분석 (MA 위치, 등락, 52주 고저, Naver A/D)."""
    try:
        daily_prices = _load_daily_prices()
        MA_WINDOWS   = [20, 60, 120, 200]
        above        = {w: 0 for w in MA_WINDOWS}
        advances, declines, unchanged_cnt = 0, 0, 0
        new_high_52w, new_low_52w = 0, 0
        total_t = 0

        for code, rows in daily_prices.items():
            if len(rows) < 5:
                continue
            total_t += 1
            closes = [r['close'] for r in rows]
            price  = closes[-1]

            for w in MA_WINDOWS:
                ma = _closes_ma(closes, w)
                if ma and price > ma:
                    above[w] += 1

            if len(closes) >= 2:
                if   closes[-1] > closes[-2]: advances  += 1
                elif closes[-1] < closes[-2]: declines  += 1
                else:                         unchanged_cnt += 1

            yr = rows[-252:] if len(rows) >= 252 else rows
            if price >= max(r['close'] for r in yr): new_high_52w += 1
            if price <= min(r['close'] for r in yr): new_low_52w  += 1

        def pct(n): return round(n / total_t * 100, 1) if total_t else 0.0

        naver_ad = _fetch_naver_ad()

        return jsonify({
            'universe': {
                'total':    total_t,
                'source':   'daily_prices.csv (tracked universe)',
            },
            'ma_breadth': {
                str(w): {'count': above[w], 'pct': pct(above[w]), 'below': total_t - above[w]}
                for w in MA_WINDOWS
            },
            'advance_decline': {
                'tracked': {
                    'advances':  advances, 'declines': declines,
                    'unchanged': unchanged_cnt,
                    'ratio':     round(advances / declines, 2) if declines else None,
                },
                'naver': naver_ad,
            },
            'new_highs_lows': {
                'new_high_52w': new_high_52w,
                'new_low_52w':  new_low_52w,
                'ratio':        round(new_high_52w / new_low_52w, 2) if new_low_52w else None,
            },
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── FTD Detector ──────────────────────────────────────────────────

@kr_bp.route('/ftd')
@_cached_response(ttl_seconds=600)
def ftd_detector():
    """Follow-Through Day 탐지 (KOSPI 기준)."""
    try:
        hist = yf.Ticker('^KS11').history(period='3mo')
        if hist.empty:
            return jsonify({'error': 'KOSPI 데이터 없음'}), 503

        rows = [
            {'date': str(idx.date()), 'close': round(float(row['Close']), 2),
             'open': round(float(row['Open']), 2), 'volume': int(row['Volume'])}
            for idx, row in hist.iterrows()
        ]
        if len(rows) < 15:
            return jsonify({'error': '데이터 부족'}), 503

        closes  = [r['close'] for r in rows]
        volumes = [r['volume'] for r in rows]
        n       = len(rows)

        current         = closes[-1]
        high_60         = max(closes[-min(60, n):])
        low_20          = min(closes[-min(20, n):])
        decline_pct     = round((current - high_60) / high_60 * 100, 1)
        ma20            = round(sum(closes[-20:]) / 20, 2) if n >= 20 else None
        ma50            = round(sum(closes[-50:]) / 50, 2) if n >= 50 else None

        # 시장 상태
        if decline_pct > -5 and (ma50 is None or current > ma50):
            market_state = 'UPTREND'
        elif decline_pct < -8:
            market_state = 'CORRECTION'
        else:
            market_state = 'NEUTRAL'

        # 최근 저점 탐색 (최근 30일 내)
        search_start  = max(0, n - 30)
        low_idx       = search_start + closes[search_start:].index(min(closes[search_start:]))

        rally_attempt = None
        ftd_signals   = []
        ftd_failed    = False

        # Rally attempt: 저점 이후 첫 상승일
        for i in range(low_idx + 1, n):
            chg = (closes[i] - closes[i-1]) / closes[i-1] * 100 if closes[i-1] else 0
            if chg > 0.3:
                rally_attempt = {
                    'date':     rows[i]['date'],
                    'change':   round(chg, 2),
                    'close':    closes[i],
                    'days_ago': n - 1 - i,
                }
                # 저점 하향 돌파 → Rally 무효
                for j in range(i + 1, n):
                    if closes[j] < closes[low_idx]:
                        ftd_failed = True
                        break
                # FTD 탐색: Rally day + 4일 이후, +1.5% 이상 & 거래량 증가
                if not ftd_failed:
                    for j in range(i + 4, min(i + 15, n)):
                        chg_j = (closes[j] - closes[j-1]) / closes[j-1] * 100 if closes[j-1] else 0
                        if chg_j >= 1.5 and volumes[j] > volumes[j-1]:
                            ftd_signals.append({
                                'date':         rows[j]['date'],
                                'change':       round(chg_j, 2),
                                'close':        closes[j],
                                'volume_ratio': round(volumes[j] / volumes[j-1], 2),
                                'day_count':    j - i,
                            })
                break  # 첫 번째 Rally attempt만 사용

        # FTD 최종 상태
        if ftd_signals and not ftd_failed:
            ftd_status = 'CONFIRMED'
        elif ftd_failed:
            ftd_status = 'FAILED'
        elif rally_attempt and not ftd_signals:
            ftd_status = 'WATCHING' if rally_attempt.get('days_ago', 99) <= 12 else 'NO_SIGNAL'
        else:
            ftd_status = 'NO_SIGNAL'

        # 히스토리: 최근 40일 (차트용)
        history = []
        for i, r in enumerate(rows[-40:], start=max(0, n-40)):
            chg = round((closes[i] - closes[i-1]) / closes[i-1] * 100, 2) if i > 0 and closes[i-1] else 0
            history.append({
                'date':   r['date'], 'close': r['close'],
                'change': chg,
                'is_rally': rally_attempt and r['date'] == rally_attempt['date'],
                'is_ftd':   any(f['date'] == r['date'] for f in ftd_signals),
            })

        return jsonify({
            'market_state':      market_state,
            'ftd_status':        ftd_status,
            'current_close':     current,
            'decline_from_peak': decline_pct,
            'high_60d':          round(high_60, 2),
            'low_20d':           round(low_20, 2),
            'ma20':              ma20,
            'ma50':              ma50,
            'rally_attempt':     rally_attempt,
            'ftd_signals':       ftd_signals,
            'ftd_failed':        ftd_failed,
            'history':           history,
            'updated_at':        datetime.now().strftime('%Y-%m-%d %H:%M'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Backtest Expert ───────────────────────────────────────────────

def _consecutive_losses(outcomes: list) -> int:
    """최대 연속 손실 횟수."""
    max_cl, cur = 0, 0
    for o in outcomes:
        if o <= 0:
            cur += 1
            max_cl = max(max_cl, cur)
        else:
            cur = 0
    return max_cl


def _max_drawdown(equity: list) -> float:
    """최대 낙폭 % 계산."""
    peak, mdd = equity[0] if equity else 1.0, 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak else 0
        mdd = max(mdd, dd)
    return round(mdd, 2)


def _profit_factor(returns: list) -> float | None:
    wins   = sum(r for r in returns if r > 0)
    losses = abs(sum(r for r in returns if r < 0))
    return round(wins / losses, 2) if losses else None


def _bt_analyze(pattern: str = None, ticker_field: str = None, daily_prices: dict = None,
                has_target_stop: bool = False, signals_data: list = None) -> dict:
    """단일 전략 백테스트 분석."""
    records = []
    
    # 데이터 소스 결정 (파일 패턴 vs 직접 전달된 데이터)
    if signals_data is not None:
        raw_signals = signals_data
    elif pattern:
        raw_signals = []
        for fp2 in sorted(glob.glob(os.path.join(DATA_DIR, pattern))):
            try:
                raw = json.load(open(fp2, encoding='utf-8'))
                sigs = raw.get('signals', []) if isinstance(raw, dict) else raw
                file_date = raw.get('date', '') if isinstance(raw, dict) else ''
                for s in sigs:
                    if isinstance(s, dict):
                        if 'file_date' not in s: s['file_date'] = file_date
                        raw_signals.append(s)
            except Exception:
                pass
    else:
        return {}

    for sig in raw_signals:
        ticker   = sig.get(ticker_field) or sig.get('code') or sig.get('stock_code') or sig.get('ticker', '')
        # signal_date가 없으면 file_date(파일기반) 사용
        sig_date = (sig.get('signal_date') or sig.get('entry_date') or sig.get('file_date') or '').replace('/', '-')
        
        if not ticker or not sig_date:
            continue
        
        rows = daily_prices.get(ticker, [])
        # 5일, 20일 수익률
        r5  = _fwd_return(rows, sig_date, 5)
        r20 = _fwd_return(rows, sig_date, 20)
        month = sig_date[:7] if len(sig_date) >= 7 else ''
        records.append({
            'ticker':     ticker,
            'name':       sig.get('name') or sig.get('stock_name', ''),
            'signal_date': sig_date,
            'month':       month,
            'score':       sig.get('score', 0),
            'grade':       sig.get('grade', ''),
            'return_5d':  r5,
            'return_20d': r20,
        })

    records.sort(key=lambda x: x['signal_date'])

    # 평가 가능한 레코드만
    c5  = [r for r in records if r['return_5d']  is not None]
    c20 = [r for r in records if r['return_20d'] is not None]

    # 기본 통계
    def stats(lst, key):
        vals = [r[key] for r in lst]
        if not vals:
            return {'count': 0, 'win_rate': 0.0, 'avg': 0.0, 'pf': None, 'max_cons_loss': 0}
        wins = [v for v in vals if v > 0]
        return {
            'count':         len(vals),
            'win_rate':      round(len(wins) / len(vals) * 100, 1),
            'avg':           round(sum(vals) / len(vals), 2),
            'pf':            _profit_factor(vals),
            'max_cons_loss': _consecutive_losses(vals),
        }

    s5  = stats(c5,  'return_5d')
    s20 = stats(c20, 'return_20d')

    # 누적 수익 곡선 (20일 기준, 종목당 1% 리스크 가정)
    equity, eq = [100.0], 100.0
    for r in c20:
        eq = eq * (1 + r['return_20d'] / 100 * 0.01)  # 1% 리스크 per trade
        equity.append(round(eq, 4))
    mdd = _max_drawdown(equity)

    # 월별 성과
    monthly: dict = {}
    for r in c20:
        m = r['month']
        if not m:
            continue
        monthly.setdefault(m, []).append(r['return_20d'])
    monthly_stats = {
        m: {'avg': round(sum(v)/len(v), 2), 'count': len(v),
            'win_rate': round(len([x for x in v if x>0])/len(v)*100,1)}
        for m, v in sorted(monthly.items())
    }

    # 최근 30건 롤링 승률 (20일 기준)
    rolling_wr = None
    if len(c20) >= 10:
        last30 = c20[-30:]
        wins30 = len([r for r in last30 if r['return_20d'] > 0])
        rolling_wr = round(wins30 / len(last30) * 100, 1)

    return {
        'total':         len(records),
        'stats_5d':      s5,
        'stats_20d':     s20,
        'max_drawdown':  mdd,
        'rolling_wr_30': rolling_wr,
        'equity_curve':  equity[-60:],   # 최근 60포인트만 전송
        'monthly':       monthly_stats,
        'recent':        records[-5:],
    }


@kr_bp.route('/backtest/detail')
@_cached_response(ttl_seconds=300)
def backtest_detail():
    """전략별 상세 백테스트 (수익곡선, MDD, Profit Factor, 월별)."""
    try:
        daily_prices = _load_daily_prices()
        # Supabase에서 보유 종목(Held Positions) 가져오기
        held_signals = []
        if _supabase:
            try:
                resp = _supabase.table("held_positions").select("*").execute()
                held_signals = resp.data or []
            except Exception:
                pass

        strategies = {
            'vcp':             _bt_analyze('vcp_signals_[0-9]*.json',        'code',       daily_prices, False),
            'closing_bet':     _bt_analyze('jongga_v2_results_[0-9]*.json',  'stock_code', daily_prices, True),
            'flow_momentum':   _bt_analyze('flow_momentum_[0-9]*.json',      'ticker',     daily_prices, False),
            'narrative':       _bt_analyze('narrative_momentum_[0-9]*.json', 'ticker',     daily_prices, False),
            'sector_rotation': _bt_analyze('sector_rotation_[0-9]*.json',    'ticker',     daily_prices, False),
            'contrarian':      _bt_analyze('contrarian_[0-9]*.json',         'ticker',     daily_prices, False),
            'held_positions':  _bt_analyze(signals_data=held_signals, ticker_field='ticker', daily_prices=daily_prices),
        }

        return jsonify({
            'strategies':       strategies,
            'updated_at':       datetime.now().strftime('%Y-%m-%d %H:%M'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/intraday-gems')
def intraday_gems():
    """장중 원석(Gem Hunter) 스캔 결과를 반환합니다."""
    try:
        filepath = os.path.join(DATA_DIR, 'intraday_gems.json')
        if not os.path.exists(filepath):
            return jsonify({"count": 0, "gems": [], "last_updated": None,
                            "message": "아직 스캔 데이터가 없습니다. 장중(09:05~15:25)에 자동 생성됩니다."})
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 백엔드 시작 시 가격 갱신 스레드 가동 (모든 함수 정의 후)
PriceCache.get_instance().start_refresh_thread(_fetch_yfinance_fallback, interval=60)
