import numpy as np
import pandas as pd
from indicators import fractal_swings

# V자 반복 패턴: 100 → 120 → 105 → 115 → 108 → 113 (60일)
segments = [
    np.linspace(100, 120, 12),  #  0~11: 상승
    np.linspace(120, 105, 12),  # 12~23: 하락
    np.linspace(105, 115, 12),  # 24~35: 상승
    np.linspace(115, 108, 12),  # 36~47: 하락
    np.linspace(108, 113, 12),  # 48~59: 상승
]
close = np.concatenate(segments)

np.random.seed(42)
noise = np.random.uniform(0, 1.5, len(close))
high = close + noise
low = close - noise

df = pd.DataFrame({"high": high, "low": low, "close": close})

swings = fractal_swings(df, k=3)

print(f"감지된 Swing 포인트: {len(swings)}개\n")
for s in swings:
    label = "고점" if s["type"] == "H" else "저점"
    print(f"  {s['type']} {label}: {s['price']:.1f} ({s['i']}일차)")
