from typing import List, Optional, Tuple

from alpha_factors import compute_alpha_factors
from config import Grade, SignalConfig
from models import (
    ChecklistDetail,
    ChartData,
    NewsData,
    ScoreDetail,
    StockData,
    SupplyData,
)


class Scorer:
    def __init__(self, config: SignalConfig = None):
        self.config = config or SignalConfig()

    def calculate(
        self,
        stock: StockData,
        charts: List[ChartData],
        news_list: List[NewsData],
        supply: Optional[SupplyData],
        llm_result: Optional[dict] = None,
    ) -> Tuple[ScoreDetail, ChecklistDetail]:
        score = ScoreDetail()
        checklist = ChecklistDetail()

        # 1. 뉴스/재료 점수 (0~3)
        score.news, news_flags = self._score_news(news_list, llm_result)
        checklist.has_news = news_flags["has_news"]
        checklist.news_sources = news_flags["sources"]
        score.llm_reason = news_flags["reason"]

        # 2. 거래대금 점수 (0~3)
        score.volume, checklist.volume_sufficient = self._score_volume(stock)

        # 3. 차트패턴 점수 (0~3)
        score.chart, chart_flags = self._score_chart(stock, charts)
        checklist.is_new_high = chart_flags["new_high"]
        checklist.is_breakout = chart_flags["breakout"]
        checklist.ma_aligned = chart_flags["ma_aligned"]

        # 4. 캔듸형태 점수 (0~1)
        score.candle, candle_flags = self._score_candle(stock, charts)
        checklist.good_candle = candle_flags["good"]
        checklist.upper_wick_long = candle_flags["upper_wick_long"]

        # 5. 기간조정 점수 (0~1)
        score.consolidation, checklist.has_consolidation = \
            self._score_consolidation(charts)

        # 6. 수급 점수 (0~2)
        score.supply, checklist.supply_positive = self._score_supply(supply)

        # 7. 조정폭 회복 점수 (0~1)
        score.retracement, checklist.retracement_recovery = \
            self._score_retracement_recovery(charts)

        # 8. 되돌림 지지 점수 (0~1)
        score.pullback_support, checklist.pullback_support_confirmed = \
            self._score_pullback_support(charts)

        # 9. Alpha158 팩터 보너스 (0~2)
        score.alpha_score, alpha_flags = self._score_alpha_factors(charts)
        checklist.volatility_squeeze    = alpha_flags["volatility_squeeze"]
        checklist.volume_breakout       = alpha_flags["volume_breakout"]
        checklist.rsi_strong            = alpha_flags["rsi_strong"]
        checklist.price_near_high       = alpha_flags["price_near_high"]
        checklist.near_new_high         = alpha_flags["near_new_high"]
        checklist.momentum_accelerating = alpha_flags["momentum_accelerating"]
        checklist.macd_golden_cross     = alpha_flags["macd_golden_cross"]
        checklist.bb_squeeze            = alpha_flags["bb_squeeze"]
        checklist.stoch_bullish         = alpha_flags["stoch_bullish"]

        # 10. VCP 패턴 보너스 (0~1)
        score.vcp_bonus = self._score_vcp_bonus(charts)
        checklist.vcp_detected = score.vcp_bonus > 0

        # 11. Short Squeeze 보너스 (0~2) — pykrx 설치 시 자동 활성
        try:
            from short_squeeze import ShortSqueezeScorer  # type: ignore
            _sq = ShortSqueezeScorer()
            score.squeeze_bonus = _sq.squeeze_bonus(stock.code, score.supply)
        except Exception:
            score.squeeze_bonus = 0

        return score, checklist

    def _score_news(
        self, news_list: List[NewsData], llm_result: Optional[dict]
    ) -> Tuple[int, dict]:
        flags = {"has_news": False, "sources": [], "reason": ""}

        # LLM 분석 결과가 있으면 우선 사용
        if llm_result and isinstance(llm_result.get("score"), int):
            pts = max(0, min(3, llm_result["score"]))
            flags["reason"] = llm_result.get("reason", "")
            flags["sources"] = llm_result.get("themes", [])
            if pts >= 1:
                flags["has_news"] = True
            return pts, flags

        # LLM 없으면 뉴스 존재 여부로 최소 판단
        if news_list:
            flags["has_news"] = True
            flags["sources"] = [n.title for n in news_list[:3]]
            flags["reason"] = news_list[0].title
            return 1, flags

        return 0, flags

    def _score_volume(self, stock: StockData) -> Tuple[int, bool]:
        tv = stock.trading_value
        if tv >= 1_000_000_000_000:  # 1조+
            pts = 3
        elif tv >= 500_000_000_000:  # 5000억+
            pts = 2
        elif tv >= 50_000_000_000:   # 500억+ — 필수통과 하한과 동일 (사각지대 제거)
            pts = 1
        else:
            pts = 0
        sufficient = tv >= 50_000_000_000
        return pts, sufficient

    def _score_chart(
        self, stock: StockData, charts: list
    ) -> tuple[int, dict]:
        flags = {"new_high": False, "breakout": False, "ma_aligned": False, "near_52w_high": False}

        if len(charts) < 20:
            return 0, flags

        pts = 0
        last = charts[-1]

        # 1) 이평선 정배열 (+1)
        if last.ma5 is not None and last.ma10 is not None and last.ma20 is not None:
            if stock.close > last.ma5 > last.ma10 > last.ma20:
                flags["ma_aligned"] = True
                pts += 1

        # 2) 52주 신고가 (저항 → 돌파)
        #    현재가 ≥ 52주 고가 → +2  (고승돌파, 가장 강력한 모멘텀)
        #    현재가 ≥ 52주 고가 95% → +1  (고가 근접)
        if stock.high_52w > 0:
            if stock.close >= stock.high_52w:
                flags["new_high"] = True
                flags["near_52w_high"] = True
                pts += 2
            elif stock.close >= stock.high_52w * 0.95:
                flags["near_52w_high"] = True
                pts += 1
        elif len(charts) >= 60:
            # 52주 데이터 없으면 60일 고가 돌파 (+1)
            high_60d = max(c.high for c in charts[-60:])
            if stock.close > high_60d:
                flags["breakout"] = True
                pts += 1

        return pts, flags

    def _score_candle(
        self, stock: StockData, charts: List[ChartData]
    ) -> Tuple[int, dict]:
        o, h, l, c = stock.open, stock.high, stock.low, stock.close
        flags = {"good": False, "upper_wick_long": False, "body_ratio": 0.0}

        if o == 0 or h == l:
            return 0, flags
        if c <= o:
            return 0, flags

        body = c - o
        total_range = h - l
        body_ratio = body / total_range
        upper_wick = h - c
        upper_wick_ratio = upper_wick / body if body > 0 else 999

        flags["body_ratio"] = round(body_ratio, 4)

        if upper_wick_ratio > 0.5:
            flags["upper_wick_long"] = True

        if (body_ratio >= 0.6 and upper_wick_ratio <= 0.3) or \
           (body_ratio >= 0.5 and upper_wick_ratio <= 0.5):
            flags["good"] = True
            return 1, flags

        return 0, flags

    def _score_supply(self, supply: Optional[SupplyData]) -> Tuple[int, bool]:
        if supply is None:
            return 0, False

        f = supply.foreign_net_5d
        i = supply.inst_net_5d

        if f > 0 and i > 0:
            pts = 2
        elif f > 0 or i > 0:
            pts = 1
        else:
            pts = 0

        return pts, pts >= 1

    def _score_retracement_recovery(
        self, charts: List[ChartData]
    ) -> Tuple[int, bool]:
        if len(charts) < 10:
            return 0, False

        recent = charts[-10:]
        high_idx = max(range(len(recent)), key=lambda i: recent[i].high)

        # 고점 이후 최소 2일은 지나야 함
        if high_idx >= len(recent) - 2:
            return 0, False

        high_val = recent[high_idx].high
        after_high = recent[high_idx + 1:]
        low_after = min(c.low for c in after_high)

        decline = high_val - low_after
        if high_val <= 0 or decline <= 0 or decline / high_val < 0.03:
            return 0, False

        recovery = recent[-1].close - low_after
        if recovery >= decline * 0.5:
            return 1, True

        return 0, False

    def _score_pullback_support(
        self, charts: List[ChartData]
    ) -> Tuple[int, bool]:
        if len(charts) < 25:
            return 0, False

        past_resistance = max(c.high for c in charts[-25:-5])
        recent_5 = charts[-5:]

        # 최근 5일 중 오늘 제외, 종가가 저항선을 넘은 날이 있는지
        breakout = any(c.close > past_resistance for c in recent_5[:-1])
        if not breakout:
            return 0, False

        today = charts[-1]
        if today.low <= past_resistance * 1.02 and today.close > past_resistance:
            return 1, True

        return 0, False

    def _score_consolidation(
        self, charts: List[ChartData]
    ) -> Tuple[int, bool]:
        if len(charts) < 20:
            return 0, False

        recent_20 = charts[-20:]
        recent_5 = charts[-5:]

        high_20 = max(c.high for c in recent_20)
        low_20 = min(c.low for c in recent_20)
        range_20 = (high_20 - low_20) / low_20 if low_20 > 0 else 0

        high_5 = max(c.high for c in recent_5)
        low_5 = min(c.low for c in recent_5)
        range_5 = (high_5 - low_5) / low_5 if low_5 > 0 else 0

        volatility_contracted = range_5 < range_20 * 0.5 if range_20 > 0 else False
        sideways = range_20 <= 0.15
        breakout = charts[-1].close > high_20

        if (sideways or volatility_contracted) and breakout:
            return 1, True

        return 0, False

    def _score_alpha_factors(self, charts: List[ChartData]) -> Tuple[int, dict]:
        """Alpha158 팩터 + ta 라이브러리 기반 보너스 점수 (0~2).

        8개 조건 중 충족 수에 따라 점수 부여 (상한 2점):
        [Alpha158]
          - 변동성 수축:     STD5 < STD20 × 0.7  (VCP 수축)
          - 거래량 돌파:     오늘 거래량 ≥ 20일 평균 × 2.0
          - RSI 강세:       14일 RSI-like > 0.55
          - 가격 위치:      RSV20 > 0.8 (20일 범위 상단 80%)
          - 신고가 근접:    IMAX20 ≤ 2 (최근 2일 내 신고가)
        [ta library]
          - MACD 골든크로스: MACD 선이 Signal 선 상향 돌파 (≥26봉)
          - 볼린저 수축:    BB 밴드폭 < 10% (≥20봉)
          - 스토캐스틱 강세: %K > %D and %K > 50 (≥20봉)

        플래그 전용 (점수 미반영):
          - 모멘텀 가속: ROC5 > ROC20 > 0
        """
        flags = {
            "volatility_squeeze": False,
            "volume_breakout": False,
            "rsi_strong": False,
            "price_near_high": False,
            "near_new_high": False,
            "momentum_accelerating": False,
            "macd_golden_cross": False,
            "bb_squeeze": False,
            "stoch_bullish": False,
        }

        count = 0

        # Alpha158 팩터 (≥20봉)
        f = compute_alpha_factors(charts)
        if f is not None:
            if f.std_ratio < 0.7:
                flags["volatility_squeeze"] = True
                count += 1

            if f.vma20_ratio >= 2.0:
                flags["volume_breakout"] = True
                count += 1

            if f.rsi14 > 0.55:
                flags["rsi_strong"] = True
                count += 1

            if f.rsv20 > 0.8:
                flags["price_near_high"] = True
                count += 1

            if f.imax20 <= 2:
                flags["near_new_high"] = True
                count += 1

            if f.roc5 > 0 and f.roc5 > f.roc20:
                flags["momentum_accelerating"] = True

        # ta 라이브러리 지표 (설치 시 자동 활성, ≥20봉)
        if len(charts) >= 20:
            try:
                import pandas as pd
                import ta as _ta

                closes = pd.Series([c.close for c in charts], dtype=float)
                highs  = pd.Series([c.high  for c in charts], dtype=float)
                lows   = pd.Series([c.low   for c in charts], dtype=float)

                # 볼린저 밴드 수축 (window=20)
                bb = _ta.volatility.BollingerBands(closes, window=20, window_dev=2)
                bb_w = bb.bollinger_wband()
                if pd.notna(bb_w.iloc[-1]) and bb_w.iloc[-1] < 0.1:
                    flags["bb_squeeze"] = True
                    count += 1

                # 스토캐스틱 강세 (window=14)
                stoch = _ta.momentum.StochasticOscillator(
                    highs, lows, closes, window=14, smooth_window=3
                )
                k_line = stoch.stoch()
                d_line = stoch.stoch_signal()
                if (pd.notna(k_line.iloc[-1]) and pd.notna(d_line.iloc[-1]) and
                        k_line.iloc[-1] > d_line.iloc[-1] and k_line.iloc[-1] > 50):
                    flags["stoch_bullish"] = True
                    count += 1

                # MACD 골든크로스 (window_slow=26, ≥26봉)
                if len(charts) >= 26:
                    macd_ind = _ta.trend.MACD(
                        closes, window_slow=26, window_fast=12, window_sign=9
                    )
                    m_line = macd_ind.macd()
                    s_line = macd_ind.macd_signal()
                    if (pd.notna(m_line.iloc[-1]) and pd.notna(m_line.iloc[-2]) and
                            pd.notna(s_line.iloc[-1]) and pd.notna(s_line.iloc[-2]) and
                            m_line.iloc[-1] > s_line.iloc[-1] and
                            m_line.iloc[-2] <= s_line.iloc[-2]):
                        flags["macd_golden_cross"] = True
                        count += 1
            except Exception:
                pass

        return min(2, count), flags

    def _score_vcp_bonus(self, charts: List[ChartData]) -> int:
        """VCP 패턴 보너스 (0~1). VCP score ≥ 60이면 +1점."""
        try:
            import pandas as pd
            from indicators import atr as calc_atr
            from vcp_detector import detect_vcp, score_vcp

            if len(charts) < 30:
                return 0

            df = pd.DataFrame([{
                "date": c.date, "open": float(c.open), "high": float(c.high),
                "low": float(c.low), "close": float(c.close), "volume": float(c.volume),
            } for c in charts])

            result = detect_vcp(df)
            if not result.detected:
                return 0

            atr_series = calc_atr(df)
            last_atr = float(atr_series.iloc[-1])
            last_close = float(df["close"].iloc[-1])
            if last_close <= 0 or (last_atr != last_atr):  # NaN check
                return 0

            atrp = last_atr / last_close * 100
            return 1 if score_vcp(result, atrp) >= 60 else 0
        except Exception:
            return 0

    def determine_grade(self, stock: StockData, score: ScoreDetail) -> Grade:
        if not score.mandatory_passed:
            return Grade.C
        if score.total >= 9:
            return Grade.A
        if score.total >= 7:
            return Grade.B
        return Grade.C

    def calculate_quality(
        self, stock: StockData, charts: List[ChartData], score: ScoreDetail
    ) -> float:
        q = 0.0

        # 1. 수급 (최대 30점)
        if score.supply >= 2:
            q += 30
        elif score.supply == 1:
            q += 15

        # 2. 총점 (최대 25점)
        if score.total >= 10:
            q += 25
        elif score.total >= 9:
            q += 20
        elif score.total >= 8:
            q += 15
        elif score.total >= 7:
            q += 10

        # 3. 당일 상승률 (최대 20점)
        chg = abs(stock.change_pct)
        if chg <= 5:
            q += 20
        elif chg <= 10:
            q += 15
        elif chg <= 15:
            q += 10
        elif chg <= 20:
            q += 5

        # 4. 20일 모멘텀 (최대 15점)
        if len(charts) >= 20:
            price_20ago = charts[-20].close
            if price_20ago > 0:
                m20 = (stock.close - price_20ago) / price_20ago * 100
                if m20 <= 20:
                    q += 15
                elif m20 <= 40:
                    q += 10
                elif m20 <= 60:
                    q += 5

        # 5. 거래량 비율 (최대 10점)
        if len(charts) >= 20:
            vol_20avg = sum(c.volume for c in charts[-20:]) / 20
            if vol_20avg > 0:
                vol_ratio = stock.volume / vol_20avg
                if 4 <= vol_ratio <= 6:
                    q += 10
                elif 2 <= vol_ratio <= 8:
                    q += 5

        return round(q, 1)
