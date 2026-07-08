import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def fractal_swings(df: pd.DataFrame, k: int = 3) -> list[dict]:
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    raw: list[dict] = []

    for i in range(k, n - k):
        if all(highs[i] > highs[i - j] and highs[i] > highs[i + j] for j in range(1, k + 1)):
            raw.append({"i": i, "type": "H", "price": float(highs[i])})
        if all(lows[i] < lows[i - j] and lows[i] < lows[i + j] for j in range(1, k + 1)):
            raw.append({"i": i, "type": "L", "price": float(lows[i])})

    raw.sort(key=lambda x: x["i"])

    # 연속 같은 타입 → 더 극단적인 것만 남기기
    result: list[dict] = []
    for swing in raw:
        if result and result[-1]["type"] == swing["type"]:
            prev = result[-1]
            if swing["type"] == "H" and swing["price"] > prev["price"]:
                result[-1] = swing
            elif swing["type"] == "L" and swing["price"] < prev["price"]:
                result[-1] = swing
        else:
            result.append(swing)

    return result
