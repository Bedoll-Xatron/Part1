"""
backtest.py
===========
kr_market/data/ 의 모든 전략 시그널 파일과 daily_prices.csv 를 이용해
D5/D10/D20 순방향 수익률을 계산하고 성과 요약을 출력한다.

실행:
  python backtest.py
  python backtest.py --strategy jongga_v2   # 특정 전략만
  python backtest.py --grade A              # 특정 등급만
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

# ── 경로 ──────────────────────────────────────────────────────────
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR   = os.path.normpath(os.path.join(_ENGINE_DIR, '..', 'data'))
_PRICES_CSV = os.path.join(_DATA_DIR, 'daily_prices.csv')

# 전략별 파일 패턴 → 전략명 매핑
_STRATEGY_PATTERNS = {
    "jongga_v2":        "jongga_v2_results_*.json",
    "vcp":              "vcp_signals_*.json",
    "flow_momentum":    "flow_momentum_*.json",
    "narrative":        "narrative_momentum_*.json",
    "sector_rotation":  "sector_rotation_*.json",
    "contrarian":       "contrarian_*.json",
}

_EVAL_DAYS = [5, 10, 20]
_TC_PCT    = 0.50  # 왕복 거래비용: 증권거래세 0.18% + 수수료 0.02% + 슬리피지 0.30%


# ── 데이터 로드 ────────────────────────────────────────────────────

def _load_prices() -> dict[str, list[dict]]:
    prices: dict[str, list[dict]] = {}
    if not os.path.exists(_PRICES_CSV):
        return prices
    with open(_PRICES_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            code = row.get('stock_code', '')
            if not code:
                continue
            prices.setdefault(code, []).append({
                'date':  row['date'],
                'open':  float(row.get('open')  or 0),
                'close': float(row.get('close') or 0),
                'high':  float(row.get('high')  or 0),
                'low':   float(row.get('low')   or 0),
            })
    for code in prices:
        prices[code].sort(key=lambda r: r['date'])
    return prices


def _close_after_n(price_rows: list[dict], sig_date: str, n: int) -> Optional[float]:
    future = [r for r in price_rows if r['date'] > sig_date]
    if len(future) < n:
        return None
    return future[n - 1]['close']


def _open_next_day(price_rows: list[dict], sig_date: str) -> Optional[float]:
    future = [r for r in price_rows if r['date'] > sig_date]
    if not future:
        return None
    o = future[0].get('open', 0)
    return float(o) if o and float(o) > 0 else None


def _hit_levels(price_rows: list[dict], sig_date: str, stop: float, target: float) -> tuple[bool, bool]:
    """손절/목표가 순차 도달 — 먼저 도달한 쪽만 기록, 당일 양쪽 동시 도달 시 손절 우선(보수적)."""
    future = [r for r in price_rows if r['date'] > sig_date][:20]
    for r in future:
        hit_s = stop   > 0 and r['low']  <= stop
        hit_t = target > 0 and r['high'] >= target
        if hit_s:
            return True, False
        if hit_t:
            return False, True
    return False, False


def _parse_date(s: str) -> str:
    if not s:
        return ''
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _extract_date_from_filename(fname: str) -> str:
    m = re.search(r'(\d{8})', fname)
    return _parse_date(m.group(1)) if m else ''


def _load_signals(strategy_filter: str = '') -> list[dict]:
    signals = []
    for strategy, pattern in _STRATEGY_PATTERNS.items():
        if strategy_filter and strategy != strategy_filter:
            continue
        files = sorted(glob.glob(os.path.join(_DATA_DIR, pattern)))
        # *_latest.json 제외 (중복)
        files = [f for f in files if 'latest' not in os.path.basename(f)]

        for fp in files:
            base_date = _extract_date_from_filename(os.path.basename(fp))
            try:
                with open(fp, encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                continue

            raw = data.get('signals', []) if isinstance(data, dict) else data
            if not isinstance(raw, list):
                continue

            for s in raw:
                code = s.get('stock_code') or s.get('code') or s.get('ticker') or ''
                name = s.get('stock_name') or s.get('name') or ''
                sig_date = _parse_date(
                    s.get('signal_date') or s.get('date') or base_date
                )
                grade = s.get('grade', '')
                if isinstance(grade, dict):
                    grade = grade.get('value', '')

                score_obj = s.get('score', {})
                if isinstance(score_obj, dict):
                    total_score  = score_obj.get('total', 0)
                    alpha_score  = score_obj.get('alpha_score', 0)
                    vcp_bonus    = score_obj.get('vcp_bonus', 0)
                    news_score   = score_obj.get('news', 0)
                    volume_score = score_obj.get('volume', 0)
                    chart_score  = score_obj.get('chart', 0)
                    supply_score = score_obj.get('supply', 0)
                else:
                    total_score = alpha_score = vcp_bonus = 0
                    news_score = volume_score = chart_score = supply_score = 0

                entry  = float(s.get('entry_price')  or s.get('price') or 0)
                stop   = float(s.get('stop_price')   or 0)
                target = float(s.get('target_price') or 0)
                quality = float(s.get('quality') or 0)

                if not code or not sig_date or entry <= 0:
                    continue

                signals.append({
                    'strategy':    strategy,
                    'stock_code':  code,
                    'stock_name':  name,
                    'signal_date': sig_date,
                    'grade':       str(grade),
                    'total_score': total_score,
                    'alpha_score': alpha_score,
                    'vcp_bonus':   vcp_bonus,
                    'news_score':  news_score,
                    'volume_score': volume_score,
                    'chart_score': chart_score,
                    'supply_score': supply_score,
                    'entry_price': entry,
                    'stop_price':  stop,
                    'target_price': target,
                    'quality':     quality,
                })

    # 중복 제거 (strategy + code + date)
    seen = set()
    unique = []
    for s in signals:
        key = (s['strategy'], s['stock_code'], s['signal_date'])
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return unique


# ── 수익률 계산 ────────────────────────────────────────────────────

@dataclass
class EvalRow:
    strategy: str
    stock_code: str
    stock_name: str
    signal_date: str
    grade: str
    total_score: int
    alpha_score: int
    entry_price: float
    stop_price: float
    target_price: float
    quality: float
    actual_entry: float = 0.0
    news_score:   int   = 0
    volume_score: int   = 0
    chart_score:  int   = 0
    supply_score: int   = 0
    d5:  Optional[float] = None
    d10: Optional[float] = None
    d20: Optional[float] = None
    hit_stop: bool   = False
    hit_target: bool = False

    @property
    def score_bucket(self) -> str:
        t = self.total_score
        if t <= 7:  return '≤7'
        if t <= 9:  return '8-9'
        if t <= 11: return '10-11'
        return '12+'


def evaluate(signals: list[dict], prices: dict) -> list[EvalRow]:
    rows = []
    for s in signals:
        code  = s['stock_code']
        sig_d = s['signal_date']
        entry = s['entry_price']
        stop  = s['stop_price']
        target = s['target_price']

        price_rows = prices.get(code, [])

        actual_entry = _open_next_day(price_rows, sig_d) or entry

        row = EvalRow(
            strategy     = s['strategy'],
            stock_code   = code,
            stock_name   = s['stock_name'],
            signal_date  = sig_d,
            grade        = s['grade'],
            total_score  = s['total_score'],
            alpha_score  = s['alpha_score'],
            entry_price  = entry,
            stop_price   = stop,
            target_price = target,
            quality      = s['quality'],
            actual_entry = actual_entry,
            news_score   = s['news_score'],
            volume_score = s['volume_score'],
            chart_score  = s['chart_score'],
            supply_score = s['supply_score'],
        )

        if price_rows:
            for n in _EVAL_DAYS:
                close_n = _close_after_n(price_rows, sig_d, n)
                if close_n is not None and actual_entry > 0:
                    pct = round((close_n - actual_entry) / actual_entry * 100 - _TC_PCT, 2)
                    setattr(row, f'd{n}', pct)

            hs, ht = _hit_levels(price_rows, sig_d, stop, target)
            row.hit_stop   = hs
            row.hit_target = ht

        rows.append(row)
    return rows


# ── 통계 집계 ──────────────────────────────────────────────────────

def _stats(rets: list[float]) -> dict:
    if not rets:
        return {"n": 0, "win_rate": 0, "avg": 0, "avg_win": 0, "avg_loss": 0, "pf": None}
    n = len(rets)
    wins   = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    win_rate = len(wins) / n
    avg_win  = round(sum(wins) / max(len(wins), 1), 2)
    avg_loss = round(sum(losses) / max(len(losses), 1), 2)
    # Profit Factor = avg_win / |avg_loss|  (승부비; >1 이면 양의 엣지)
    pf = round(avg_win / abs(avg_loss), 2) if avg_loss < 0 else None
    return {
        "n":        n,
        "win_rate": round(win_rate * 100, 1),
        "avg":      round(sum(rets) / n, 2),
        "avg_win":  avg_win,
        "avg_loss": avg_loss,
        "pf":       pf,
    }


def _risk_metrics(rets: list[float]) -> dict:
    """quantstats를 이용한 리스크 지표 (설치 시 자동 활성)."""
    out: dict = {"sharpe": None, "max_dd": None, "sortino": None}
    if len(rets) < 5:
        return out
    try:
        import math
        import warnings
        import pandas as pd
        import quantstats as qs
        warnings.filterwarnings("ignore")
        dates = pd.bdate_range(start="2020-01-01", periods=len(rets))
        s = pd.Series([r / 100.0 for r in rets], index=dates)

        def _safe(val, scale=1.0) -> Optional[float]:
            try:
                v = float(val) * scale
                return None if (math.isnan(v) or math.isinf(v)) else round(v, 2)
            except Exception:
                return None

        # 10일 수익률 기준 → 연환산 계수 25 (250 거래일 / 10)
        out["sharpe"]  = _safe(qs.stats.sharpe(s, periods=25))
        out["max_dd"]  = _safe(qs.stats.max_drawdown(s), scale=100)
        out["sortino"] = _safe(qs.stats.sortino(s, periods=25))
    except Exception:
        pass
    return out


def _print_risk_table(title: str, groups: dict[str, list[float]]) -> None:
    metrics = {k: _risk_metrics(v) for k, v in groups.items()}
    if not any(m["sharpe"] is not None for m in metrics.values()):
        return
    print(f"\n{'='*70}")
    print(f"  {title}  [리스크 지표 / quantstats]")
    print(f"{'='*70}")
    print(f"  {'그룹':<18} {'Sharpe':>8}  {'MaxDD':>8}  {'Sortino':>9}")
    print(f"  {'-'*50}")
    for key in sorted(metrics.keys()):
        m = metrics[key]
        if m["sharpe"] is None:
            continue
        sh_str = f"{m['sharpe']:>8.2f}"
        dd_str = f"{m['max_dd']:+.1f}%" if m["max_dd"] is not None else "    N/A"
        so_str = f"{m['sortino']:>9.2f}" if m["sortino"] is not None else f"{'N/A':>9}"
        print(f"  {key:<18} {sh_str}  {dd_str:>8}  {so_str}")
    print()


def _factor_ic_report(rows: list[EvalRow]) -> None:
    """Spearman IC 분석 (alphalens 방식) — 팩터별 D10 예측력."""
    try:
        from scipy.stats import spearmanr
    except ImportError:
        return

    d10_rows = [r for r in rows if r.d10 is not None]
    if len(d10_rows) < 10:
        return

    rets = [r.d10 for r in d10_rows]
    factors = [
        ("total_score",  [r.total_score  for r in d10_rows]),
        ("news_score",   [r.news_score   for r in d10_rows]),
        ("volume_score", [r.volume_score for r in d10_rows]),
        ("chart_score",  [r.chart_score  for r in d10_rows]),
        ("supply_score", [r.supply_score for r in d10_rows]),
        ("alpha_score",  [r.alpha_score  for r in d10_rows]),
        ("quality",      [r.quality      for r in d10_rows]),
    ]

    print(f"\n{'='*70}")
    print(f"  Factor IC (Spearman)  [alphalens 방식]  N={len(d10_rows)}")
    print(f"{'='*70}")
    print(f"  {'팩터':<18} {'IC':>8}  {'p-value':>10}  {'유의성':>6}")
    print(f"  {'-'*50}")
    for name, vals in factors:
        if len(set(vals)) < 2:
            continue
        ic, pval = spearmanr(vals, rets)
        sig = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else "-"
        print(f"  {name:<18} {ic:>8.3f}  {pval:>10.4f}  {sig:>6}")
    print()


def _print_table(title: str, groups: dict[str, list[float]], horizon: str):
    print(f"\n{'='*70}")
    print(f"  {title}  [{horizon}일 수익률 기준]")
    print(f"{'='*70}")
    print(f"  {'그룹':<18} {'N':>4}  {'승률':>7}  {'평균수익':>9}  {'평균손실':>9}  {'PF(익손비)':>11}")
    print(f"  {'-'*65}")
    for key in sorted(groups.keys()):
        st = _stats(groups[key])
        if st['n'] == 0:
            continue
        bar  = '#' * int(max(st['win_rate'] / 10, 0))
        pf_s = f"{st['pf']:>10.2f}x" if st['pf'] is not None else f"{'∞':>11}"
        print(f"  {key:<18} {st['n']:>4}  {st['win_rate']:>6.1f}%  "
              f"{st['avg']:>+8.2f}%  {st['avg_loss']:>+8.2f}%  "
              f"{pf_s}  {bar}")
    print()


def summarize(rows: list[EvalRow], grade_filter: str = ''):
    if grade_filter:
        rows = [r for r in rows if r.grade == grade_filter]

    evaluated = {n: [r for r in rows if getattr(r, f'd{n}') is not None]
                 for n in _EVAL_DAYS}

    # 전체 현황
    print(f"\n{'='*70}")
    print(f"  백테스트 결과 요약  (총 시그널: {len(rows)}개)")
    print(f"  가격 데이터 보유: D5={len(evaluated[5])} / D10={len(evaluated[10])} / D20={len(evaluated[20])}")
    print(f"{'='*70}")

    if not evaluated[10]:
        print("  ⚠  D10 수익률 계산 가능한 시그널이 없습니다.")
        print("     daily_prices.csv 에 시그널 이후 10 거래일치 데이터가 필요합니다.")
        _show_signal_coverage(rows)
        return

    horizon = 10  # 기준 수익률 지평
    eval_rows = sorted(evaluated[horizon], key=lambda r: r.signal_date)

    # 전략별
    by_strategy: dict[str, list[float]] = defaultdict(list)
    for r in eval_rows:
        by_strategy[r.strategy].append(getattr(r, f'd{horizon}'))
    _print_table("전략별 성과", by_strategy, horizon)
    _print_risk_table("전략별 리스크", by_strategy)

    # 등급별
    by_grade: dict[str, list[float]] = defaultdict(list)
    for r in eval_rows:
        by_grade[r.grade or 'N/A'].append(getattr(r, f'd{horizon}'))
    _print_table("등급별 성과 (A/B/C)", by_grade, horizon)

    # 점수구간별
    by_bucket: dict[str, list[float]] = defaultdict(list)
    for r in eval_rows:
        by_bucket[r.score_bucket].append(getattr(r, f'd{horizon}'))
    _print_table("총점 구간별 성과", by_bucket, horizon)

    # 알파 보너스 유무별
    by_alpha: dict[str, list[float]] = defaultdict(list)
    for r in eval_rows:
        key = 'alpha≥1' if r.alpha_score >= 1 else 'alpha=0'
        by_alpha[key].append(getattr(r, f'd{horizon}'))
    _print_table("Alpha 보너스 유무별 성과", by_alpha, horizon)

    # D5 / D20 비교
    for n in [5, 20]:
        if not evaluated[n]:
            continue
        by_g: dict[str, list[float]] = defaultdict(list)
        for r in evaluated[n]:
            by_g[r.grade or 'N/A'].append(getattr(r, f'd{n}'))
        _print_table(f"등급별 성과", by_g, n)

    # 손절·목표가 히트율
    with_levels = [r for r in eval_rows if r.stop_price > 0 and r.target_price > 0]
    if with_levels:
        hit_t = sum(1 for r in with_levels if r.hit_target)
        hit_s = sum(1 for r in with_levels if r.hit_stop)
        print(f"\n  손절·목표 히트율 (N={len(with_levels)})")
        print(f"    목표가 도달: {hit_t}/{len(with_levels)} = {hit_t/len(with_levels)*100:.1f}%")
        print(f"    손절선 터치: {hit_s}/{len(with_levels)} = {hit_s/len(with_levels)*100:.1f}%")

    # Factor IC 분석
    _factor_ic_report(eval_rows)

    # Top 10 시그널 (D10 수익률 순)
    top = sorted(eval_rows, key=lambda r: getattr(r, f'd{horizon}') or 0, reverse=True)[:10]
    print(f"\n  Top 10 시그널 (D{horizon} 기준)")
    print(f"  {'날짜':<12} {'코드':<8} {'이름':<14} {'전략':<16} {'등급'} {'점수':>4} {'D10':>8}")
    print(f"  {'-'*70}")
    for r in top:
        ret = getattr(r, f'd{horizon}')
        print(f"  {r.signal_date:<12} {r.stock_code:<8} {r.stock_name[:12]:<14} "
              f"{r.strategy[:14]:<16} {r.grade:>2}    {r.total_score:>3}  {ret:>+7.2f}%")


def _show_signal_coverage(rows: list[EvalRow]):
    """가격 데이터 없을 때 시그널 날짜 분포 표시."""
    dates = sorted(set(r.signal_date for r in rows))
    print(f"\n  시그널 날짜 범위: {dates[0] if dates else '?'} ~ {dates[-1] if dates else '?'}")
    print(f"  총 {len(rows)}개 시그널 / {len(dates)}개 날짜")
    print(f"\n  daily_prices.csv 경로: {_PRICES_CSV}")
    if os.path.exists(_PRICES_CSV):
        with open(_PRICES_CSV, newline='', encoding='utf-8') as f:
            price_rows = list(csv.DictReader(f))
        if price_rows:
            pdates = sorted(set(r['date'] for r in price_rows))
            print(f"  가격 데이터 날짜 범위: {pdates[0]} ~ {pdates[-1]} ({len(pdates)}개 날짜)")
    print("\n  → build_daily_prices.py 를 실행해 가격 데이터를 먼저 수집하세요.")


# ── 진입점 ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="시그널 백테스트")
    parser.add_argument('--strategy', default='', help='전략 필터 (예: jongga_v2, vcp)')
    parser.add_argument('--grade',    default='', help='등급 필터 (A/B/C)')
    args = parser.parse_args()

    print("=== 시그널 로드 중... ===")
    signals = _load_signals(args.strategy)
    print(f"  시그널 수: {len(signals)}개")
    if not signals:
        print("  시그널 없음. data/ 디렉토리에 결과 JSON이 있는지 확인하세요.")
        return

    print("\n=== 가격 데이터 로드 중... ===")
    prices = _load_prices()
    print(f"  종목 수: {len(prices)}  "
          f"({'가격 데이터 없음' if not prices else '로드 완료'})")

    print("\n=== 수익률 계산 중... ===")
    rows = evaluate(signals, prices)

    summarize(rows, grade_filter=args.grade)


if __name__ == '__main__':
    main()
