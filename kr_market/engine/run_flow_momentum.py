"""
수급 모멘텀 엔진 실행 진입점
==============================
사용법:
  python run_flow_momentum.py               # 기본 실행
  python run_flow_momentum.py --top-n 50    # 마켓별 50개 후보
  python run_flow_momentum.py --min-flow 2  # flow_score 2점 이상만 저장
  python run_flow_momentum.py --no-telegram # 텔레그램 알림 비활성화
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flow_momentum import run, save_results


def _build_telegram_message(result: dict) -> str:
    stats   = result['stats']
    signals = result['signals']
    strong  = [s for s in signals if s['signal_strength'] == 'strong']
    mod     = [s for s in signals if s['signal_strength'] == 'moderate']

    lines = [
        f"📊 수급 모멘텀 결과 | {result['date']}",
        f"총 {stats['total']}개  강:{stats['strong']} 중:{stats['moderate']} 약:{stats['weak']}",
        '',
    ]

    if strong:
        lines.append('🔥 강한 수급 종목:')
        for s in strong[:5]:
            market_tag = s['market'][:2]
            lines.append(
                f"  [{market_tag}] {s['name']}  {s['score']}점 "
                f"외:{s['foreign_flow']:+.0f}억 기:{s['institution_flow']:+.0f}억"
            )

    if mod:
        lines.append('')
        lines.append('📈 보통 수급 종목:')
        for s in mod[:3]:
            market_tag = s['market'][:2]
            lines.append(
                f"  [{market_tag}] {s['name']}  {s['score']}점 "
                f"외:{s['foreign_flow']:+.0f}억 기:{s['institution_flow']:+.0f}억"
            )

    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description='수급 모멘텀 엔진')
    parser.add_argument('--top-n',     type=int,  default=40, help='마켓별 후보 종목 수 (default 40)')
    parser.add_argument('--min-flow',  type=int,  default=1,  help='최소 flow_score (default 1)')
    parser.add_argument('--no-telegram', action='store_true', help='텔레그램 알림 비활성화')
    parser.add_argument('--date',        type=str,  help='분석 대상 날짜 (YYYY-MM-DD)')
    args = parser.parse_args()

    target_dt = None
    if args.date:
        try:
            from datetime import datetime
            target_dt = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"  [경고] 잘못된 날짜 형식: {args.date}")

    # 엔진 실행
    result = run(target_date=target_dt, top_n=args.top_n, min_flow_score=args.min_flow)

    # 저장
    save_results(result)

    # 텔레그램 알림
    if not args.no_telegram and result['stats']['total'] > 0:
        try:
            from notifier import send_telegram  # type: ignore
            msg = _build_telegram_message(result)
            send_telegram(msg)
            print('  텔레그램 전송 완료')
        except ImportError:
            print('  [스킵] notifier 모듈 없음')
        except Exception as e:
            print(f'  [경고] 텔레그램 전송 실패: {e}')


if __name__ == '__main__':
    main()
