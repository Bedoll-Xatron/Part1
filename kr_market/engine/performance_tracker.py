"""
성과 추적기 (Performance Tracker)
====================================
시그널 생성 시 기록하고, 매일 실행 시 N일 후 수익률을 자동으로 계산합니다.

파이프라인:
  1. 시그널 기록 : log_signals(signals) → signals_log.csv 에 추가
  2. 수익률 계산 : update_returns()   → daily_prices.csv 에서 종가 조회 후 수익률 기입
  3. 성과 집계   : compute_summary()  → performance_summary.json 생성

저장 경로:
  kr_market/data/signals_log.csv
  kr_market/data/performance_summary.json
"""

from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

# ── 경로 설정 ──────────────────────────────────────────────────────
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR   = os.path.normpath(os.path.join(_ENGINE_DIR, '..', 'data'))
sys.path.insert(0, _ENGINE_DIR)

_LOG_CSV     = os.path.join(_DATA_DIR, 'signals_log.csv')
_SUMMARY_JSON = os.path.join(_DATA_DIR, 'performance_summary.json')
_PRICES_CSV  = os.path.join(_DATA_DIR, 'daily_prices.csv')

_LOG_FIELDS = [
    "signal_date", "stock_code", "stock_name", "market",
    "grade", "strategy",
    "entry_price", "stop_price", "target_price",
    "score", "quality",
    # 수익률 (나중에 채워짐)
    "d5_close", "d5_return_pct",
    "d10_close", "d10_return_pct",
    "d20_close", "d20_return_pct",
    "hit_stop", "hit_target",
    "updated_at",
]

# 평가 시점 (영업일 기준이 아닌 캘린더 일수 – 단순화)
_EVAL_DAYS = [5, 10, 20]


# ── 시그널 기록 ───────────────────────────────────────────────────

def log_signals(signals: list, strategy: str = "jongga_v2") -> int:
    """
    시그널 목록을 signals_log.csv 에 추가합니다.

    Parameters:
        signals : Signal 객체 목록 (run_engine.py의 Signal 또는 dict)
        strategy: 전략명

    Returns:
        기록된 행 수
    """
    os.makedirs(_DATA_DIR, exist_ok=True)

    # 기존 파일에서 중복 확인 (signal_date + stock_code 기준)
    existing_keys: set[tuple] = set()
    if os.path.exists(_LOG_CSV):
        with open(_LOG_CSV, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                existing_keys.add((row.get('signal_date', ''), row.get('stock_code', '')))

    new_rows = []
    for sig in signals:
        # Signal 객체 또는 dict 모두 지원
        if isinstance(sig, dict):
            sd   = sig.get('signal_date', date.today().isoformat())
            code = sig.get('stock_code', '')
            name = sig.get('stock_name', '')
            mkt  = sig.get('market', '')
            grd  = sig.get('grade', '')
            ep   = sig.get('entry_price', 0)
            sp   = sig.get('stop_price', 0)
            tp   = sig.get('target_price', 0)
            sc   = sig.get('score', 0)
            ql   = sig.get('quality', 0)
        else:
            sd   = getattr(sig, 'signal_date', date.today()).isoformat() \
                   if not isinstance(getattr(sig, 'signal_date', ''), str) \
                   else sig.signal_date
            code = sig.stock_code
            name = sig.stock_name
            mkt  = sig.market
            grd  = sig.grade.value if hasattr(sig.grade, 'value') else str(sig.grade)
            ep   = sig.entry_price
            sp   = sig.stop_price
            tp   = sig.target_price
            sc   = sig.score.total if hasattr(sig, 'score') else 0
            ql   = sig.quality

        key = (str(sd), str(code))
        if key in existing_keys:
            continue  # 중복 스킵
        existing_keys.add(key)

        new_rows.append({
            "signal_date":    str(sd),
            "stock_code":     str(code),
            "stock_name":     str(name),
            "market":         str(mkt),
            "grade":          str(grd),
            "strategy":       strategy,
            "entry_price":    ep,
            "stop_price":     sp,
            "target_price":   tp,
            "score":          sc,
            "quality":        ql,
            "d5_close":       "",
            "d5_return_pct":  "",
            "d10_close":      "",
            "d10_return_pct": "",
            "d20_close":      "",
            "d20_return_pct": "",
            "hit_stop":       "",
            "hit_target":     "",
            "updated_at":     "",
        })

    if not new_rows:
        return 0

    mode = 'a' if os.path.exists(_LOG_CSV) else 'w'
    with open(_LOG_CSV, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=_LOG_FIELDS)
        if mode == 'w':
            writer.writeheader()
        writer.writerows(new_rows)

    print(f"  [PerformanceTracker] {len(new_rows)}개 시그널 기록 완료 → {_LOG_CSV}")
    return len(new_rows)


# ── 수익률 업데이트 ───────────────────────────────────────────────

def _load_prices() -> dict[str, list[dict]]:
    """daily_prices.csv를 {stock_code: [{date, close, high, low}, ...]} 형태로 로드."""
    prices: dict[str, list[dict]] = {}
    if not os.path.exists(_PRICES_CSV):
        return prices
    with open(_PRICES_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            code = row.get('stock_code', '')
            if not code:
                continue
            prices.setdefault(code, []).append({
                'date':  row.get('date', ''),
                'close': float(row.get('close', 0) or 0),
                'high':  float(row.get('high', 0) or 0),
                'low':   float(row.get('low', 0) or 0),
            })
    # 날짜 오름차순 정렬
    for code in prices:
        prices[code].sort(key=lambda r: r['date'])
    return prices


def _get_close_after_n_days(
    price_rows: list[dict], signal_date_str: str, n: int
) -> Optional[float]:
    """signal_date 이후 n번째 거래일 종가를 반환. 없으면 None."""
    future = [r for r in price_rows if r['date'] > signal_date_str]
    if len(future) < n:
        return None
    return future[n - 1]['close']


def update_returns() -> int:
    """
    signals_log.csv 에서 수익률이 비어 있는 행을 찾아,
    daily_prices.csv 참조해 수익률을 채웁니다.

    Returns:
        업데이트된 행 수
    """
    if not os.path.exists(_LOG_CSV):
        print("  [PerformanceTracker] signals_log.csv 없음, 건너뜀")
        return 0

    prices_map = _load_prices()
    rows: list[dict] = []
    updated = 0

    with open(_LOG_CSV, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        # 이미 d20이 채워졌으면 건너뜀
        if row.get('d20_return_pct'):
            continue

        code       = row.get('stock_code', '')
        sig_date   = row.get('signal_date', '')
        entry_price = float(row.get('entry_price', 0) or 0)
        stop_price  = float(row.get('stop_price', 0) or 0)
        target_price = float(row.get('target_price', 0) or 0)

        if not code or not sig_date or entry_price <= 0:
            continue

        price_rows = prices_map.get(code, [])
        if not price_rows:
            continue

        any_filled = False
        for n in _EVAL_DAYS:
            close_n = _get_close_after_n_days(price_rows, sig_date, n)
            if close_n is None:
                continue
            ret_pct = round((close_n - entry_price) / entry_price * 100, 2)
            row[f'd{n}_close']      = close_n
            row[f'd{n}_return_pct'] = ret_pct
            any_filled = True

        if any_filled:
            # 손절/목표가 터치 여부
            future_rows = [r for r in price_rows if r['date'] > sig_date][:20]
            if stop_price > 0:
                row['hit_stop']   = int(any(r['low'] <= stop_price for r in future_rows))
            if target_price > 0:
                row['hit_target'] = int(any(r['high'] >= target_price for r in future_rows))
            row['updated_at'] = datetime.now().isoformat()
            updated += 1

    if updated:
        with open(_LOG_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=_LOG_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  [PerformanceTracker] {updated}개 행 수익률 업데이트 완료")

    return updated


# ── 성과 집계 ─────────────────────────────────────────────────────

def compute_summary() -> dict:
    """
    signals_log.csv 에서 전략·등급별 성과를 집계하고
    performance_summary.json 으로 저장합니다.

    Returns:
        summary dict
    """
    if not os.path.exists(_LOG_CSV):
        return {}

    with open(_LOG_CSV, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    def _safe_float(v):
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    # 전략별 집계
    groups: dict[str, list[float]] = {}
    for row in rows:
        key = f"{row.get('strategy', 'unknown')}__{row.get('grade', 'X')}"
        ret = _safe_float(row.get('d10_return_pct'))
        if ret is None:
            continue
        groups.setdefault(key, []).append(ret)

    summary_items = []
    for key, rets in groups.items():
        strategy, grade = key.split('__')
        wins = [r for r in rets if r > 0]
        win_rate = len(wins) / len(rets) if rets else 0
        avg_r    = round(sum(rets) / len(rets), 2) if rets else 0
        # Expectancy = WinRate × AvgWin - LossRate × AvgLoss
        avg_win  = round(sum(r for r in rets if r > 0) / max(len(wins), 1), 2)
        avg_loss_vals = [r for r in rets if r <= 0]
        avg_loss = round(sum(avg_loss_vals) / max(len(avg_loss_vals), 1), 2)
        expectancy = round(win_rate * avg_win + (1 - win_rate) * avg_loss, 2)

        summary_items.append({
            "strategy":   strategy,
            "grade":      grade,
            "total":      len(rets),
            "win_rate":   round(win_rate * 100, 1),
            "avg_return": avg_r,
            "avg_win":    avg_win,
            "avg_loss":   avg_loss,
            "expectancy": expectancy,
        })

    summary_items.sort(key=lambda x: -x['expectancy'])

    summary = {
        "updated_at": datetime.now().isoformat(),
        "total_signals": len(rows),
        "evaluated_signals": sum(len(v) for v in groups.values()),
        "by_strategy_grade": summary_items,
    }

    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_SUMMARY_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"  [PerformanceTracker] 성과 집계 완료 → {_SUMMARY_JSON}")
    print(f"    총 시그널: {summary['total_signals']}  "
          f"평가 완료: {summary['evaluated_signals']}")
    for item in summary_items[:5]:
        print(f"    [{item['strategy']}/{item['grade']}] "
              f"WinRate {item['win_rate']:.0f}%  AvgR {item['avg_return']:+.2f}%  "
              f"Expectancy {item['expectancy']:+.2f}%")

    return summary


# ── 독립 실행 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== 수익률 업데이트 ===")
    update_returns()
    print("\n=== 성과 집계 ===")
    compute_summary()
