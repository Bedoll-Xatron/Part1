"""vcp_signals.json의 각 시그널에 성과 추적 필드(status, return_pct, current_price)를 추가한다."""

from __future__ import annotations

import json
import os

import requests
from bs4 import BeautifulSoup

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'vcp_signals.json')

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _fetch_prices(code: str, pages: int = 2) -> list[dict]:
    """네이버 금융에서 일봉 데이터를 가져온다. [{date, close}, ...] 최신순."""
    url = f"https://finance.naver.com/item/sise_day.naver?code={code}"
    headers = {**_HEADERS, "Referer": url}
    rows = []
    for page in range(1, pages + 1):
        try:
            resp = requests.get(f"{url}&page={page}", headers=headers, timeout=5)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", class_="type2")
            if not table:
                break
            for tr in table.find_all("tr"):
                cols = tr.find_all("td")
                if len(cols) < 2:
                    continue
                date_text = cols[0].get_text(strip=True)
                price_text = cols[1].get_text(strip=True).replace(",", "")
                if date_text and price_text.isdigit():
                    rows.append({"date": date_text, "close": int(price_text)})
        except Exception as e:
            print(f"  [ERROR] {code} page {page}: {e}")
            break
    return rows


def _find_price_on_or_before(rows: list[dict], target_date: str) -> int | None:
    """target_date(YYYY-MM-DD) 이하인 가장 가까운 거래일 종가를 반환한다."""
    target = target_date.replace("-", ".")
    for r in rows:
        if r["date"] <= target:
            return r["close"]
    return None


def enrich():
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    signal_date = data.get('date', '')  # "2026-03-15"
    signals = data.get('signals', [])
    print(f"시그널 날짜: {signal_date}")
    print(f"총 {len(signals)}개 시그널 처리 시작\n")

    for s in signals:
        code = s.get('code', '')
        name = s.get('name', code)

        print(f"  {name}({code}) 가격 조회 중...")
        rows = _fetch_prices(code, pages=2)  # 최신순 일봉

        if not rows:
            s['entry_price'] = None
            s['current_price'] = None
            s['return_pct'] = 0.0
            s['status'] = 'OPEN'
            print(f"    → 가격 조회 실패, OPEN 처리")
            continue

        current_price = rows[0]["close"]
        entry_price = _find_price_on_or_before(rows, signal_date)

        if entry_price is None:
            entry_price = current_price

        return_pct = round((current_price - entry_price) / entry_price * 100, 2) if entry_price else 0.0

        s['entry_price'] = entry_price
        s['current_price'] = current_price
        s['return_pct'] = return_pct
        s['status'] = 'CLOSED' if return_pct > 0 else 'OPEN'

        print(f"    → 진입가: {entry_price:,} (시그널일 종가) | 현재가: {current_price:,} | 수익률: {return_pct}% | {s['status']}")

    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n완료 — {DATA_PATH} 저장됨")


if __name__ == '__main__':
    enrich()
