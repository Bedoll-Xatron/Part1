"""
시장 국면 감지 (Market Regime Detection)
=========================================
KODEX200(069500) 기준 이동평균으로 현재 시장 국면을 판별합니다.

국면 분류:
  BULL     : 지수 > MA200  AND  MA50 > MA200  (강세장 – 풀 포지션)
  CAUTION  : 지수 > MA200  BUT  MA50 <= MA200 (비강세 – 보수적 운용)
             OR  지수 < MA200  AND  MA50 > MA200 (조정 국면)
  BEAR     : 지수 < MA200  AND  MA50 <= MA200  (약세장 – 매수 중단)

사용법:
  from market_regime import MarketRegime, RegimeLevel
  regime = MarketRegime()
  level, detail = regime.detect()
  if level == RegimeLevel.BEAR:
      print("매수 중단")
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

# ── 경로 설정 ──────────────────────────────────────────────────────
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR   = os.path.normpath(os.path.join(_ENGINE_DIR, '..', 'data'))
sys.path.insert(0, _ENGINE_DIR)

from collectors import get_chart_data  # type: ignore

# KODEX200 (코스피200 추종 ETF – 지수 프록시)
_KODEX200 = "069500"


class RegimeLevel(Enum):
    BULL     = "BULL"      # 강세장 – 기본 전략 풀 가동
    CAUTION  = "CAUTION"   # 보수적 – 필터 강화, A등급만 매수
    BEAR     = "BEAR"      # 약세장 – 매수 신호 전면 차단


@dataclass
class RegimeDetail:
    """국면 판별 상세 정보"""
    level: RegimeLevel
    kospi_close: float        # KODEX200 현재가 (지수 프록시)
    ma20: float               # 20일 이동평균
    ma60: float               # 60일 이동평균
    ma50: float               # 50일 이동평균
    ma200: float              # 200일 이동평균
    above_ma200: bool         # 지수 > MA200 여부
    ma50_gt_ma200: bool       # MA50 > MA200 (골든크로스 여부)
    above_ma60: bool          # 지수 > MA60 여부 (중기 추세)
    above_ma20: bool          # 지수 > MA20 여부 (단기 추세)
    score: int                # 0~5: 강도 점수
    description: str          # 국면 설명 (한국어)
    signal_date: str          # 분석 기준일


# ── 이동평균 계산 헬퍼 ─────────────────────────────────────────────

def _sma(closes: list[float], period: int) -> Optional[float]:
    """단순 이동평균. 데이터 부족하면 None."""
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


# ── 메인 클래스 ───────────────────────────────────────────────────

class MarketRegime:
    """시장 국면 감지기"""

    def __init__(self, proxy_code: str = _KODEX200):
        self.proxy_code = proxy_code

    def detect(self, target_date: date | None = None) -> tuple[RegimeLevel, RegimeDetail]:
        """
        현재 시장 국면을 감지합니다.

        Returns:
            (RegimeLevel, RegimeDetail) 튜플
        """
        effective_date = target_date or date.today()
        date_str = effective_date.isoformat()

        print(f"  [시장 국면 감지] KODEX200({self.proxy_code}) 차트 수집 중...")
        try:
            charts = get_chart_data(self.proxy_code, days=220)
        except Exception as e:
            print(f"  [경고] KODEX200 차트 수집 실패: {e}. CAUTION 기본 반환.")
            return self._default_caution(date_str)

        if not charts or len(charts) < 60:
            print(f"  [경고] KODEX200 데이터 부족({len(charts) if charts else 0}일). CAUTION 기본 반환.")
            return self._default_caution(date_str)

        closes = [float(c.close) for c in charts]
        current = closes[-1]

        ma20  = _sma(closes, 20)
        ma60  = _sma(closes, 60)
        ma50  = _sma(closes, 50)
        ma200 = _sma(closes, 200)

        # MA200 데이터 부족이면 MA150으로 대체 (초기 운영 시)
        if ma200 is None:
            ma200 = _sma(closes, min(len(closes), 150))

        if ma50 is None or ma200 is None or ma20 is None or ma60 is None:
            return self._default_caution(date_str)

        above_ma200   = current > ma200
        ma50_gt_ma200 = ma50 > ma200
        above_ma60    = current > ma60
        above_ma20    = current > ma20

        # ── 국면 판별 ──────────────────────────────────────────────
        # 강도 점수 (5점 만점)
        # 장기(+2): MA200 위
        # 중기(+2): MA50 골든크로스 + MA60 위
        # 단기(+1): MA20 위 (빠른 반응)
        score = 0
        if above_ma200:   score += 2
        if ma50_gt_ma200: score += 1
        if above_ma60:    score += 1
        if above_ma20:    score += 1

        if score >= 4:
            level = RegimeLevel.BULL
            desc  = f"강세장 | KODEX200 {current:,.0f}  MA200 {ma200:,.0f} 상단  (점수 {score}/5)"
        elif score >= 2:
            level = RegimeLevel.CAUTION
            desc  = f"주의   | KODEX200 {current:,.0f}  지수/이평 혼재  (점수 {score}/5)"
        else:
            level = RegimeLevel.BEAR
            desc  = f"약세장 | KODEX200 {current:,.0f}  MA200 {ma200:,.0f} 하단  (점수 {score}/5)"

        print(f"  [시장 국면] {desc}")

        detail = RegimeDetail(
            level=level,
            kospi_close=current,
            ma20=ma20,
            ma60=ma60,
            ma50=ma50,
            ma200=ma200,
            above_ma200=above_ma200,
            ma50_gt_ma200=ma50_gt_ma200,
            above_ma60=above_ma60,
            above_ma20=above_ma20,
            score=score,
            description=desc,
            signal_date=date_str,
        )
        return level, detail

    @staticmethod
    def _default_caution(date_str: str) -> tuple[RegimeLevel, RegimeDetail]:
        """데이터 수집 실패 시 기본 CAUTION 반환."""
        detail = RegimeDetail(
            level=RegimeLevel.CAUTION,
            kospi_close=0.0,
            ma20=0.0,
            ma60=0.0,
            ma50=0.0,
            ma200=0.0,
            above_ma200=False,
            ma50_gt_ma200=False,
            above_ma60=False,
            above_ma20=False,
            score=0,
            description="국면 판별 불가 – 기본 CAUTION 적용",
            signal_date=date_str,
        )
        return RegimeLevel.CAUTION, detail

    @staticmethod
    def is_contrarian_safe(level: RegimeLevel) -> bool:
        """역발상 반전 전략 진입 허용 여부 (BULL 국면에서만 허용)."""
        return level == RegimeLevel.BULL

    # ── 국면별 필터 설정 반환 ─────────────────────────────────────

    @staticmethod
    def get_filter_overrides(level: RegimeLevel) -> dict:
        """
        국면별 SignalConfig 오버라이드 값을 반환합니다.

        Returns:
            dict with keys: min_total_score, min_quality, allow_grades,
                            position_scale (0.0~1.0), buy_enabled
        """
        if level == RegimeLevel.BULL:
            return {
                "min_total_score":  8,    # 기본값 유지
                "min_quality":      55.0,
                "allow_grades":     ["A", "B"],
                "position_scale":   1.0,   # 풀 베팅
                "buy_enabled":      True,
            }
        elif level == RegimeLevel.CAUTION:
            return {
                "min_total_score":  9,    # +1 상향
                "min_quality":      60.0, # +5 상향
                "allow_grades":     ["A"],  # A등급만
                "position_scale":   0.7,   # 70%로 축소
                "buy_enabled":      True,
            }
        else:  # BEAR
            return {
                "min_total_score":  15,   # 사실상 통과 불가
                "min_quality":      90.0,
                "allow_grades":     [],   # 빈 리스트 → 매수 전면 차단
                "position_scale":   0.0,
                "buy_enabled":      False,
            }


# ── 독립 실행 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    regime = MarketRegime()
    level, detail = regime.detect()

    print("\n" + "=" * 60)
    print(f"  시장 국면: {level.value}")
    print(f"  설명     : {detail.description}")
    print(f"  KODEX200 : {detail.kospi_close:,.0f}")
    print(f"  MA20     : {detail.ma20:,.0f}  {'위' if detail.above_ma20 else '아래'}")
    print(f"  MA60     : {detail.ma60:,.0f}  {'위' if detail.above_ma60 else '아래'}")
    print(f"  MA50     : {detail.ma50:,.0f}")
    print(f"  MA200    : {detail.ma200:,.0f}  {'위' if detail.above_ma200 else '아래'}")
    print(f"  골든크로스: {detail.ma50_gt_ma200}")
    print(f"  강도 점수 : {detail.score}/5")
    print(f"  역발상 허용: {MarketRegime.is_contrarian_safe(level)}")
    overrides = MarketRegime.get_filter_overrides(level)
    print(f"\n  적용 필터 오버라이드:")
    for k, v in overrides.items():
        print(f"    {k}: {v}")
    print("=" * 60)
