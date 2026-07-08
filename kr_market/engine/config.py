from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple


class Grade(Enum):
    A = "A"
    B = "B"
    C = "C"


@dataclass
class GradeConfig:
    """등급별 포지션 사이징 설정"""
    r_multiplier: float    # R배수 (0이면 매매 안 함)


@dataclass
class SignalConfig:
    # 필터링 조건
    min_trading_value: int = 50_000_000_000   # 거래대금 최소 500억
    min_change_pct: float = 5.0               # 최소 등락률 %
    max_change_pct: float = 20.0              # 최대 등락률 %
    min_price: int = 1_000                    # 최소 주가
    max_price: int = 500_000                  # 최대 주가

    # 품질 게이트
    min_supply_score: int = 2            # 수급 최소 점수
    min_total_score: int = 8             # 총점 최소 점수
    min_quality: float = 55.0            # 품질 최소 점수

    # 포지션 사이징
    r_ratio: float = 0.005               # 자본 대비 기본 R 비율 (0.5%)
    stop_loss_pct: float = 0.05          # 손절 비율 (5%)
    take_profit_pct: float = 0.15        # 익절 비율 (15%)
    max_position_pct: float = 0.50       # 최대 포지션 비율 (50%)

    # 등급별 설정
    grade_configs: Dict[Grade, GradeConfig] = field(default_factory=lambda: {
        Grade.A: GradeConfig(r_multiplier=2.0),
        Grade.B: GradeConfig(r_multiplier=1.0),
        Grade.C: GradeConfig(r_multiplier=0.0),
    })

    # 제외 조건
    exclude_etf: bool = True
    exclude_spac: bool = True
    exclude_preferred: bool = True

    # 지원 후 패턴
    exclude_keywords: list[str] = field(default_factory=lambda: [
        "스팩", "SPAC", "ETF", "ETN", "리츠", "우B", "우C",
        "1우", "2우", "3우", "인버스", "레버리지",
    ])

    # 포트폴리오 제어
    max_same_sector_positions: int = 2   # 동일 섹터 최대 진입 종목 수
    max_total_positions: int = 6         # 전체 동시 보유 최대 종목 수


@dataclass
class VCPGradeParams:
    min_r12: float                    # 수축비율 C1/C2 최소값
    min_r23: float                    # 수축비율 C2/C3 최소값
    require_descending_highs: bool    # 고점 하강 필수 여부
    require_ascending_lows: bool      # 저점 상승 필수 여부
    trend_mode: str                   # "STRICT", "ABOVE_MA20", "ABOVE_MA60", "ANY"


@dataclass
class VCPConfig:
    swing_k: int = 3
    lookback: int = 60

    # 등급별 파라미터
    grade_a: VCPGradeParams = field(default_factory=lambda: VCPGradeParams(
        min_r12=1.20, min_r23=1.15,
        require_descending_highs=True, require_ascending_lows=True,
        trend_mode="STRICT",
    ))
    grade_b: VCPGradeParams = field(default_factory=lambda: VCPGradeParams(
        min_r12=1.12, min_r23=1.08,
        require_descending_highs=False, require_ascending_lows=False,
        trend_mode="ABOVE_MA20",
    ))
    grade_c: VCPGradeParams = field(default_factory=lambda: VCPGradeParams(
        min_r12=1.05, min_r23=1.02,
        require_descending_highs=False, require_ascending_lows=False,
        trend_mode="ABOVE_MA60",
    ))
    grade_d: VCPGradeParams = field(default_factory=lambda: VCPGradeParams(
        min_r12=1.02, min_r23=1.01,
        require_descending_highs=False, require_ascending_lows=False,
        trend_mode="ANY",
    ))

    # 스코어링 바운드
    c3_lo: float = 1.0
    c3_hi: float = 12.0
    atrp_lo: float = 0.5
    atrp_hi: float = 5.0

    def all_grades(self) -> List[Tuple[VCPGradeParams, str]]:
        return [
            (self.grade_a, "A"),
            (self.grade_b, "B"),
            (self.grade_c, "C"),
            (self.grade_d, "D"),
        ]
