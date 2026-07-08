"""
gem_scheduler.py
================
Flask 서버에 내장되는 장중 원석(Gem Hunter) 자동 스케줄러.

서버가 켜져 있으면 **거래일** 장중(09:05~15:25 KST) 5분 간격으로
intraday_gem_scanner.py를 자동 실행하여 intraday_gems.json을 갱신합니다.
별도 배치 파일(run_intraday.bat)을 켤 필요가 없습니다.

공휴일 판별:
  data.go.kr 한국천문연구원 특일정보 API를 사용하여
  임시공휴일·대체공휴일·선거일까지 자동으로 제외합니다.
"""

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

log = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))
_MARKET_OPEN_HOUR = 9
_MARKET_OPEN_MIN = 5       # 09:05 — 장 시작 직후부터
_MARKET_CLOSE_HOUR = 15
_MARKET_CLOSE_MIN = 25     # 15:25 — 장 마감 직전까지
_INTERVAL_SEC = 5 * 60     # 5분 간격

# ── 공휴일 API ────────────────────────────────────────────────────
_HOLIDAY_API_URL = (
    "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
)

# 캐시: { "2026-05": {date(2026,5,1), date(2026,5,5), ...} }
_holiday_cache: dict[str, set] = {}
_holiday_cache_lock = threading.Lock()


def _load_holidays_for_month(year: int, month: int) -> set:
    """
    data.go.kr 특일정보 API로 해당 월의 공휴일(휴일) 날짜 set을 가져온다.
    API 실패 시 빈 set 반환 (주말 체크만으로 폴백).
    """
    api_key = os.environ.get("HOLIDAY_API_KEY", "")
    if not api_key:
        log.warning("[holiday] HOLIDAY_API_KEY가 .env에 없습니다 — 공휴일 필터 비활성")
        return set()

    try:
        params = {
            "solYear": str(year),
            "solMonth": f"{month:02d}",
            "ServiceKey": api_key,
            "_type": "json",
            "numOfRows": "50",
        }
        resp = requests.get(_HOLIDAY_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # 응답 구조: response > body > items > item (list or dict)
        body = data.get("response", {}).get("body", {})
        items = body.get("items", "")
        if not items:
            return set()

        item_list = items.get("item", [])
        if isinstance(item_list, dict):
            item_list = [item_list]

        holidays = set()
        for item in item_list:
            # isHoliday == 'Y' 인 것만 (실제 쉬는 날)
            if item.get("isHoliday") == "Y":
                loc_date = str(item.get("locdate", ""))  # "20260505"
                if len(loc_date) == 8:
                    from datetime import date
                    d = date(int(loc_date[:4]), int(loc_date[4:6]), int(loc_date[6:]))
                    holidays.add(d)

        log.info(
            f"[holiday] {year}-{month:02d} 공휴일 {len(holidays)}일 로드: "
            f"{', '.join(str(d) for d in sorted(holidays)) or '없음'}"
        )
        return holidays

    except Exception as e:
        log.warning(f"[holiday] API 호출 실패 ({e}) — 주말 체크로 폴백")
        return set()


def _is_holiday(dt: datetime) -> bool:
    """오늘이 공휴일인지 판별 (월 단위 캐시 활용)."""
    key = f"{dt.year}-{dt.month:02d}"
    with _holiday_cache_lock:
        if key not in _holiday_cache:
            _holiday_cache[key] = _load_holidays_for_month(dt.year, dt.month)
        return dt.date() in _holiday_cache[key]


def _is_market_hours() -> bool:
    """현재 시각이 한국 장중 거래 시간대인지 확인 (주말 + 공휴일 제외)."""
    now = datetime.now(_KST)
    # 주말 제외
    if now.weekday() >= 5:
        return False
    # 공휴일 제외
    if _is_holiday(now):
        return False
    market_open = now.replace(hour=_MARKET_OPEN_HOUR, minute=_MARKET_OPEN_MIN, second=0)
    market_close = now.replace(hour=_MARKET_CLOSE_HOUR, minute=_MARKET_CLOSE_MIN, second=0)
    return market_open <= now <= market_close


def _run_scanner_safe():
    """스캐너를 실행하되 에러가 나도 스레드를 죽이지 않음."""
    try:
        import subprocess
        import sys

        scanner_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'kr_market', 'engine', 'intraday_gem_scanner.py'
        )
        scanner_path = os.path.abspath(scanner_path)

        log.info(f"[gem-scheduler] 장중 원석 스캐너 실행: {scanner_path}")
        result = subprocess.run(
            [sys.executable, scanner_path],
            capture_output=True,
            text=True,
            timeout=600,  # 10분 타임아웃
            encoding='utf-8',
            errors='replace',
        )
        if result.returncode == 0:
            # 결과 요약 출력
            for line in result.stdout.splitlines():
                if '💎' in line or '✅' in line or '⚠️' in line:
                    log.info(f"[gem-scanner] {line.strip()}")
        else:
            log.warning(f"[gem-scanner] 종료코드 {result.returncode}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        log.warning("[gem-scanner] 타임아웃 (10분 초과)")
    except Exception as e:
        log.error(f"[gem-scanner] 실행 오류: {e}")


def _scheduler_loop():
    """
    무한 루프: 거래일 장중이면 스캐너 실행 후 5분 대기, 장외/공휴일이면 1분마다 체크.
    """
    log.info("[gem-scheduler] 장중 원석 자동 스케줄러 시작됨 (거래일 장중 5분 간격)")

    while True:
        if _is_market_hours():
            log.info("[gem-scheduler] 장중 — 스캐너 실행")
            _run_scanner_safe()
            log.info(f"[gem-scheduler] 다음 스캔까지 {_INTERVAL_SEC // 60}분 대기")
            time.sleep(_INTERVAL_SEC)
        else:
            now = datetime.now(_KST)
            reason = ""
            if now.weekday() >= 5:
                reason = "주말"
            elif _is_holiday(now):
                reason = "공휴일"
            else:
                reason = "장외 시간"
            log.debug(f"[gem-scheduler] {reason} ({now.strftime('%H:%M')}) — 1분 후 재확인")
            time.sleep(60)


def start_gem_scheduler():
    """Flask app factory에서 호출. 데몬 스레드로 실행."""
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="gem-scheduler")
    t.start()
    log.info("[gem-scheduler] 데몬 스레드 등록 완료 (공휴일 API 연동)")

