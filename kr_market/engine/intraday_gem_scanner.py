"""
intraday_gem_scanner.py
========================
장중 원석(Gem Hunter) 발굴 스캐너.

[개선] 네이버 금융 거래량 상위 종목 스크래핑 -> 빠른 스캔 (5분 내 완료)

조건:
  - 전일 대비 상승 (양봉)
  - 현재가 > 20일선 & 60일선 (정배열 초입)
  - 거래량 20일 평균의 1.5배 이상
  - 당일 등락률 15% 미만 (상한가 제외)
"""

import os
import sys
import json
import time
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import FinanceDataReader as fdr

# Windows CP949 콘솔 인코딩 문제 방지
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

log = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, 'intraday_gems.json')

_NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _parse_num(text: str, is_float=False):
    """콤마, +, %, 공백 제거 후 숫자 변환"""
    try:
        cleaned = text.strip().replace(",", "").replace("+", "").replace("%", "")
        return float(cleaned) if is_float else int(cleaned)
    except Exception:
        return 0.0 if is_float else 0


def _fetch_naver_volume_top(limit: int = 150) -> list:
    """
    네이버 금융 거래량 상위 종목을 가져온다. (KOSPI + KOSDAQ)
    컬럼: [순위, 종목명, 현재가, 전일비, 등락률, 거래대금, 거래량, ...]
    반환: [{"code", "name", "price", "change_pct", "volume"}, ...]
    """
    results = []

    for sosok in ("0", "1"):  # 0=KOSPI, 1=KOSDAQ
        url = f"https://finance.naver.com/sise/sise_quant.naver?sosok={sosok}"
        try:
            resp = requests.get(url, headers=_NAVER_HEADERS, timeout=10)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", class_="type_2")
            if not table:
                continue

            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 8:
                    continue
                a_tag = tds[1].find("a")
                if not a_tag:
                    continue
                href = a_tag.get("href", "")
                code = href.split("code=")[-1].strip() if "code=" in href else ""
                if not code:
                    continue
                name = a_tag.get_text(strip=True)

                price = _parse_num(tds[2].get_text())
                # tds[4] = 등락률 (예: "-0.93%", "+3.50%")
                change_pct = _parse_num(tds[4].get_text(), is_float=True)
                # tds[5] = 거래량, tds[6] = 거래대금(억)
                volume = _parse_num(tds[5].get_text())

                if price <= 0:
                    continue

                results.append({
                    "code": code,
                    "name": name,
                    "price": price,
                    "change_pct": change_pct,
                    "volume": volume,
                })

        except Exception as e:
            log.warning(f"[gem-scanner] 네이버 거래량 조회 실패 (sosok={sosok}): {e}")

    # 거래량 기준 내림차순 정렬 후 limit 적용
    results.sort(key=lambda x: x["volume"], reverse=True)
    return results[:limit]


def _get_ma_and_vol_ma(ticker: str):
    """
    FDR로 해당 종목의 일봉 데이터를 가져와 MA20, MA60, VolMA20을 계산.
    반환: (ma20, ma60, vol_ma20) 또는 실패 시 (None, None, None)
    """
    try:
        df = fdr.DataReader(ticker, '2023-01-01')
        if len(df) < 65:
            return None, None, None
        ma20 = float(df['Close'].rolling(20).mean().iloc[-1])
        ma60 = float(df['Close'].rolling(60).mean().iloc[-1])
        vol_ma20 = float(df['Volume'].rolling(20).mean().iloc[-1])
        return ma20, ma60, vol_ma20
    except Exception:
        return None, None, None


def run_intraday_scanner():
    start_time = time.time()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now_str}] 장중 원석(Gem Hunter) 발굴 스캐너 시작...")

    # 1. 네이버 거래량 상위 종목 수집
    print("거래량 상위 종목 로딩 중 (네이버)...")
    candidates = _fetch_naver_volume_top(limit=150)
    print(f"  -> {len(candidates)}개 후보 종목 확보")

    # 2. 사전 필터: 상승 중 + 등락률 0~15% 이내
    pre_filtered = [c for c in candidates if 0 < c["change_pct"] < 15]
    print(f"  -> 사전 필터 후 {len(pre_filtered)}개 (양봉 + 15% 미만)")

    gems = []
    for i, c in enumerate(pre_filtered, 1):
        ticker = c["code"]
        name = c["name"]
        price = c["price"]
        change_pct = c["change_pct"]
        volume = c["volume"]

        if i % 10 == 0:
            print(f"  진행 중... [{i}/{len(pre_filtered)}]")

        ma20, ma60, vol_ma20 = _get_ma_and_vol_ma(ticker)
        if ma20 is None or vol_ma20 is None or vol_ma20 == 0:
            continue

        # 조건: 정배열 초입(MA20 위) + 거래량 평균 이상 (1.0배)
        # volume_ratio로 품질 구분 (1.5배 이상이 최상급)
        if price > ma20 and volume > vol_ma20 * 1.5:
            volume_ratio = round(volume / vol_ma20, 1)
            above_ma60 = price > ma60
            gems.append({
                "ticker": ticker,
                "name": name,
                "price": float(price),
                "change_pct": round(change_pct, 2),
                "volume_ratio": volume_ratio,
                "above_ma60": above_ma60,
                "scan_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            })
            flag = "[MA60+]" if above_ma60 else ""
            print(f"  [GEM] {name}({ticker}) : +{change_pct:.1f}% / 거래량 {volume_ratio:.1f}배 {flag}")

    # 결과 저장
    result_data = {
        "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "count": len(gems),
        "gems": sorted(gems, key=lambda x: x['volume_ratio'], reverse=True),
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    print(f"\n[완료] 장중 스캔 완료! 총 {len(gems)}개 원석 발굴 ({elapsed:.1f}초 소요)")
    print(f"결과 저장: {OUTPUT_FILE}\n")
    log.info(f"[gem-scanner] 완료: {len(gems)}개 원석 ({elapsed:.1f}초)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_intraday_scanner()
