# Part 6 프롬프트 모음 — 수강생용

> 강의를 따라하면서 아래 프롬프트를 Claude Code에 입력하세요. 순서대로 진행하면 Part 6가 완성됩니다. **프롬프트 → 테스트 → 확인** 3단계로 진행합니다. 각 섹션 끝에 ✅ 체크포인트가 있습니다.

---

## 0. 사전 준비

### 패키지 설치

```bash
pip install flask flask-cors python-dotenv pandas yfinance requests beautifulsoup4
```

### 프로젝트 폴더 확인

```bash
# 프로젝트 루트에서 실행해야 합니다
ls kr_market/data/
# jongga_v2_latest.json, vcp_signals.json 등이 보여야 함
```

> ⚠️ **주의**: 반드시 프로젝트 루트(최상위 폴더)에서 작업하세요. `kr_market/data/` 경로가 상대경로이므로 다른 폴더에서 실행하면 파일을 찾을 수 없습니다.

---

## 6-1. Flask 프로젝트 구조

### 프롬프트 1: App Factory

```
app/__init__.py 파일을 만들어줘.

create_app() 함수:
1. Flask 앱 생성
2. .env에서 환경변수 로드 (python-dotenv)
3. CORS 설정 — /api/* 경로에 모든 origin 허용
4. Blueprint 등록 (register_blueprints 함수 호출)
5. 앱 반환

CORS(app, resources={r"/api/*": {"origins": "*"}})
이렇게 설정하면 프론트엔드에서 API를 호출할 수 있어.
```

> 💡 **App Factory란?** 앱을 만드는 "공장 함수"입니다. 테스트할 때, 배포할 때 설정만 바꿔서 다른 버전의 앱을 만들 수 있습니다.

### 프롬프트 2: Blueprint 등록

```
app/routes/__init__.py 파일을 만들어줘.

register_blueprints(app) 함수:
  kr_market.py의 kr_bp를 url_prefix='/api/kr'로 등록

이렇게 하면 kr_market.py의 모든 라우트가 /api/kr/ 아래에 자동으로 배치돼.
예: @kr_bp.route('/signals') → GET /api/kr/signals
```

> 💡 **Blueprint란?** 회사의 "부서"와 같습니다. 한국주식(kr), 미국주식(us), 암호화폐(crypto) 각각 독립적으로 API를 관리합니다.

### 프롬프트 3: 빈 KR Blueprint + run.py

```
1. app/routes/kr_market.py를 만들어줘:
   kr_bp = Blueprint('kr', __name__)
   테스트용 라우트 하나만 만들어:
   @kr_bp.route('/health')
   def health(): return jsonify({"status": "ok"})

2. run.py를 만들어줘:
   from app import create_app
   app = create_app()
   app.run(host='0.0.0.0', port=5001, debug=True)
```

### 테스트 4: 서버 실행

> ⚠️ **터미널 2개가 필요합니다.**
> - **터미널 1:** 서버 실행 (끄지 마세요)
> - **터미널 2:** curl로 테스트

**터미널 1 (서버 실행)**

```bash
python run.py
```

**터미널 2 (테스트)**

```bash
curl http://localhost:5001/api/kr/health
```

✅ **체크포인트 6-1**: `{"status": "ok"}` 응답 확인

---

## 6-2. 시그널 API

### 프롬프트 5: VCP 시그널 API

```
kr_market.py에 /signals 엔드포인트를 추가해줘.
_cached_response(ttl_seconds=300) 캐시 적용.

GET /api/kr/signals:
1. kr_market/data/jongga_v2_latest.json 파일을 읽어
2. signals 배열을 꺼내서 score 기준 내림차순 정렬
3. JSON 응답으로 반환:
   {
     "signals": [...],
     "count": 5,
     "generated_at": "2026-02-17",
     "source": "json_live"
   }

파일이 없으면:
   {"signals": [], "count": 0, "message": "시그널 데이터가 없습니다."}

에러 발생 시:
   {"error": "에러 메시지"}, 500
```

### 테스트 5: 시그널 API 확인

```bash
# 기본 테스트
curl http://localhost:5001/api/kr/signals

# JSON 보기 좋게 정렬
curl -s http://localhost:5001/api/kr/signals | python -m json.tool
```

> 💡 **curl 옵션:** `-s` (진행 상태바 숨기기), `| python -m json.tool` (JSON 정렬)

✅ **체크포인트 6-2**: signals 배열과 count 숫자 확인 (데이터 파일이 없어도 빈 배열 응답이 오면 정상)

---

## 6-3. 종가베팅 API

### 프롬프트 6: 종가베팅 3개 API

```
kr_market.py에 종가베팅 API 3개를 추가해줘.
모두 _cached_response(ttl_seconds=300) 캐시 적용.

1. GET /api/kr/jongga-v2/latest
   - kr_market/data/jongga_v2_latest.json 읽어서 반환
   - 파일 없으면 jongga_v2_results_*.json 중 가장 최신 파일
   - 그것도 없으면 {"signals": [], "message": "No data"}

2. GET /api/kr/jongga-v2/dates
   - jongga_v2_results_*.json 파일들의 날짜 목록 반환
   - 파일명에서 날짜 추출 (예: jongga_v2_results_20260217.json → "20260217")
   - 최신순 정렬

3. GET /api/kr/jongga-v2/history/<date_str>
   - YYYYMMDD 형식 검증 (8자리 숫자)
   - 특정 날짜의 결과 파일을 읽어서 반환
   - 없으면 404
```

> 💡 **폴백(fallback)이란?** 1순위가 없으면 2순위, 그것도 없으면 기본값을 반환하여 에러를 방지하는 패턴입니다.

### 테스트 6: 종가베팅 API 확인

```bash
# 1. 최신 결과
curl http://localhost:5001/api/kr/jongga-v2/latest

# 2. 날짜 목록
curl http://localhost:5001/api/kr/jongga-v2/dates
# ["20260305", "20260228", "20260217"] 형태

# 3. 특정 날짜 조회 (위에서 확인한 날짜 입력)
curl http://localhost:5001/api/kr/jongga-v2/history/20260305

# 4. 404 에러 확인
curl http://localhost:5001/api/kr/jongga-v2/history/19990101
```

✅ **체크포인트 6-3**: latest 응답, dates 배열, history 정상/404 작동 확인

---

## 6-4. 마켓 게이트 API

### 프롬프트 7: TTL 캐시 데코레이터

```
kr_market.py에 TTL 캐시 데코레이터를 추가해줘.

_cached_response(ttl_seconds=300) 데코레이터:
- 같은 URL 요청이 ttl_seconds 이내에 또 오면 캐시된 응답 반환
- 캐시 키 = 함수이름 + URL 경로
- 딕셔너리에 (데이터, 만료시각)을 저장
- 만료되면 새로 호출
```

> 💡 **TTL(Time To Live)이란?** 데이터의 유효기간입니다. 매번 새로 계산하지 않고 일정 시간 동안 저장된 결과를 반환합니다.

### 프롬프트 8: 마켓 게이트 API

```
kr_market.py에 /market-gate 엔드포인트를 추가해줘.
_cached_response(ttl_seconds=300) 캐시 적용해줘.

GET /api/kr/market-gate:
1. KODEX 200(069500) 데이터 로드
2. MA20, MA50, MA200 계산
3. 시장 상태 판단:
   - 현재가 > MA200 AND MA20 > MA50 → "RISK_ON"
   - 현재가 < MA200 AND MA20 < MA50 → "RISK_OFF"
   - 그 외 → "NEUTRAL"
4. 섹터별 등락률 데이터 포함

응답 형식:
{
  "date": "2026.03.15",
  "kodex200": {"code": "069500", "price": ..., "ma20": ..., "ma50": ..., "ma200": ...},
  "regime": "RISK_ON",
  "regime_detail": {"price_above_ma200": true, "ma20_above_ma50": true},
  "sectors": [{"name": "반도체", "change_pct": 2.3}, ...]
}
```

### 테스트 8: 마켓 게이트 및 캐시 확인

```bash
# 1차 요청 (계산 실행 — 네이버 금융 크롤링으로 수초 소요)
curl http://localhost:5001/api/kr/market-gate

# 2차 요청 (5분 이내 — 캐시 히트로 즉시 응답)
curl http://localhost:5001/api/kr/market-gate
```

✅ **체크포인트 6-4**: regime 값(RISK_ON/NEUTRAL/RISK_OFF) 확인 및 2차 요청 속도 향상(캐시 작동) 확인

---

## 6-5. 실시간 가격 API

### 프롬프트 9: PriceCache 싱글턴

```
app/utils/price_cache.py를 만들어줘.

PriceCache 클래스 (싱글턴):
- _prices: {ticker: {price, change_pct, volume, updated_at}}
- _tracked: 추적 중인 ticker set
- _lock: Threading Lock (스레드 안전)
- _version: 변경 감지용 버전 번호

메서드:
- get_instance() 클래스 메서드 → 싱글턴
- register_tickers(tickers) → 추적 ticker 등록
- bulk_update(prices) → 가격 일괄 업데이트
- get_prices(tickers=None) → 캐시된 가격 조회
- get_version() → 현재 버전

스레드 안전을 위해 모든 접근에 Lock 사용.
```

### 프롬프트 10: 실시간 가격 API

```
kr_market.py에 실시간 가격 API 2개를 추가해줘.

1. POST /api/kr/realtime-prices
   - Body: {"tickers": ["005930", "000660"]}
   - PriceCache에서 조회 (캐시 미스 시 yfinance 폴백)
   - 응답: {"prices": {"005930": {"price": 58000, "change_pct": 1.2}}, "version": 1}

2. GET /api/kr/price-stream (SSE)
   - Server-Sent Events로 실시간 가격 스트리밍
   - PriceCache의 version 변경 시 새 데이터 전송 (5초 간격 체크)
   - Content-Type: text/event-stream
```

> 💡 **SSE(Server-Sent Events)란?** 서버가 클라이언트에게 단방향으로 실시간 데이터를 지속적으로 밀어주는(push) 방식입니다.

### 테스트 10: POST 및 SSE 테스트

**POST 요청 (curl)**

```bash
curl -X POST http://localhost:5001/api/kr/realtime-prices \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["005930", "000660"]}'
```

**SSE 스트림 테스트 (curl)**

```bash
curl http://localhost:5001/api/kr/price-stream
# 5초마다 데이터가 출력됩니다. 중단하려면 Ctrl+C를 누르세요.
```

✅ **체크포인트 6-5**: POST 응답에서 prices 객체 확인 및 SSE 스트림 정상 수신 확인

---

## 6-5½. 성과 추적 데이터 준비

> ⚠️ **왜 이 단계가 필요한가?** 6-6에서 만들 성과 추적 API는 데이터 파일이 필요합니다.
> - `vcp_signals.json`에 현재 시그널만 있고 **status, return_pct 필드가 없음**
> - 종가베팅 시그널의 이후 가격을 추적할 **daily_prices.csv가 없음**
>
> 이 스크립트를 먼저 만들어 데이터를 준비한 뒤 6-6으로 넘어갑니다.

### 프롬프트 10a: VCP 시그널 상태 추가

```
kr_market/data/vcp_signals.json을 읽어서
각 시그널에 성과 추적 필드를 추가하는
스크립트 kr_market/engine/enrich_vcp.py를 만들어줘.

로직:
1. vcp_signals.json의 각 시그널에서 pivot_high를 진입가로 사용
2. 네이버 금융에서 해당 종목의 현재가를 조회
3. return_pct = (현재가 - pivot_high) / pivot_high * 100
4. return_pct > 0 이면 status="CLOSED", 아니면 status="OPEN"
5. 각 시그널에 status, return_pct, current_price 필드 추가
6. 결과를 vcp_signals.json에 덮어쓰기
```

### 프롬프트 10b: 일별 가격 CSV 생성

```
kr_market/engine/build_daily_prices.py를 만들어줘.

로직:
1. kr_market/data/jongga_v2_results_*.json 전체 로드
2. 모든 시그널의 stock_code 목록 추출 (중복 제거)
3. 각 종목의 signal_date 이후 일별 종가를 네이버 금융에서 수집
4. 결과를 kr_market/data/daily_prices.csv로 저장

CSV 형식:
stock_code,date,close
036930,2026-03-05,32000
036930,2026-03-06,33500
...
```

### 테스트 10½: 데이터 생성 확인

```bash
# 1. VCP 시그널 상태 추가
python kr_market/engine/enrich_vcp.py

# 2. 결과 확인 — status, return_pct 필드가 보이면 성공
cat kr_market/data/vcp_signals.json | python -m json.tool

# 3. 일별 가격 CSV 생성
python kr_market/engine/build_daily_prices.py

# 4. 결과 확인 — stock_code,date,close 헤더가 보이면 성공
head -5 kr_market/data/daily_prices.csv
```

✅ **체크포인트 6-5½**: vcp_signals.json에 `"status"` 필드 추가됨 + daily_prices.csv 파일 생성됨

---

## 6-6. 성과 추적 API

### 프롬프트 11: VCP 누적 성과

```
kr_market.py에 /vcp-cumulative 엔드포인트를 추가해줘.
_cached_response(ttl_seconds=120) 적용.

GET /api/kr/vcp-cumulative:
1. kr_market/data/vcp_signals.json 읽기
2. 각 시그널 상태 분류: OPEN / CLOSED (status 필드)
3. CLOSED에서 승률, 평균 수익률, 등급별 성과 계산
4. 응답: {"stats": {total, closed, open, win_rate,
   avg_return, grade_stats: {A: {...}, B: {...}}}}
```

### 프롬프트 12: 종가베팅 누적 성과

```
kr_market.py에 /jongga-v2/cumulative 엔드포인트를 추가해줘.

GET /api/kr/jongga-v2/cumulative:
1. jongga_v2_results_*.json 파일 전체 로드
2. daily_prices.csv에서 시그널 이후 가격 추적
3. 타겟가(+9%) 도달 → TARGET_HIT (승)
4. 손절가(-5%) 도달 → STOP_HIT (패)
5. 아직 미결 → OPEN (현재가 기준 평가)
6. 각 시그널에 outcome, roi_pct, days_held 포함
7. 승률, 평균 ROI, 등급별 ROI 계산
8. 페이지네이션 지원 (?page=1&per_page=20)
```

### 테스트 12: 성과 API 확인

```bash
# VCP 누적 성과
curl http://localhost:5001/api/kr/vcp-cumulative

# 종가베팅 누적 성과
curl http://localhost:5001/api/kr/jongga-v2/cumulative

# 페이지네이션 테스트
curl "http://localhost:5001/api/kr/jongga-v2/cumulative?page=1&per_page=5"
```

> 💡 **검증 팁:**
> - `win_rate`가 0~100 사이인지?
> - `total` = closed + open 인지?
> - grade_stats의 A등급 win_rate가 B등급보다 높은지?

✅ **체크포인트 6-6**: 통계 데이터 산출 및 페이지네이션 정상 작동 확인

---

## 전체 API 테스트

### 프롬프트 13: 전체 테스트 스크립트

```
모든 API 엔드포인트를 테스트하는 스크립트를 만들어줘.

http://localhost:5001 에 대해:
1. GET /api/kr/health → 200 확인
2. GET /api/kr/signals → signals 배열 확인
3. GET /api/kr/jongga-v2/latest → 응답 확인
4. GET /api/kr/jongga-v2/dates → 배열 확인
5. GET /api/kr/market-gate → regime 필드 확인
6. POST /api/kr/realtime-prices → 가격 확인 (body: {"tickers": ["005930"]})
7. GET /api/kr/vcp-cumulative → stats 확인
8. GET /api/kr/jongga-v2/cumulative → stats 확인

각 API마다 통과/실패 표시해줘. 마지막에 통과/실패 개수를 출력해줘.
```

---

## 브라우저 및 확장 도구를 활용한 테스트

- **브라우저 주소창:** GET 요청 URL을 직접 입력하여 확인 가능
- **브라우저 개발자 도구 (F12 → Console):**

```javascript
// POST 테스트
fetch('http://localhost:5001/api/kr/realtime-prices', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({tickers: ["005930", "000660"]})
}).then(r => r.json()).then(console.log);

// SSE 테스트
const es = new EventSource('http://localhost:5001/api/kr/price-stream');
es.onmessage = e => console.log(JSON.parse(e.data));
```

- **VS Code REST Client:** `test.http` 파일을 생성하고 엔드포인트를 작성하여 에디터 내에서 직접 요청 전송

---

## API 엔드포인트 요약표

| #  | 메서드 | URL                                | 역할               | 캐시     |
|----|--------|------------------------------------|--------------------|----------|
| 1  | GET    | `/api/kr/health`                   | 서버 상태 확인     | -        |
| 2  | GET    | `/api/kr/signals`                  | VCP + 시그널       | 300초    |
| 3  | GET    | `/api/kr/jongga-v2/latest`         | 종가베팅 V2 최신   | 300초    |
| 4  | GET    | `/api/kr/jongga-v2/dates`          | 결과 날짜 목록     | 300초    |
| 5  | GET    | `/api/kr/jongga-v2/history/:date`  | 특정 날짜 결과     | 300초    |
| 6  | GET    | `/api/kr/market-gate`              | 시장 상태 및 섹터  | 300초    |
| 7  | POST   | `/api/kr/realtime-prices`          | 실시간 가격 조회   | -        |
| 8  | GET    | `/api/kr/price-stream`             | SSE 가격 스트림    | 5초 push |
| 9  | GET    | `/api/kr/vcp-cumulative`           | VCP 누적 성과      | 120초    |
| 10 | GET    | `/api/kr/jongga-v2/cumulative`     | 종가베팅 누적 성과 | -        |

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| Address already in use | 포트 5001 충돌 | `lsof -i :5001` → `kill -9 <PID>` |
| CORS 에러 | CORS 설정 누락/위치 오류 | `app/__init__.py`에서 Blueprint 등록 전 `CORS(app, ...)` 확인 |
| 파일을 찾을 수 없습니다 | 실행 위치가 루트가 아님 | 프로젝트 최상위 디렉토리에서 실행 |
| yfinance 에러 | 패키지 미설치 | `pip install yfinance` |
| ModuleNotFoundError: 'app' | 루트가 아닌 곳에서 실행 | `app/` 폴더가 있는 디렉토리에서 실행 |
| market-gate 응답이 느림 | 네이버 금융 크롤링 시간 | 정상 (첫 요청만 느리고, 이후 5분간 캐시) |
| bs4 import 에러 | beautifulsoup4 미설치 | `pip install beautifulsoup4` |

---

## 최종 체크리스트

- [ ] `python run.py` 정상 실행
- [ ] `/api/kr/health` 상태 200 응답
- [ ] `/api/kr/signals` 배열 응답
- [ ] `/api/kr/jongga-v2/latest` 데이터 반환
- [ ] `/api/kr/jongga-v2/dates` 배열 응답 (YYYYMMDD 형식)
- [ ] `/api/kr/market-gate` regime 상태 응답
- [ ] `/api/kr/realtime-prices` 종목 가격 응답 (POST)
- [ ] `/api/kr/price-stream` SSE 스트림 수신
- [ ] `vcp_signals.json`에 status 필드 존재 (enrich_vcp.py 실행 후)
- [ ] `daily_prices.csv` 파일 존재 (build_daily_prices.py 실행 후)
- [ ] `/api/kr/vcp-cumulative` 통계 반환
- [ ] `/api/kr/jongga-v2/cumulative` 통계 반환

**12개 중 10개 이상 통과 시 Part 6 완료입니다. (다음 파트: Next.js 대시보드 구축)**
