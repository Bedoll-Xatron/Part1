# 주식 시그널 분석 시스템 (Part1)

## 자동 업데이트 규칙
- 새 파일 생성, 메서드 추가/변경, 구현 상태 변경 시 이 CLAUDE.md를 즉시 업데이트할 것
- 미구현 → 완료 전환 시 Scorer 점수 체계 테이블 반영
- 새 테스트/시각화 파일 추가 시 해당 테이블에 추가

## 프로젝트 개요
한국 주식(KOSPI/KOSDAQ) 급등 종목을 자동 감지하고, 8개 항목 15점 만점으로 스코어링하여 A/B/C 등급을 매기는 시스템.

## 디렉토리 구조
```
Part1/
├── CLAUDE.md
├── kr_market/
│   ├── engine/                    ← 핵심 소스 코드
│   │   ├── .env                   ← API 키 (Gemini)
│   │   ├── models.py
│   │   ├── config.py
│   │   ├── collectors.py
│   │   ├── llm_analyzer.py
│   │   ├── scorer.py
│   │   ├── position_sizer.py       ← PositionSizer + PositionResult
│   │   ├── generator.py           ← SignalGenerator (메인 파이프라인)
│   │   ├── persistence.py         ← JSON 저장 (날짜별 + latest)
│   │   ├── run_engine.py          ← V2 실행 진입점
│   │   └── run_scoring.py         ← V1 실행 진입점
│   ├── data/                        ← 결과 JSON 저장
│   │   ├── jongga_v2_results_YYYYMMDD.json
│   │   └── jongga_v2_latest.json
│   ├── 시각화_결과물/               ← 실행 시 자동 생성
│   │   ├── scoring_checklist.html
│   │   └── 웹대시보드.html
│   └── 시각화_가이드/               ← 정적 가이드 파일
│       ├── candle_guide.html
│       ├── supply_insight.html
│       ├── bonus_patterns.html
│       ├── grading_insight.html
│       ├── consolidation_breakout.html
│       └── disclaimer.html            ← 투자 면책 고지
└── _archive/                      ← 이전 파일 보관
```

## 실행 방법
```bash
cd kr_market/engine
python3 run_scoring.py
```

## 파이프라인
```
수집(collectors.py) → LLM 분석(llm_analyzer.py) → 스코어링(scorer.py) → 리포트(HTML)
```

## 핵심 파일 (kr_market/engine/)

| 파일 | 역할 |
|---|---|
| `models.py` | 데이터 모델 (StockData, ChartData, SupplyData, ScoreDetail, ChecklistDetail, NewsData, Grade, Signal, ScreenerResult) |
| `config.py` | SignalConfig — 필터링 조건 (거래대금, 등락률, 가격 범위, 제외 키워드) |
| `scorer.py` | Scorer 클래스 — 8개 항목 점수 산출 (`calculate()` → `ScoreDetail, ChecklistDetail`) |
| `collectors.py` | 데이터 수집기 (시세, 차트, 뉴스, 수급) |
| `llm_analyzer.py` | LLM 기반 뉴스/재료 분석 |
| `position_sizer.py` | PositionResult (데이터클래스) + PositionSizer (R 기반 포지션 사이징) |
| `generator.py` | SignalGenerator (메인 파이프라인) |
| `persistence.py` | save_result_to_json() — ScreenerResult를 날짜별/latest JSON으로 저장 |
| `run_engine.py` | V2 실행 진입점 — SignalGenerator + 저장 + 결과 출력 |
| `notifier.py` | 텔레그램 알림 (send_telegram, _send_long_telegram) |
| `run_scoring.py` | V1 실행 진입점 — 통합 파이프라인 + HTML 리포트/대시보드 |

## Scorer 점수 체계 (15점 만점)

| # | 항목 | 배점 | 메서드 | 상태 |
|---|---|---|---|---|
| 1 | 뉴스/재료 | 0~3 | `_score_news()` | 완료 |
| 2 | 거래대금 | 0~3 | `_score_volume()` | 완료 |
| 3 | 차트패턴 | 0~3 | `_score_chart()` | 완료 (VCP 슬롯 비어있음) |
| 4 | 캔들형태 | 0~1 | `_score_candle()` | 완료 |
| 5 | 기간조정 | 0~1 | `_score_consolidation()` | 완료 |
| 6 | 수급 | 0~2 | `_score_supply()` | 완료 |
| 7 | 조정폭 회복 | 0~1 | `_score_retracement_recovery()` | 완료 |
| 8 | 되돌림 지지 | 0~1 | `_score_pullback_support()` | 완료 |

## 주요 모델 필드명 주의
- SupplyData: `foreign_net_5d`, `inst_net_5d` (buy가 아닌 net)
- StockData: `trading_value` (거래대금), `change_pct` (등락률)
- ChartData: `ma5`, `ma10`, `ma20` (Optional[float])

## 등급 기준
- **A**: 9점 이상 (적극 매수)
- **B**: 7~8점 (관심 관찰)
- **C**: 6점 이하 또는 필수 조건 미통과 (패스)
- 필수 조건: `news >= 1 AND volume >= 1`

## 컨벤션
- 스코어링 메서드 반환 패턴: `Tuple[int, bool]` 또는 `Tuple[int, dict]`
- 테스트 파일: `_archive/test_*.py` (보관)
- python3으로 실행 (python 명령어 없음)
