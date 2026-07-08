import asyncio
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import yfinance as yf
from flask import Blueprint, jsonify, request, send_file
from google import genai
from google.genai import types

chart_bp = Blueprint("chart_analysis", __name__)

# ---------------------------------------------------------------------------
# 경로 / 설정
# ---------------------------------------------------------------------------

_BASE = Path(__file__).parent.parent.parent          # Part7/
CHARTS_DIR = _BASE / "charts_kr"
OUTPUT_CSV = _BASE / "gemini_chart_analysis_kr.csv"
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-preview")
SEMAPHORE_LIMIT = 10

# ---------------------------------------------------------------------------
# 종목 리스트
# ---------------------------------------------------------------------------

STOCKS: dict[str, str] = {
    "005930.KS": "삼성전자",    "000660.KS": "SK하이닉스",   "373220.KS": "LG에너지솔루션",
    "207940.KS": "삼성바이오로직스", "005380.KS": "현대차",    "000270.KS": "기아",
    "006400.KS": "삼성SDI",     "051910.KS": "LG화학",       "035420.KS": "NAVER",
    "035720.KS": "카카오",      "005490.KS": "POSCO홀딩스",  "055550.KS": "신한지주",
    "105560.KS": "KB금융",      "003670.KS": "포스코퓨처엠", "012330.KS": "현대모비스",
    "066570.KS": "LG전자",      "003550.KS": "LG",           "032830.KS": "삼성생명",
    "086790.KS": "하나금융지주", "034730.KS": "SK",           "015760.KS": "한국전력",
    "096770.KS": "SK이노베이션", "017670.KS": "SK텔레콤",     "030200.KS": "KT",
    "316140.KS": "우리금융지주", "009150.KS": "삼성전기",     "010130.KS": "고려아연",
    "028260.KS": "삼성물산",    "034020.KS": "두산에너빌리티","011200.KS": "HMM",
    "018260.KS": "삼성에스디에스","033780.KS": "KT&G",        "000810.KS": "삼성화재",
    "010950.KS": "S-Oil",       "009540.KS": "HD한국조선해양","267250.KS": "HD현대",
    "003490.KS": "대한항공",    "036570.KS": "엔씨소프트",   "011170.KS": "롯데케미칼",
    "024110.KS": "기업은행",    "000720.KS": "현대건설",     "010140.KS": "삼성중공업",
    "047050.KS": "포스코인터내셔널","009240.KS": "한샘",       "090430.KS": "아모레퍼시픽",
    "051900.KS": "LG생활건강",  "329180.KS": "HD현대중공업", "004020.KS": "현대제철",
    "000100.KS": "유한양행",    "011780.KS": "금호석유",     "016360.KS": "삼성증권",
    "006800.KS": "미래에셋증권","138040.KS": "메리츠금융지주","003410.KS": "쌍용C&E",
    "069500.KS": "KODEX 200",   "352820.KS": "하이브",       "259960.KS": "크래프톤",
    "042660.KS": "한화오션",    "402340.KS": "SK스퀘어",     "361610.KS": "SK아이이테크놀로지",
    "001570.KS": "금양",        "271560.KS": "오리온",       "000080.KS": "하이트진로",
    "002790.KS": "아모레G",     "088350.KS": "한화생명",     "161390.KS": "한국타이어앤테크놀로지",
    "004170.KS": "신세계",      "021240.KS": "코웨이",       "006360.KS": "GS건설",
    "071050.KS": "한국금융지주","139480.KS": "이마트",       "326030.KS": "SK바이오팜",
    "180640.KS": "한진칼",      "032640.KS": "LG유플러스",   "078930.KS": "GS",
    "247540.KQ": "에코프로비엠", "086520.KQ": "에코프로",     "377300.KQ": "카카오페이",
    "263750.KQ": "펄어비스",    "068270.KQ": "셀트리온",     "196170.KQ": "알테오젠",
    "145020.KQ": "휴젤",        "041510.KQ": "에스엠",       "293490.KQ": "카카오게임즈",
    "112040.KQ": "위메이드",    "035900.KQ": "JYP Ent.",     "357780.KQ": "솔브레인",
    "028300.KQ": "에이치엘비",  "095340.KQ": "ISC",          "039030.KQ": "이오테크닉스",
    "058470.KQ": "리노공업",    "005290.KQ": "동진쎄미켐",   "383220.KQ": "F&F",
    "454910.KQ": "에이피알",    "322510.KQ": "제이엘케이",   "236810.KQ": "엔비티",
    "403870.KQ": "HPSP",        "067310.KQ": "하나마이크론", "218410.KQ": "RFHIC",
    "041920.KQ": "메디아나",
}

# ---------------------------------------------------------------------------
# 분석 상태 (스레드 공유)
# ---------------------------------------------------------------------------

_state: dict = {
    "running": False,
    "total": len(STOCKS),
    "current": 0,
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "error": None,
}
_state_lock = threading.Lock()


def _update_state(**kwargs) -> None:
    with _state_lock:
        _state.update(kwargs)


# ---------------------------------------------------------------------------
# 차트 생성
# ---------------------------------------------------------------------------

def _setup_font() -> None:
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            fm.fontManager.addfont(path)
            prop = fm.FontProperties(fname=path)
            plt.rcParams["font.family"] = prop.get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False


def _chart_path(ticker: str, name: str) -> Path:
    safe = name.replace("/", "_").replace(" ", "_")
    return CHARTS_DIR / f"{ticker}_{safe}.png"


def _generate_data_and_chart(ticker: str, name: str) -> tuple[Path | None, str | None]:
    path = _chart_path(ticker, name)
    try:
        end = datetime.today()
        start = end - timedelta(days=200) # 120일선 여유 확보
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty or len(df) < 120:
            return None, None

        if isinstance(df.columns, pd.MultiIndex):
            try:
                df.columns = df.columns.droplevel("Ticker")
            except KeyError:
                df.columns = df.columns.droplevel(1)

        df.index = pd.DatetimeIndex(df.index)

        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA60"] = df["Close"].rolling(60).mean()
        df["MA120"] = df["Close"].rolling(120).mean()

        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        df["Vol20"] = df["Volume"].rolling(20).mean()

        std = df["Close"].rolling(20).std()
        df["BB_upper"] = df["MA20"] + 2 * std
        df["BB_lower"] = df["MA20"] - 2 * std

        latest = df.iloc[-1]
        text_data = f"""
Ticker: {ticker}
Name: {name}
Date: {df.index[-1].date()}
Current Price: {latest['Close']:.0f}
MA20: {latest['MA20']:.0f}
MA60: {latest['MA60']:.0f}
MA120: {latest['MA120']:.0f}
RSI(14): {latest['RSI']:.2f}
Volume Today: {latest['Volume']}, 20-day Avg Vol: {latest['Vol20']:.0f}
Bollinger Bands(20) Upper: {latest['BB_upper']:.0f}, Lower: {latest['BB_lower']:.0f}

[Recent 5 days trend]
"""
        for i in range(-5, 0):
            row = df.iloc[i]
            date_str = str(df.index[i].date())
            text_data += f"- {date_str}: Close {row['Close']:.2f}, Vol {row['Volume']}\n"
        return path, text_data
    except Exception as exc:
        logging.error(f"[_generate_data_and_chart] {ticker}: {exc}")
        return None, None


# ---------------------------------------------------------------------------
# Gemini 분석
# ---------------------------------------------------------------------------

_PROMPT = """\
당신은 25년 경력의 대한민국 수익률 상위 1% 기술적 분석 전문가입니다.

아래는 {name}({ticker}) 한국 주식 차트의 최근 기술적 지표 수치입니다:
---
{text_data}
---

위 수치 데이터를 전문적으로 분석해주세요.
!! 중요: 모든 분석 내용과 'reasons' 항목은 반드시 **한국어(Korean)**로만 작성하세요 !!

다음 항목을 평가하여 엄격하게 JSON을 작성하세요:
1. 이동평균선(20/60/120) 배열 상태 (정배열인지 역배열인지 혼재인지)
2. RSI가 30 이하(과매도) 또는 70 이상(과매수)인지
3. 거래량이 최근 20일 평균 대비 증감했는지
4. 볼린저밴드 상/하단 터치 여부 접근

반드시 아래 JSON 형식으로만 응답하세요. 다른 설명은 추가하지 마세요:
{{
  "signal": "BUY|HOLD|SELL",
  "confidence": 0,
  "reasons": ["한국어 이유1", "한국어 이유2"],
  "ma_status": "정배열|역배열|혼재",
  "rsi_zone": "과매수|과매도|중립",
  "volume_trend": "증가|감소|보합"
}}"""


def _analyze_one(client: genai.Client, ticker: str, name: str, text_data: str) -> dict:
    try:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=_PROMPT.format(name=name, ticker=ticker, text_data=text_data),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction="당신은 한국 주식 분석가입니다. 출력 언어는 무조건 '한국어'만 허용됩니다. reasons와 기타 텍스트를 절대 영어로 쓰지 말고 반드시 한국어로만 작성하세요."
            ),
        )
        
        raw_text = resp.text.strip()
        
        # JSON 파싱
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
            "종목코드": ticker,
            "종목명": name,
            "시장": "코스피" if ticker.endswith(".KS") else "코스닥",
            "signal": str(parsed.get("signal", "HOLD")).upper(),
            "confidence": float(parsed.get("confidence", 50)),
            "ma_status": str(parsed.get("ma_status", "")),
            "rsi_zone": str(parsed.get("rsi_zone", "")),
            "volume_trend": str(parsed.get("volume_trend", "")),
            "reasons": "; ".join(reasons) if isinstance(reasons, list) else str(reasons),
        }
    except Exception as exc:
        return {
            "종목코드": ticker, "종목명": name,
            "시장": "코스피" if ticker.endswith(".KS") else "코스닥",
            "signal": "ERROR", "confidence": 0.0,
            "ma_status": "", "rsi_zone": "", "volume_trend": "",
            "reasons": str(exc),
        }


async def _run_analysis(chart_data: dict[str, str]) -> list[dict]:
    client = genai.Client(api_key=GOOGLE_API_KEY)
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    executor = ThreadPoolExecutor(max_workers=SEMAPHORE_LIMIT)
    loop = asyncio.get_event_loop()
    results: list[dict] = []

    async def do_one(ticker: str, text_data: str) -> dict:
        async with semaphore:
            result = await loop.run_in_executor(
                executor, _analyze_one, client, ticker, STOCKS[ticker], text_data
            )
            _update_state(current=_state["current"] + 1)
            return result

    tasks = [do_one(t, txt) for t, txt in chart_data.items()]
    results = list(await asyncio.gather(*tasks))
    executor.shutdown(wait=False)
    return results


def _pipeline() -> None:
    """백그라운드 스레드에서 전체 파이프라인 실행."""
    try:
        _setup_font()
        CHARTS_DIR.mkdir(exist_ok=True)

        # Step 1: 차트 및 데이터 생성
        chart_data: dict[str, str] = {}
        for ticker, name in STOCKS.items():
            path, text_data = _generate_data_and_chart(ticker, name)
            if path and text_data:
                chart_data[ticker] = text_data
            _update_state(current=_state["current"] + 1)

        # Step 2: Gemini 분석 (current를 0으로 리셋)
        _update_state(current=0, total=len(chart_data))
        results = asyncio.run(_run_analysis(chart_data))

        # Step 3: CSV 저장
        df = pd.DataFrame(results)
        valid = df[df["signal"] != "ERROR"].copy()
        valid["confidence"] = pd.to_numeric(valid["confidence"], errors="coerce").fillna(0)
        valid = valid.sort_values("confidence", ascending=False).reset_index(drop=True)
        valid.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

        _update_state(
            running=False,
            status="done",
            finished_at=datetime.now().isoformat(),
        )
    except Exception as exc:
        logging.error(f"[pipeline] 오류: {exc}")
        _update_state(running=False, status="error", error=str(exc))


# ---------------------------------------------------------------------------
# 스케줄러
# ---------------------------------------------------------------------------

_KST = timezone(timedelta(hours=9))
_SCHEDULE_HOUR = 17
_SCHEDULE_MIN  = 5
_STALE_HOURS   = 23


def _trigger_pipeline() -> bool:
    """실행 중이 아닐 때만 파이프라인을 시작. 시작하면 True 반환."""
    with _state_lock:
        if _state["running"]:
            return False
    _update_state(
        running=True,
        status="running",
        total=len(STOCKS),
        current=0,
        started_at=datetime.now().isoformat(),
        finished_at=None,
        error=None,
    )
    threading.Thread(target=_pipeline, daemon=True).start()
    return True


def _auto_scheduler() -> None:
    """
    앱 시작 시 결과가 없거나 _STALE_HOURS 이상 오래됐으면 즉시 실행.
    이후 매일 _SCHEDULE_HOUR:_SCHEDULE_MIN KST 에 자동 재실행.
    """
    # 시작 시 판단
    needs_run = (
        not OUTPUT_CSV.exists()
        or (time.time() - OUTPUT_CSV.stat().st_mtime) > _STALE_HOURS * 3600
    )
    if needs_run:
        logging.info("[scheduler] 결과 없음/오래됨 → 즉시 분석 시작")
        _trigger_pipeline()

    # 매일 지정 시각 루프
    while True:
        now = datetime.now(_KST)
        next_run = now.replace(
            hour=_SCHEDULE_HOUR, minute=_SCHEDULE_MIN, second=0, microsecond=0
        )
        if now >= next_run:
            next_run += timedelta(days=1)
        sleep_sec = (next_run - now).total_seconds()
        logging.info(f"[scheduler] 다음 자동 분석: {next_run.strftime('%Y-%m-%d %H:%M KST')} (대기 {sleep_sec/3600:.1f}h)")
        time.sleep(sleep_sec)

        logging.info("[scheduler] 자동 분석 시작")
        _trigger_pipeline()


def start_scheduler() -> None:
    """Flask app factory에서 호출. 중복 실행 방지."""
    threading.Thread(target=_auto_scheduler, daemon=True, name="chart-scheduler").start()


# ---------------------------------------------------------------------------
# Flask 엔드포인트
# ---------------------------------------------------------------------------

@chart_bp.post("/run")
def run_analysis():
    if not _trigger_pipeline():
        return jsonify({"ok": False, "message": "이미 분석 중입니다."}), 409
    return jsonify({"ok": True, "message": "분석을 시작했습니다."})


@chart_bp.get("/status")
def get_status():
    with _state_lock:
        snap = dict(_state)
    pct = round(snap["current"] / snap["total"] * 100) if snap["total"] else 0
    return jsonify({**snap, "pct": pct})


@chart_bp.get("/results")
def get_results():
    if not OUTPUT_CSV.exists():
        return jsonify({"results": [], "summary": {"BUY": 0, "HOLD": 0, "SELL": 0}})

    df = pd.read_csv(OUTPUT_CSV, encoding="utf-8-sig")
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0)
    df = df.sort_values("confidence", ascending=False)

    summary = df["signal"].value_counts().to_dict()
    records = df.to_dict(orient="records")
    return jsonify({"results": records, "summary": summary})


@chart_bp.get("/charts/<path:ticker>")
def get_chart(ticker: str):
    name = STOCKS.get(ticker, "")
    if name:
        path = _chart_path(ticker, name)
        if path.exists():
            return send_file(str(path), mimetype="image/png")

    # 티커로 파일 검색 (폴백)
    if CHARTS_DIR.exists():
        safe_ticker = ticker.replace(".", "_").replace("/", "_")
        for f in CHARTS_DIR.glob(f"{ticker}_*.png"):
            return send_file(str(f), mimetype="image/png")

    return jsonify({"error": "차트를 찾을 수 없습니다."}), 404
