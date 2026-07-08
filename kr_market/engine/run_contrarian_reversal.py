"""역발상 반전 엔진 실행 진입점.

사용법:
  python run_contrarian_reversal.py
  python run_contrarian_reversal.py --top-n 60 --max-rsi 35
  python run_contrarian_reversal.py --no-telegram
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contrarian_reversal import run, save_results


def main() -> None:
    parser = argparse.ArgumentParser(description='역발상 반전 엔진')
    parser.add_argument('--top-n',       type=int, default=50, help='마켓별 하락 종목 수집 수')
    parser.add_argument('--max-rsi',     type=int, default=40, help='최대 RSI (과매도 기준)')
    parser.add_argument('--no-telegram', action='store_true')
    parser.add_argument('--date',        type=str,  help='분석 대상 날짜 (YYYY-MM-DD)')
    args = parser.parse_args()

    target_dt = None
    if args.date:
        from datetime import datetime
        try:
            target_dt = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"  [경고] 잘못된 날짜 형식: {args.date}")

    result = run(target_date=target_dt, top_n=args.top_n, min_rsi_threshold=args.max_rsi)
    save_results(result)

    if not args.no_telegram and result['stats']['total'] > 0:
        try:
            from notifier import send_telegram  # type: ignore
            stats = result['stats']
            lines = [
                f"↩️ 역발상 반전 결과 | {result['date']}",
                f"총 {stats['total']}개  고확률: {stats['high_prob']}개  평균과매도: {stats['avg_oversold']:.1f}",
                '',
            ]
            for s in result['signals'][:5]:
                lines.append(
                    f"  [{s['market'][:2]}] {s['name']}  "
                    f"RSI:{s['rsi']:.1f}  확률:{s['reversal_probability']:.0%}"
                )
            send_telegram('\n'.join(lines))
        except Exception as e:
            print(f'  [텔레그램 실패] {e}')


if __name__ == '__main__':
    main()
