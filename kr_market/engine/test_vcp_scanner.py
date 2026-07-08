import numpy as np
import pandas as pd
from vcp_detector import detect_vcp, score_vcp
from indicators import atr


def make_df(close_arr, seed=42):
    """종가 배열로 OHLC DataFrame 생성."""
    np.random.seed(seed)
    noise = np.random.uniform(0, 1.0, len(close_arr))
    return pd.DataFrame({
        "open": close_arr + noise * 0.3,
        "high": close_arr + noise,
        "low": close_arr - noise,
        "close": close_arr,
    })


def print_result(label, result, df, supply=None):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  감지: {result.detected}")

    if result.detected:
        atr_series = atr(df, period=14)
        atrp = (atr_series.iloc[-1] / df["close"].iloc[-1]) * 100
        score = score_vcp(result, atrp)
        result.score = score

        print(f"  등급: {result.grade}")
        print(f"  수축률: C1={result.c1}% → C2={result.c2}% → C3={result.c3}%")
        print(f"  비율: r12={result.r12}  r23={result.r23}")
        print(f"  피봇 고점: {result.pivot_high:.1f}")
        print(f"  ATR%: {atrp:.2f}%")
        print(f"  점수: {score}/100")

    if supply:
        print(f"  외인 5일: {supply['foreign_5d']:+,}")
        print(f"  기관 5일: {supply['inst_5d']:+,}")
        verdict = "양호" if supply["foreign_5d"] > 0 or supply["inst_5d"] > 0 else "불량"
        print(f"  수급 판정: {verdict}")
    print()


# ── 케이스 1: VCP 완벽 종목 ──
# H1=120 L1=90 → C1=25%
# H2=115 L2=97.75 → C2=15%
# H3=112 L3=104.16 → C3=7%
case1 = np.concatenate([
    np.linspace(80, 120, 10),    # 상승 (트렌드 확립)
    np.linspace(120, 90, 10),    # 하락 (L1)
    np.linspace(90, 115, 10),    # 상승 (H2)
    np.linspace(115, 98, 10),    # 하락 (L2)
    np.linspace(98, 112, 10),    # 상승 (H3)
    np.linspace(112, 104, 10),   # 소폭 하락 (L3)
    np.linspace(104, 110, 10),   # 수렴 횡보
    np.linspace(110, 111, 10),   # 피봇 근처 대기
])
df1 = make_df(case1, seed=42)
supply1 = {"foreign_5d": 150_000, "inst_5d": 80_000}

result1 = detect_vcp(df1)
print_result("케이스 1: VCP 완벽 종목 (수축 25→15→7%, 수급 양호)", result1, df1, supply1)


# ── 케이스 2: VCP 없는 종목 (계속 하락) ──
case2 = np.concatenate([
    np.linspace(120, 110, 20),
    np.linspace(110, 95, 20),
    np.linspace(95, 80, 20),
    np.linspace(80, 70, 20),
])
df2 = make_df(case2, seed=99)

result2 = detect_vcp(df2)
print_result("케이스 2: VCP 없는 종목 (지속 하락)", result2, df2)


# ── 케이스 3: VCP는 있지만 수급 나쁜 종목 ──
# 케이스 1과 동일한 가격 패턴, 수급만 다름
case3 = case1.copy()
df3 = make_df(case3, seed=42)
supply3 = {"foreign_5d": -200_000, "inst_5d": -50_000}

result3 = detect_vcp(df3)
print_result("케이스 3: VCP 감지 but 수급 불량 (외인/기관 순매도)", result3, df3, supply3)


# ── 비교 요약 ──
print(f"{'='*60}")
print(f"  비교 요약")
print(f"{'='*60}")
print(f"  {'케이스':<40} {'감지':>4} {'등급':>4} {'점수':>4} {'수급':>6}")
print(f"  {'-'*58}")

rows = [
    ("1. 완벽 VCP + 수급 양호", result1, supply1),
    ("2. 지속 하락 (VCP 없음)", result2, None),
    ("3. VCP 감지 + 수급 불량", result3, supply3),
]
for label, r, sup in rows:
    detected = "O" if r.detected else "X"
    grade = r.grade if r.detected else "-"
    score = str(r.score) if r.detected else "-"
    if sup:
        supply_label = "양호" if sup["foreign_5d"] > 0 or sup["inst_5d"] > 0 else "불량"
    else:
        supply_label = "-"
    print(f"  {label:<40} {detected:>4} {grade:>4} {score:>4} {supply_label:>6}")

print(f"\n  결론: VCP 패턴 + 수급 양호 = 케이스 1만 실전 매수 대상")
print(f"{'='*60}\n")
