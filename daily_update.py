"""
daily_update.py
=================
매 거래일 장 마감(오후 4시) 이후 실행하는 일일 누적 업데이트 스크립트.

실행 순서:
  1. run_engine.py               — 종가베팅(jongga) V2 시그널 생성
  2. vcp_scanner.py              — VCP 패턴 스캔 (날짜별 누적 저장)
  3. run_flow_momentum.py        — 수급 모멘텀
  4. run_narrative_momentum.py   — 테마/내러티브 모멘텀
  5. run_sector_rotation.py      — 섹터 로테이션
  6. run_contrarian_reversal.py  — 역발상 반전
  7. build_daily_prices.py       — daily_prices.csv 누적 업데이트

사용법:
  python daily_update.py                 # 거래일 자동 체크 후 실행
  python daily_update.py --force         # 주말/휴일 무시하고 강제 실행
  python daily_update.py --no-telegram   # 텔레그램 알림 비활성화
  python daily_update.py --only jongga vcp  # 특정 엔진만 실행
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta

# ── 경로 ─────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.join(BASE_DIR, 'kr_market', 'engine')
LOG_DIR    = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# ── 로깅 ─────────────────────────────────────────────────────────
log_file = os.path.join(LOG_DIR, f"daily_update_{date.today().strftime('%Y%m%d')}.log")
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', closefd=False)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        _stream_handler,
    ],
)
log = logging.getLogger(__name__)

# ── 한국 공휴일 ───────────────────────────────────────────────────
# 대체공휴일 포함. 필요 시 아래에 날짜를 추가하세요.
KR_HOLIDAYS: set[date] = {
    # 2026
    date(2026, 1,  1),   # 신정
    date(2026, 1, 28),   # 설날 연휴
    date(2026, 1, 29),   # 설날
    date(2026, 1, 30),   # 설날 연휴
    date(2026, 3,  1),   # 삼일절
    date(2026, 3,  2),   # 삼일절 대체공휴일 (3/1이 일요일)
    date(2026, 5,  5),   # 어린이날
    date(2026, 5, 25),   # 부처님 오신 날
    date(2026, 6,  6),   # 현충일
    date(2026, 8, 15),   # 광복절
    date(2026, 9, 24),   # 추석 연휴
    date(2026, 9, 25),   # 추석
    date(2026, 9, 26),   # 추석 연휴
    date(2026, 10, 3),   # 개천절
    date(2026, 10, 5),   # 개천절 대체공휴일 (10/3이 토요일)
    date(2026, 10, 9),   # 한글날
    date(2026, 12, 25),  # 성탄절
    # 2027
    date(2027, 1,  1),   # 신정
    date(2027, 2, 16),   # 설날 연휴
    date(2027, 2, 17),   # 설날
    date(2027, 2, 18),   # 설날 연휴
    date(2027, 3,  1),   # 삼일절
    date(2027, 5,  5),   # 어린이날
    date(2027, 5, 13),   # 부처님 오신 날
    date(2027, 6,  6),   # 현충일
    date(2027, 8, 15),   # 광복절
    date(2027, 10, 3),   # 개천절
    date(2027, 10, 9),   # 한글날
    date(2027, 12, 25),  # 성탄절
}


def is_trading_day(d: date | None = None) -> bool:
    """주말 및 한국 공휴일이 아닌 평일인지 확인."""
    if d is None:
        d = date.today()
    if d.weekday() >= 5:      # 토(5), 일(6)
        return False
    return d not in KR_HOLIDAYS


def get_last_trading_day(d: date) -> date:
    """기준일 이전의 가장 최근 거래일을 반환."""
    prev = d - timedelta(days=1)
    while not is_trading_day(prev):
        prev -= timedelta(days=1)
    return prev


def run_script(name: str, script: str, extra_args: list[str]) -> bool:
    """엔진 스크립트를 ENGINE_DIR 에서 실행하고 성공 여부를 반환."""
    script_path = os.path.join(ENGINE_DIR, script)
    if not os.path.exists(script_path):
        log.error(f"  스크립트 없음: {script_path}")
        return False

    cmd = [sys.executable, script_path] + extra_args
    log.info(f"  $ {' '.join(os.path.basename(c) for c in cmd)}")

    # Windows cp949 환경에서 이모지/한글 print 오류 방지
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'

    try:
        proc = subprocess.run(
            cmd,
            cwd=ENGINE_DIR,           # 상대 import가 동작하도록 engine/ 에서 실행
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=600,
            env=env,
        )
        for line in (proc.stdout or '').strip().splitlines():
            log.info(f"    {line}")
        for line in (proc.stderr or '').strip().splitlines():
            log.warning(f"    [stderr] {line}")
        if proc.returncode != 0:
            log.error(f"  → 실패 (exit={proc.returncode})")
            return False
        log.info(f"  → 완료")
        return True
    except subprocess.TimeoutExpired:
        log.error(f"  → 타임아웃 (600초 초과)")
        return False
    except Exception as e:
        log.error(f"  → 예외 발생: {e}")
        return False


# ── 실행할 단계 목록 ──────────────────────────────────────────────
# (alias, 표시명, 스크립트파일, 추가인수 플래그키)
STEPS = [
    ("jongga",     "종가베팅 V2",          "run_engine.py",               True),
    ("vcp",        "VCP 패턴 스캐너",       "vcp_scanner.py",              False),
    ("flow",       "수급 모멘텀",           "run_flow_momentum.py",        True),
    ("narrative",  "테마 모멘텀",           "run_narrative_momentum.py",   True),
    ("sector",     "섹터 로테이션",         "run_sector_rotation.py",      True),
    ("contrarian", "역발상 반전",           "run_contrarian_reversal.py",  True),
    ("prices",     "daily_prices 업데이트", "build_daily_prices.py",       False),
    ("supabase",   "Supabase 푸시",         "supabase_push.py",            False),
]


def main() -> None:
    parser = argparse.ArgumentParser(description='일일 시장 데이터 자동 업데이트')
    parser.add_argument('--force',       action='store_true',
                        help='거래일 여부를 무시하고 강제 실행')
    parser.add_argument('--no-telegram', action='store_true',
                        help='텔레그램 알림 비활성화')
    parser.add_argument('--only',        nargs='+', metavar='ALIAS',
                        help=f"지정한 엔진만 실행 (alias: {', '.join(s[0] for s in STEPS)})")
    args = parser.parse_args()

    today = date.today()
    log.info('=' * 60)
    log.info(f"일일 업데이트 시작: {today}  {datetime.now().strftime('%H:%M:%S')}")
    log.info('=' * 60)

    # ── 분석 대상 날짜 결정 (Intelligent Date Selection) ──────────
    # 오전 11:00 이전 실행 시: '직전 거래일' 마감 데이터 분석 (Morning Briefing)
    # 오전 11:00 이후 실행 시: '오늘' 장중/마감 데이터 분석 (Intraday/Evening Scan)
    now = datetime.now()
    if now.hour < 11:
        target_date = get_last_trading_day(today)
        mode_str = "오전 모드 (직전 거래일 분석)"
    else:
        target_date = today
        mode_str = "오후 모드 (당일 데이터 분석)"

    log.info(f"실행 모드: {mode_str}")
    log.info(f"분석 대상 날짜: {target_date}")
    log.info('-' * 60)

    # ── 실행 대상 필터 ────────────────────────────────────────────

    # ── 실행 대상 필터 ────────────────────────────────────────────
    only = set(args.only) if args.only else None
    steps_to_run = [s for s in STEPS if only is None or s[0] in only]
    if only:
        unknown = only - {s[0] for s in STEPS}
        if unknown:
            log.warning(f"알 수 없는 alias: {', '.join(unknown)}")

    # ── 각 엔진 순차 실행 ─────────────────────────────────────────
    results: list[tuple[str, bool]] = []
    for alias, display_name, script, has_telegram in steps_to_run:
        log.info(f"\n[{display_name}]")
        
        # 기본 공통 인자: --date
        extra: list[str] = ["--date", target_date.strftime("%Y-%m-%d")]
        
        # 텔레그램 인자
        if has_telegram and args.no_telegram:
            extra.append('--no-telegram')
            
        ok = run_script(display_name, script, extra)
        results.append((display_name, ok))

    # ── 최종 요약 ─────────────────────────────────────────────────
    log.info(f"\n{'=' * 60}")
    log.info(f"업데이트 완료 요약 ({today})")
    log.info('-' * 60)
    success_count = sum(1 for _, ok in results if ok)
    for display_name, ok in results:
        mark = '✓' if ok else '✗'
        log.info(f"  {mark}  {display_name}")
    log.info('-' * 60)
    log.info(f"성공: {success_count}/{len(results)}")
    log.info('=' * 60)


if __name__ == '__main__':
    main()
