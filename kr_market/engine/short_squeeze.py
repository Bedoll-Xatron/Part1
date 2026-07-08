"""
공매도 잔고 & Short Squeeze 감지 (Short Squeeze Engine)
=======================================================
우선순위:
  1. KRX 공식 OPEN API (krx_API_KEY) — .env 에 키 입력 시 자동 사용
  2. pykrx 라이브러리 (fallback) — 공식 API 실패 시 스크래핑 방식

KRX 공식 API 절차 (2-step OTP 방식):
  1. OTP 발급 URL → code 획득
  2. 데이터 조회 URL → JSON 결과

설치:
    pip install pykrx   # fallback용
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from typing import Optional

# ── 환경 변수 로드 ─────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    load_dotenv(dotenv_path=_ENV_PATH)
except ImportError:
    pass

_KRX_API_KEY = os.getenv("krx_API_KEY", "")

# ── KIS API 연동 ──────────────────────────────────────────────────
try:
    from kis_api import KISClient
    _KIS_CLIENT = KISClient()
except ImportError:
    _KIS_CLIENT = None

_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR   = os.path.normpath(os.path.join(_ENGINE_DIR, '..', 'data'))


# ── KRX 공식 API (OTP 2-step) ─────────────────────────────────────

_KRX_OTP_URL  = "https://openapi.krx.co.kr/contents/COM/GenerateOTP.cmd"
_KRX_DATA_URL = "https://openapi.krx.co.kr/contents/COM/GetQuote.cmd"

# 공매도 잔고 보고현황 bld 코드
_KRX_SHORT_BLD = "dbms/MDC/STAT/standard/MDCSTAT04301"


def _get_short_ratio_official(stock_code: str, target_date: date) -> Optional[float]:
    """
    KRX 공식 Open API로 단일 종목 공매도 잔고 비율을 조회합니다.
    API 키 없으면 None 반환.
    """
    if not _KRX_API_KEY:
        return None

    import requests

    # T+2 지연 반영
    lookup = (target_date - timedelta(days=2)).strftime("%Y%m%d")

    try:
        # Step 1: OTP 발급
        otp_params = {
            "bld":    _KRX_SHORT_BLD,
            "auth":   _KRX_API_KEY,
            "isuCd":  stock_code,
            "strtDd": lookup,
            "endDd":  lookup,
            "share":  "1",
            "money":  "1",
            "csvxls_isNo": "false",
        }
        otp_resp = requests.get(_KRX_OTP_URL, params=otp_params, timeout=10)
        otp_resp.raise_for_status()
        otp_code = otp_resp.text.strip()

        if not otp_code:
            return None

        # Step 2: 실제 데이터 조회
        data_resp = requests.post(
            _KRX_DATA_URL,
            data={"code": otp_code},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        data_resp.raise_for_status()
        result = data_resp.json()

        rows = result.get("output", []) or []
        for row in rows:
            for key in ["SHRT_BLNC_RT", "shrt_blnc_rt", "잔고비율"]:
                if key in row:
                    return float(str(row[key]).replace(",", "").replace("%", "") or 0)

        return 0.0

    except Exception as e:
        print(f"  [ShortSqueeze/공식API] {stock_code} 조회 실패: {e}")
        return None


def _get_all_official(target_date: date) -> dict[str, float]:
    """KRX 공식 API로 전 종목 공매도 잔고 비율을 한번에 수집합니다."""
    if not _KRX_API_KEY:
        return {}

    import requests

    lookup = (target_date - timedelta(days=2)).strftime("%Y%m%d")
    try:
        otp_params = {
            "bld":    _KRX_SHORT_BLD,
            "auth":   _KRX_API_KEY,
            "strtDd": lookup,
            "endDd":  lookup,
            "share":  "1",
            "money":  "1",
            "csvxls_isNo": "false",
        }
        otp_resp = requests.get(_KRX_OTP_URL, params=otp_params, timeout=10)
        otp_resp.raise_for_status()
        otp_code = otp_resp.text.strip()

        if not otp_code:
            return {}

        data_resp = requests.post(
            _KRX_DATA_URL,
            data={"code": otp_code},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        data_resp.raise_for_status()
        result = data_resp.json()

        rows = result.get("output", []) or []
        out: dict[str, float] = {}
        for row in rows:
            code = row.get("ISU_SRT_CD", row.get("isu_srt_cd", ""))
            if not code:
                continue
            for key in ["SHRT_BLNC_RT", "shrt_blnc_rt"]:
                if key in row:
                    try:
                        out[code] = float(str(row[key]).replace(",", "") or 0)
                    except ValueError:
                        pass
                    break
        print(f"  [ShortSqueeze/공식API] {len(out)}개 종목 공매도 잔고 수집 완료")
        return out

    except Exception as e:
        print(f"  [ShortSqueeze/공식API] 전체 수집 실패: {e}")
        return {}


# ── pykrx fallback ────────────────────────────────────────────────

def _get_short_ratio_pykrx(stock_code: str, target_date: date) -> float:
    """pykrx 라이브러리로 공매도 잔고 비율(%) 조회 (fallback)."""
    try:
        from pykrx import stock  # type: ignore
    except ImportError:
        return 0.0

    lookup = (target_date - timedelta(days=2)).strftime("%Y%m%d")
    try:
        df = stock.get_shorting_balance_by_ticker(lookup)
        if df is None or df.empty:
            return 0.0
        if stock_code in df.index:
            row = df.loc[stock_code]
            for col in ["공매도잔고비율", "비율", "잔고비율"]:
                if col in row.index:
                    return float(row[col])
    except Exception as e:
        print(f"  [ShortSqueeze/pykrx] {stock_code} 조회 실패: {e}")
    return 0.0


def _get_all_pykrx(target_date: date) -> dict[str, float]:
    """pykrx로 전 종목 공매도 잔고 비율 수집 (fallback)."""
    try:
        from pykrx import stock  # type: ignore
    except ImportError:
        print("  [ShortSqueeze] pykrx 미설치. `python -m pip install pykrx`")
        return {}

    lookup = (target_date - timedelta(days=2)).strftime("%Y%m%d")
    try:
        df = stock.get_shorting_balance_by_ticker(lookup)
        if df is None or df.empty:
            return {}
        result: dict[str, float] = {}
        for col in ["공매도잔고비율", "비율", "잔고비율"]:
            if col in df.columns:
                for code, val in df[col].items():
                    try:
                        result[str(code)] = float(val)
                    except (ValueError, TypeError):
                        pass
                break
        print(f"  [ShortSqueeze/pykrx] {len(result)}개 종목 수집 완료")
        return result
    except Exception as e:
        print(f"  [ShortSqueeze/pykrx] 전체 수집 실패: {e}")
        return {}


# ── 통합 인터페이스 ────────────────────────────────────────────────

def _get_short_balance_ratio(stock_code: str, target_date: date) -> float:
    """공매도 잔고 비율(%) 조회 — KIS 우선, 공식 API 차선, pykrx fallback."""
    # 1. KIS API (최신/정상 데이터 확률 높음)
    if _KIS_CLIENT and _KIS_CLIENT.app_key:
        data = _KIS_CLIENT.get_short_selling_data(stock_code)
        if data and "ratio" in data:
            return data["ratio"]

    # 2. KRX 공식 API
    if _KRX_API_KEY:
        ratio = _get_short_ratio_official(stock_code, target_date)
        if ratio is not None:
            return ratio

    # 3. pykrx fallback
    return _get_short_ratio_pykrx(stock_code, target_date)


def fetch_all_short_balances(target_date: date | None = None) -> dict[str, float]:
    """
    전 종목 공매도 잔고 비율 벌크 수집 — 공식 API 우선, pykrx fallback.
    daily_update.py 에서 하루 한 번 호출하세요.
    """
    effective = target_date or date.today()
    api_tag = "공식API 사용" if _KRX_API_KEY else "pykrx fallback"
    print(f"  [ShortSqueeze] 공매도 잔고 수집 시작 ({api_tag})...")

    if _KRX_API_KEY:
        result = _get_all_official(effective)
        if result:
            return result
        print("  [ShortSqueeze] 공식 API 실패 → pykrx fallback")

    return _get_all_pykrx(effective)


# ── Short Squeeze 점수 계산 ───────────────────────────────────────

class ShortSqueezeScorer:
    """
    공매도 잔고 비율 + 수급 강도를 결합하여 0~2점 보너스 계산.

    점수 기준:
      2점: 공매도 잔고비율 >= 5%  AND  수급 점수 >= 2  (쌍매수 + 고공매도 = 잠재 폭발)
      1점: 공매도 잔고비율 >= 2%  AND  수급 점수 >= 1
      0점: 조건 미충족
    """
    def __init__(self, target_date: date | None = None):
        self.target_date = target_date or date.today()
        self._cache: dict[str, float] = {}

    def squeeze_bonus(self, stock_code: str, supply_score: int) -> int:
        if supply_score == 0:
            return 0

        if stock_code not in self._cache:
            ratio = _get_short_balance_ratio(stock_code, self.target_date)
            self._cache[stock_code] = ratio
            time.sleep(0.1)
        else:
            ratio = self._cache[stock_code]

        if ratio >= 5.0 and supply_score >= 2:
            return 2
        if ratio >= 2.0 and supply_score >= 1:
            return 1
        return 0

    def get_ratio(self, stock_code: str) -> float:
        return self._cache.get(stock_code, 0.0)


# ── 독립 실행 & API 키 테스트 ─────────────────────────────────────

if __name__ == "__main__":
    print("=== KRX API 키 상태 ===")
    print(f"  krx_API_KEY: {'설정됨' if _KRX_API_KEY else '미설정 (pykrx fallback)'}")

    print("\n=== Short Squeeze 테스트 (삼성전자·SK하이닉스·NAVER) ===")
    test_codes = ["005930", "000660", "035420"]
    scorer = ShortSqueezeScorer()
    for code in test_codes:
        ratio = _get_short_balance_ratio(code, date.today())
        bonus = scorer.squeeze_bonus(code, supply_score=2)
        print(f"  {code} | 공매도잔고: {ratio:.2f}% | 보너스: {bonus}점")

    print("\n=== 전체 종목 상위 5 공매도 잔고 ===")
    all_bal = fetch_all_short_balances()
    for code, ratio in sorted(all_bal.items(), key=lambda x: -x[1])[:5]:
        print(f"  {code}: {ratio:.2f}%")
