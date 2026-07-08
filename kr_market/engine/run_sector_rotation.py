"""섹터 로테이션 엔진 실행 진입점.

사용법:
  python run_sector_rotation.py
  python run_sector_rotation.py --max-files 20
  python run_sector_rotation.py --no-telegram
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sector_rotation import run, save_results


def main() -> None:
    parser = argparse.ArgumentParser(description='섹터 로테이션 엔진')
    parser.add_argument('--max-files',   type=int, default=15, help='참조할 jongga 파일 수')
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

    result = run(target_date=target_dt, max_files=args.max_files)
    save_results(result)

    if not args.no_telegram and result['stats']['total'] > 0:
        try:
            from notifier import send_telegram  # type: ignore
            stats = result['stats']
            lines = [
                f"🔄 섹터 로테이션 결과 | {result['date']}",
                f"총 {stats['total']}개  {stats['sector_count']}개 섹터  평균RS: {stats['avg_rs']:.1f}",
                '',
            ]
            markup = [s for s in result['signals'] if s['rotation_phase'] == 'markup'][:5]
            if markup:
                lines.append('📈 Markup 섹터:')
                for s in markup:
                    lines.append(f"  [{s['sector']}] {s['name']}  RS:{s['relative_strength']:.1f}")
            send_telegram('\n'.join(lines))
        except Exception as e:
            print(f'  [텔레그램 실패] {e}')


if __name__ == '__main__':
    main()
