from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional

from config import Grade, SignalConfig


@dataclass
class StockData:
    code: str
    name: str
    market: str
    open: int
    high: int
    low: int
    close: int
    volume: int
    trading_value: int
    change_pct: float
    high_52w: int
    low_52w: int


@dataclass
class SupplyData:
    code: str
    foreign_net_5d: int
    inst_net_5d: int
    foreign_hold_pct: float


@dataclass
class ChartData:
    code: str
    date: date
    open: int
    high: int
    low: int
    close: int
    volume: int
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None


@dataclass
class ScoreDetail:
    news: int = 0             # 뉴스/재료 0~3점
    volume: int = 0           # 거래대금 0~3점
    chart: int = 0            # 차트패턴 0~3점
    candle: int = 0           # 캔들형태 0~1점
    consolidation: int = 0    # 기간조정 0~1점
    supply: int = 0           # 수급 0~2점
    retracement: int = 0      # 조정폭 회복 0~1점
    pullback_support: int = 0 # 되돌림 지지 0~1점
    alpha_score: int = 0      # Alpha158 팩터 보너스 0~2점
    vcp_bonus: int = 0        # VCP 패턴 보너스 0~1점
    squeeze_bonus: int = 0    # Short Squeeze 보너스 0~2점
    timing_score: int = 0     # Stage 2 타이밍 점수 0~10점 (진입 타이밍 전용)
    llm_reason: str = ""      # LLM 분석 이유

    @property
    def total(self) -> int:
        return (
            self.news + self.volume + self.chart + self.candle +
            self.consolidation + self.supply + self.retracement +
            self.pullback_support + self.alpha_score + self.vcp_bonus
        )

    @property
    def mandatory_passed(self) -> bool:
        return self.news >= 1 and self.volume >= 1

    def to_dict(self) -> dict:
        return {
            "news": self.news,
            "volume": self.volume,
            "chart": self.chart,
            "candle": self.candle,
            "consolidation": self.consolidation,
            "supply": self.supply,
            "retracement": self.retracement,
            "pullback_support": self.pullback_support,
            "alpha_score": self.alpha_score,
            "vcp_bonus": self.vcp_bonus,
            "squeeze_bonus": self.squeeze_bonus,
            "timing_score": self.timing_score,
            "llm_reason": self.llm_reason,
            "total": self.total,
        }


@dataclass
class ChecklistDetail:
    """체크리스트 상세 — 필수/보조/부정적 조건"""

    # 필수 조건
    has_news: bool = False
    news_sources: List[str] = field(default_factory=list)
    volume_sufficient: bool = False

    # 보조 조건
    is_new_high: bool = False               # 52주 신고가
    is_breakout: bool = False               # 돌파
    ma_aligned: bool = False                # 이평선 정배열
    good_candle: bool = False               # 좋은 캔들
    upper_wick_long: bool = False           # 윗꼬리 김
    has_consolidation: bool = False         # 기간조정
    supply_positive: bool = False           # 수급 양호
    retracement_recovery: bool = False
    pullback_support_confirmed: bool = False

    # Alpha158 팩터
    volatility_squeeze: bool = False     # 5일 변동성 < 20일의 70% (VCP 수축)
    volume_breakout: bool = False        # 오늘 거래량 ≥ 20일 평균의 2배
    rsi_strong: bool = False             # RSI-like > 0.55 (매수세 우위)
    price_near_high: bool = False        # RSV20 > 0.8 (20일 범위 상단 80%)
    near_new_high: bool = False          # IMAX20 ≤ 2 (최근 2일 내 신고가)
    momentum_accelerating: bool = False  # ROC5 > ROC20 > 0 (모멘텀 가속)
    vcp_detected: bool = False           # VCP 패턴 감지 (score ≥ 60)

    # ta 라이브러리 지표
    macd_golden_cross: bool = False      # MACD 선이 Signal 선 상향 돌파
    bb_squeeze: bool = False             # 볼린저 밴드폭 수축 (wband < 10%)
    stoch_bullish: bool = False          # 스토캐스틱 %K > %D and %K > 50

    # 부정적
    negative_news: bool = False

    def to_dict(self) -> Dict[str, dict]:
        return {
            "mandatory": {
                "has_news": self.has_news,
                "news_sources": self.news_sources,
                "volume_sufficient": self.volume_sufficient,
            },
            "optional": {
                "is_new_high": self.is_new_high,
                "is_breakout": self.is_breakout,
                "ma_aligned": self.ma_aligned,
                "good_candle": self.good_candle,
                "upper_wick_long": self.upper_wick_long,
                "has_consolidation": self.has_consolidation,
                "supply_positive": self.supply_positive,
                "retracement_recovery": self.retracement_recovery,
                "pullback_support_confirmed": self.pullback_support_confirmed,
                "volatility_squeeze": self.volatility_squeeze,
                "volume_breakout": self.volume_breakout,
                "rsi_strong": self.rsi_strong,
                "price_near_high": self.price_near_high,
                "near_new_high": self.near_new_high,
                "momentum_accelerating": self.momentum_accelerating,
                "vcp_detected": self.vcp_detected,
                "macd_golden_cross": self.macd_golden_cross,
                "bb_squeeze": self.bb_squeeze,
                "stoch_bullish": self.stoch_bullish,
            },
            "negative": {
                "negative_news": self.negative_news,
            },
        }


@dataclass
class NewsData:
    code: str
    title: str
    source: str
    published_at: datetime
    url: Optional[str] = None
    summary: str = ""


@dataclass
class Signal:
    """매매 시그널"""

    # 종목 정보
    stock_code: str
    stock_name: str
    market: str

    # 시그널
    signal_date: date
    grade: Grade

    # 점수
    score: ScoreDetail
    checklist: ChecklistDetail

    # 가격
    current_price: int
    entry_price: int
    stop_price: int
    target_price: int

    # 포지션
    r_value: float
    position_size: int
    quantity: int
    r_multiplier: float = 0.0

    # 시장 데이터
    trading_value: int = 0
    change_pct: float = 0.0
    foreign_5d: int = 0
    inst_5d: int = 0

    # 품질
    quality: float = 0.0

    # 뉴스
    news_items: List[Dict] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "market": self.market,
            "signal_date": self.signal_date.isoformat(),
            "grade": self.grade.value,
            "score": self.score.to_dict(),
            "checklist": self.checklist.to_dict(),
            "current_price": self.current_price,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "r_value": self.r_value,
            "position_size": self.position_size,
            "quantity": self.quantity,
            "r_multiplier": self.r_multiplier,
            "trading_value": self.trading_value,
            "change_pct": self.change_pct,
            "foreign_5d": self.foreign_5d,
            "inst_5d": self.inst_5d,
            "quality": self.quality,
            "news_items": self.news_items,
            "themes": self.themes,
        }


@dataclass
class ScreenerResult:
    """스크리너 결과"""
    date: date
    total_candidates: int              # 전체 후보 수
    filtered_count: int                # 필터 통과 수
    signals: List[Signal] = field(default_factory=list)
    by_grade: Dict[str, int] = field(default_factory=dict)   # 등급별 개수
    by_market: Dict[str, int] = field(default_factory=dict)  # 시장별 개수
    processing_time_ms: float = 0.0    # 소요 시간 (ms)

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "total_candidates": self.total_candidates,
            "filtered_count": self.filtered_count,
            "signals": [s.to_dict() for s in self.signals],
            "by_grade": self.by_grade,
            "by_market": self.by_market,
            "processing_time_ms": self.processing_time_ms,
        }
