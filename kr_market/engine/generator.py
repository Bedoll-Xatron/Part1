"""시그널 생성기 — 수집 → LLM 분석 → 스코어링 → 포지션 사이징 → Signal 생성"""

import asyncio
import time
from datetime import date
from typing import List, Optional

from config import SignalConfig
from collectors import get_top_gainers, get_chart_data, get_supply_data, get_stock_news
from llm_analyzer import GeminiAnalyzer
from market_regime import RegimeLevel
from models import Grade, Signal, StockData
from position_sizer import PositionSizer
from scorer import Scorer


class SignalGenerator:
    """매매 시그널 생성기"""

    def __init__(
        self,
        config: SignalConfig = None,
        capital: int = 10_000_000,
        regime_level: RegimeLevel = RegimeLevel.BULL,
        position_scale: float = 1.0,
        allow_grades: list[str] | None = None,
    ):
        self.config = config or SignalConfig()
        self.capital = capital
        self.regime_level = regime_level
        self.position_scale = position_scale
        # allow_grades: None or [] → [”A”, ”B”] 기본
        self.allow_grades = set(allow_grades) if allow_grades else {"A", "B"}
        self.scorer = Scorer(self.config)
        self.position_sizer = PositionSizer(capital, self.config)
        self.llm_analyzer = GeminiAnalyzer()

    async def generate(self, top_n: int = 15) -> List[Signal]:
        """메인 파이프라인: 수집 → 분석 → 필터링 → 정렬"""
        today = date.today()

        print("=" * 60)
        print(f"  시그널 생성 시작 | {today}  [{self.regime_level.value}]")
        print("=" * 60)
        if self.position_scale < 1.0:
            print(f"  ⚠️  시장 국면 {self.regime_level.value}: 포지션 {int(self.position_scale*100)}% 축소 적용")
        print(f"  허용 등급: {self.allow_grades or '없음 (BEAR 차단)'}")

        # 1. KOSPI, KOSDAQ 각각 상승 종목 top_n개 수집
        print("\n[수집] KOSPI 상승 종목...")
        kospi = get_top_gainers("KOSPI", self.config)
        print("[수집] KOSDAQ 상승 종목...")
        kosdaq = get_top_gainers("KOSDAQ", self.config)

        kospi = sorted(kospi, key=lambda x: x.change_pct, reverse=True)[:top_n]
        kosdaq = sorted(kosdaq, key=lambda x: x.change_pct, reverse=True)[:top_n]
        all_stocks = kospi + kosdaq
        total = len(all_stocks)

        print(f"\n  총 분석 대상: {total}개 (KOSPI {len(kospi)} + KOSDAQ {len(kosdaq)})")
        print("-" * 60)

        # 2. 각 종목에 대해 _analyze_stock() 호출
        signals: List[Signal] = []
        for i, stock in enumerate(all_stocks, 1):
            print(f"\n[{i}/{total}] {stock.name}({stock.code}) 분석 중...")
            signal = await self._analyze_stock(stock, today)
            if signal:
                signals.append(signal)

        # 3. C등급 제외 (이미 _analyze_stock에서 None 반환)
        # 4. 등급순 정렬 (A > B), 동일 등급 내 총점 내림차순
        grade_order = {Grade.A: 0, Grade.B: 1}
        signals.sort(key=lambda s: (grade_order.get(s.grade, 99), -s.score.total))

        # 5. 결과 요약
        a_cnt = sum(1 for s in signals if s.grade == Grade.A)
        b_cnt = sum(1 for s in signals if s.grade == Grade.B)

        print(f"\n{'=' * 60}")
        print(f"  시그널 생성 완료: {len(signals)}개 (A: {a_cnt}, B: {b_cnt})")
        print(f"{'=' * 60}")

        for s in signals:
            print(f"  [{s.grade.value}] {s.stock_name:<12} "
                  f"{s.score.total:>2}/15  품질 {s.quality:>5.1f}  "
                  f"{s.quantity}주 {s.position_size:>12,}원"
                  )

        return signals

    async def _analyze_stock(
        self, stock: StockData, target_date: date
    ) -> Optional[Signal]:
        """개별 종목 분석 → Signal 생성"""
        name = stock.name
        code = stock.code

        try:
            # 1. 차트 데이터 60일 수집
            print(f"  차트 수집...")
            charts = get_chart_data(code, days=60)

            # StockData OHLC/52주 보완 (API 원본에 없는 필드)
            if charts:
                latest = charts[-1]
                if stock.open == 0:
                    stock.open = latest.open
                if stock.high == 0:
                    stock.high = latest.high
                if stock.low == 0:
                    stock.low = latest.low
                stock.high_52w = max(c.high for c in charts)
                stock.low_52w = min(c.low for c in charts)

            # 2. 뉴스 3건 수집
            print(f"  뉴스 수집...")
            news_list = get_stock_news(code, name, limit=3)
            news_items = [{"title": n.title, "summary": n.summary} for n in news_list]

            # 3. LLM 뉴스 분석
            print(f"  LLM 분석...")
            llm_result = await self.llm_analyzer.analyze_news(name, news_items)
            llm_score = llm_result.get("score", 0)
            llm_source = llm_result.get("source", "?")
            print(f"  → LLM: {llm_score}/3 ({llm_source})")

            # 4. 수급 데이터 수집
            print(f"  수급 수집...")
            supply = get_supply_data(code)

            # 5. scorer.calculate() → 점수 계산
            score, checklist = self.scorer.calculate(
                stock, charts, news_list, supply, llm_result
            )
            print(f"  점수: {score.total}/15")

            # 6. scorer.determine_grade() → 등급 결정
            grade_raw = self.scorer.determine_grade(stock, score)
            grade = Grade(grade_raw.value)
            print(f"  등급: {grade.value}")

            # 7. 허용 등급 필터 (시장 국면 반영)
            if grade.value not in self.allow_grades:
                print(f"  → 국면({self.regime_level.value}) 허용 등급 외 제외: {grade.value}")
                return None

            # 8. 품질 게이트 3중 필터
            # Gate 1: 수급 점수
            if score.supply < self.config.min_supply_score:
                print(f"  → 수급부족 {name}: supply={score.supply}")
                return None

            # Gate 2: 총점
            if score.total < self.config.min_total_score:
                print(f"  → 점수부족 {name}: total={score.total}")
                return None

            # Gate 3: 품질 점수
            quality = self.scorer.calculate_quality(stock, charts, score)
            print(f"  품질: {quality}")

            if quality < self.config.min_quality:
                print(f"  → 품질부족 {name}: quality={quality}")
                return None

            # 9. position_sizer.calculate() → 포지션 계산  (국면 스케일 적용)
            pos = self.position_sizer.calculate(stock.close, grade)

            # 시장 국면에 따라 포지션 규모 조정
            if self.position_scale != 1.0:
                pos.position_size = round(pos.position_size * self.position_scale)
                pos.quantity      = int(pos.position_size / stock.close) if stock.close > 0 else 0
                pos.position_size = float(pos.quantity * stock.close)
                pos.position_pct  = round(pos.position_size / self.capital * 100, 1) if self.capital > 0 else 0.0

            print(f"  포지션: {pos.quantity}주 / {pos.position_size:,.0f}원 "
                  f"(자본대비 {pos.position_pct}%)")

            # 10. Signal 객체 생성 및 반환
            return Signal(
                stock_code=code,
                stock_name=name,
                market=stock.market,
                signal_date=target_date,
                grade=grade,
                score=score,
                checklist=checklist,
                current_price=stock.close,
                entry_price=pos.entry_price,
                stop_price=pos.stop_price,
                target_price=pos.target_price,
                r_value=pos.r_value,
                position_size=int(pos.position_size),
                quantity=pos.quantity,
                r_multiplier=pos.r_multiplier,
                trading_value=stock.trading_value,
                change_pct=stock.change_pct,
                foreign_5d=supply.foreign_net_5d,
                inst_5d=supply.inst_net_5d,
                quality=quality,
                news_items=news_items,
                themes=llm_result.get("themes", []),
            )

        except Exception as e:
            print(f"  [에러] {name}({code}): {e}")
            return None
