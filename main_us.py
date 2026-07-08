import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from google import genai
from google.genai import types

load_dotenv()

# ---------------------------------------------------------------------------
# 경로 / 설정
# ---------------------------------------------------------------------------

_BASE = Path(__file__).parent
OUTPUT_CSV = _BASE / "gemini_chart_analysis.csv"
CHARTS_DIR = _BASE / "charts"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

# 대상 종목 (S&P 500 주요 종목 등)
STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "BRK-B", "LLY", "AVGO",
    "JPM", "V", "WMT", "UNH", "XOM", "MA", "PG", "JNJ", "HD", "ORCL",
    "CVX", "MRK", "ABBV", "COST", "BAC", "PEP", "CRM", "NFLX", "AMD", "TMO"
]

def _generate_text_data(ticker: str) -> str | None:
    try:
        end = datetime.today()
        start = end - timedelta(days=200) # 120일선 계산을 위한 여유 확보
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty or len(df) < 120:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            try:
                df.columns = df.columns.droplevel("Ticker")
            except KeyError:
                pass

        df.index = pd.DatetimeIndex(df.index)

        # 1. 이동평균선
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA60"] = df["Close"].rolling(60).mean()
        df["MA120"] = df["Close"].rolling(120).mean()

        # 2. RSI (14)
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # 3. 거래량 20일선
        df["Vol20"] = df["Volume"].rolling(20).mean()

        # 4. 볼린저밴드 (20, 2)
        std = df["Close"].rolling(20).std()
        df["BB_upper"] = df["MA20"] + 2 * std
        df["BB_lower"] = df["MA20"] - 2 * std

        # 4. 볼린저밴드 (20, 2)
        std = df["Close"].rolling(20).std()
        df["BB_upper"] = df["MA20"] + 2 * std
        df["BB_lower"] = df["MA20"] - 2 * std

        latest = df.iloc[-1]
        
        # 텍스트 형식으로 변환
        text_data = f"""
Ticker: {ticker}
Date: {df.index[-1].date()}
Current Price: {latest['Close']:.2f}
MA20: {latest['MA20']:.2f}
MA60: {latest['MA60']:.2f}
MA120: {latest['MA120']:.2f}
RSI(14): {latest['RSI']:.2f}
Volume Today: {latest['Volume']}, 20-day Avg Vol: {latest['Vol20']:.0f}
Bollinger Bands(20) Upper: {latest['BB_upper']:.2f}, Lower: {latest['BB_lower']:.2f}

[Recent 5 days trend]
"""
        for i in range(-5, 0):
            row = df.iloc[i]
            date_str = str(df.index[i].date())
            text_data += f"- {date_str}: Close {row['Close']:.2f}, Vol {row['Volume']}\n"
            
        return text_data
    except Exception as exc:
        print(f"[data] {ticker}: {exc}")
        return None

_PROMPT = """\
당신은 25년 경력의 수익률 상위 1% 기술적 분석 전문가입니다.

아래는 {ticker} 미국 주식의 최근 기술적 지표 수치입니다:
---
{text_data}
---

위 수치 데이터를 분석해주세요.
!! 중요: 모든 분석 내용과 'reasons' 항목은 반드시 **한국어(Korean)**로만 작성하세요 !!

다음 항목을 평가하여 JSON을 작성하세요:
1. 이동평균선(20/60/120) 배열 상태 (정배열인지 역배열인지 혼재인지)
2. RSI가 30 이하(과매도) 또는 70 이상(과매수)인지 판단
3. 거래량이 최근 20일 평균 대비 증감했는지
4. 볼린저밴드 상/하단 터치 여부 접근

반드시 아래 JSON 형식으로만 응답하세요. 다른 설명은 추가하지 마세요.
{{
  "signal": "BUY|HOLD|SELL",
  "confidence": 0,
  "reasons": ["한국어 이유1", "한국어 이유2"],
  "ma_status": "정배열|역배열|혼재",
  "rsi_zone": "과매수|과매도|중립",
  "volume_trend": "증가|감소|보합"
}}"""

def _analyze_one(client: genai.Client, ticker: str, text_data: str) -> dict:
    try:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=_PROMPT.format(ticker=ticker, text_data=text_data),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction="당신은 한국 시장 주식 분석가입니다. 출력 언어는 무조건 한국어입니다. reasons와 기타 텍스트를 절대 영어로 출력하지 말고 한국어로만 작성하세요."
            ),
        )
        
        raw_text = resp.text.strip()
        
        # JSON 블록 파싱 처리
        if "```json" in raw_text:
            json_str = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            json_str = raw_text.split("```")[1].strip()
        else:
            json_str = raw_text

        parsed = json.loads(json_str)
        if isinstance(parsed, list):
            parsed = parsed[0]

        reasons = parsed.get("reasons", [])
        return {
            "ticker": ticker,
            "signal": str(parsed.get("signal", "HOLD")).upper(),
            "confidence": float(parsed.get("confidence", 50)),
            "ma_status": str(parsed.get("ma_status", "")),
            "rsi_zone": str(parsed.get("rsi_zone", "")),
            "volume_trend": str(parsed.get("volume_trend", "")),
            "reasons": "; ".join(reasons) if isinstance(reasons, list) else str(reasons),
        }
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"[Gemini Error for {ticker}] {exc}")
        return {
            "ticker": ticker,
            "signal": "ERROR", "confidence": 0.0,
            "ma_status": "", "rsi_zone": "", "volume_trend": "",
            "reasons": str(exc),
        }

def _pipeline():
    # 1. 텍스트 데이터 생성
    print("Extracting technical indicators...")
    ticker_data = {}
    for ticker in STOCKS:
        data_str = _generate_text_data(ticker)
        if data_str:
            ticker_data[ticker] = data_str
            
    # 2. Gemini API 분석 (텍스트 기반)
    print(f"Analyzing {len(ticker_data)} tickers via Gemini...")
    client = genai.Client(api_key=GOOGLE_API_KEY)
    
    results = []
    for ticker, text_data in ticker_data.items():
        print(f"Analyzing {ticker}...")
        results.append(_analyze_one(client, ticker, text_data))
        time.sleep(1.5) # API Rate Limit 보호
        
    # 3. CSV 저장
    df = pd.DataFrame(results)
    if not df.empty and "signal" in df.columns:
        valid = df[df["signal"] != "ERROR"].copy()
        if not valid.empty and "confidence" in valid.columns:
            valid["confidence"] = pd.to_numeric(valid["confidence"], errors="coerce").fillna(0)
            valid = valid.sort_values("confidence", ascending=False).reset_index(drop=True)
        valid.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print("Done! Saved to:", OUTPUT_CSV)
    else:
        print("No valid results to save.")

if __name__ == "__main__":
    _pipeline()
