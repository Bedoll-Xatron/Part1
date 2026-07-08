import numpy as np
import pandas as pd
from typing import Optional
from vcp_detector import detect_vcp, score_vcp
from indicators import atr


def print_result(label: str, result, atrp: Optional[float] = None):
    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"{'='*50}")
    print(f"  감지: {result.detected}")
    if result.detected:
        print(f"  등급: {result.grade}")
        print(f"  피봇 고점: {result.pivot_high:.1f}")
        print(f"  수축률: C1={result.c1}%  C2={result.c2}%  C3={result.c3}%")
        print(f"  비율:  r12={result.r12}  r23={result.r23}")
        print(f"  L3 프록시: {result.l3_proxy}")
        if atrp is not None:
            score = score_vcp(result, atrp)
            result.score = score
            print(f"  ATR%: {atrp:.2f}%")
            print(f"  점수: {score}/100")
    print()


# ── 테스트 1: 수축 패턴 (VCP 감지 기대) ──
# 80 → 100 (트렌드 확립) → 120 → 105 → 115 → 108 → 113 → 110 → 112
# H1=120, H2=115, H3=113 (고점 하강, 수축률 감소)
segments_vcp = [
    np.linspace(80, 100, 10),   #  0~9:  트렌드 확립 상승
    np.linspace(100, 120, 10),  # 10~19: 상승 (H1)
    np.linspace(120, 105, 10),  # 20~29: 하락 (L1)
    np.linspace(105, 115, 10),  # 30~39: 상승 (H2)
    np.linspace(115, 108, 10),  # 40~49: 하락 (L2)
    np.linspace(108, 113, 10),  # 50~59: 상승 (H3)
    np.linspace(113, 110, 10),  # 60~69: 소폭 하락 (L3)
    np.linspace(110, 112, 10),  # 70~79: 소폭 상승
]
close_vcp = np.concatenate(segments_vcp)

np.random.seed(42)
noise = np.random.uniform(0, 1.5, len(close_vcp))
df_vcp = pd.DataFrame({
    "high": close_vcp + noise,
    "low": close_vcp - noise,
    "close": close_vcp,
})

result_vcp = detect_vcp(df_vcp)
atr_series = atr(df_vcp, period=14)
atrp_val = (atr_series.iloc[-1] / df_vcp["close"].iloc[-1]) * 100
print_result("테스트 1: 수축 패턴 (VCP 감지 기대)", result_vcp, atrp_val)


# ── 테스트 2: 수축 없는 패턴 (계속 하락 → 미감지 기대) ──
close_down = np.linspace(120, 80, 60)
np.random.seed(99)
noise2 = np.random.uniform(0, 1.0, 60)
df_down = pd.DataFrame({
    "high": close_down + noise2,
    "low": close_down - noise2,
    "close": close_down,
})

result_down = detect_vcp(df_down)
print_result("테스트 2: 계속 하락 패턴 (미감지 기대)", result_down)
