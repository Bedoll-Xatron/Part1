"""
Alpha158 핵심 팩터 서브셋 — OHLCV 데이터로 계산 가능한 기술적 팩터.

참조: microsoft/qlib Alpha158DL (github.com/microsoft/qlib)
윈도우: 5/20/60일 (현 프로젝트 수집 범위 내)
"""

import statistics
from dataclasses import dataclass
from typing import List, Optional

from models import ChartData


@dataclass
class AlphaFactors:
    # 변동성 수축 (VCP 핵심 시그널)
    std5: float = 0.0       # 5일 변동성 / 현재가
    std20: float = 0.0      # 20일 변동성 / 현재가
    std_ratio: float = 1.0  # std5 / std20 — 1 미만이면 수축 중

    # 모멘텀
    roc5: float = 0.0       # 5일 수익률
    roc20: float = 0.0      # 20일 수익률
    roc60: float = 0.0      # 60일 수익률 (데이터 부족 시 0)

    # RSI-like (14일 업다운 비율, 0~1)
    rsi14: float = 0.5

    # 거래량
    vma20_ratio: float = 0.0  # 오늘 거래량 / 20일 평균 거래량

    # 가격 위치
    rsv20: float = 0.0   # (종가 - 20일 저가) / (20일 고가 - 20일 저가), 0~1
    imax20: int = 20     # 최근 20일 고점 이후 경과일 (0 = 오늘이 고점)


def compute_alpha_factors(charts: List[ChartData]) -> Optional[AlphaFactors]:
    """ChartData 리스트(오름차순)로 AlphaFactors를 계산한다. 20봉 미만이면 None."""
    if len(charts) < 20:
        return None

    n = len(charts)
    close = [float(c.close) for c in charts]
    high  = [float(c.high)  for c in charts]
    low   = [float(c.low)   for c in charts]
    vol   = [float(c.volume) for c in charts]

    c_last = close[-1]
    if c_last <= 0:
        return None

    f = AlphaFactors()

    # STD (가격 표준편차 / 현재가)
    if len(close) >= 5 and len(set(close[-5:])) > 1:
        f.std5 = statistics.stdev(close[-5:]) / c_last
    f.std20 = statistics.stdev(close[-20:]) / c_last if len(set(close[-20:])) > 1 else 0.0
    f.std_ratio = f.std5 / f.std20 if f.std20 > 0 else 1.0

    # ROC
    if n >= 6 and close[-6] > 0:
        f.roc5 = close[-1] / close[-6] - 1
    if n >= 21 and close[-21] > 0:
        f.roc20 = close[-1] / close[-21] - 1
    if n >= 61 and close[-61] > 0:
        f.roc60 = close[-1] / close[-61] - 1

    # RSI-like (14일)
    if n >= 15:
        gains  = sum(max(close[i] - close[i - 1], 0) for i in range(-14, 0))
        losses = sum(max(close[i - 1] - close[i], 0) for i in range(-14, 0))
        f.rsi14 = gains / (gains + losses + 1e-12)

    # VMA ratio
    vol_avg20 = sum(vol[-20:]) / 20
    f.vma20_ratio = vol[-1] / vol_avg20 if vol_avg20 > 0 else 0.0

    # RSV (스토캐스틱 분자)
    h20 = max(high[-20:])
    l20 = min(low[-20:])
    f.rsv20 = (c_last - l20) / (h20 - l20 + 1e-12)

    # IMAX (최근 20일 내 고점 이후 경과일)
    max_idx = max(range(20), key=lambda i: high[n - 20 + i])
    f.imax20 = 19 - max_idx  # 0 = 오늘이 고점, 19 = 20일 전이 고점

    return f
