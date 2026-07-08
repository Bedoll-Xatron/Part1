"""테마 모멘텀 엔진 실행 진입점.

사용법:
  python run_narrative_momentum.py
  python run_narrative_momentum.py --max-files 20 --min-news 2
  python run_narrative_momentum.py --no-telegram
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from narrative_momentum import run, save_results


def main() -> None:
    parser = argparse.ArgumentParser(description='테마 모멘텀 엔진')
    parser.add_argument('--max-files',   type=int,  default=15, help='참조할 jongga 파일 수')
    parser.add_argument('--min-news',    type=int,  default=1,  help='최소 뉴스 점수')
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

    result = run(target_date=target_dt, min_news_score=args.min_news)
    save_results(result)

    if not args.no_telegram and result['stats']['total'] > 0:
        try:
            from notifier import send_telegram  # type: ignore
            stats = result['stats']
            lines = [
                f"🔥 테마 모멘텀 결과 | {result['date']}",
                f"총 {stats['total']}개  Top테마: {stats['top_theme']}  감성: {stats['avg_sentiment']:+.2f}",
                '',
            ]
            for s in result['signals'][:5]:
                lines.append(f"  [{s['market'][:2]}] {s['name']}  {s['theme']}  {s['score']}점")
            send_telegram('\n'.join(lines))
        except Exception as e:
            print(f'  [텔레그램 실패] {e}')


if __name__ == '__main__':
    main()
