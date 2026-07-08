"""Part 6 전체 API 엔드포인트 테스트 스크립트."""

import json
import requests

BASE = "http://localhost:5001"
results = []


def test(name, method, path, body=None, check=None):
    url = f"{BASE}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, timeout=10)
        else:
            resp = requests.post(url, json=body, timeout=10)

        data = resp.json()
        ok = resp.status_code == 200 and (check(data) if check else True)
    except Exception as e:
        ok = False
        data = str(e)

    status = "PASS" if ok else "FAIL"
    results.append(ok)
    mark = "\033[92m PASS \033[0m" if ok else "\033[91m FAIL \033[0m"
    print(f"  [{mark}] {name}")
    if not ok:
        print(f"         → {str(data)[:120]}")


print("=" * 55)
print("  Part 6 API 테스트")
print("=" * 55)
print()

test(
    "1. GET /api/kr/health",
    "GET", "/api/kr/health",
    check=lambda d: d.get("status") == "ok",
)

test(
    "2. GET /api/kr/signals",
    "GET", "/api/kr/signals",
    check=lambda d: isinstance(d.get("signals"), list),
)

test(
    "3. GET /api/kr/jongga-v2/latest",
    "GET", "/api/kr/jongga-v2/latest",
    check=lambda d: "signals" in d or "date" in d,
)

test(
    "4. GET /api/kr/jongga-v2/dates",
    "GET", "/api/kr/jongga-v2/dates",
    check=lambda d: isinstance(d.get("dates"), list),
)

test(
    "5. GET /api/kr/market-gate",
    "GET", "/api/kr/market-gate",
    check=lambda d: "regime" in d,
)

test(
    "6. POST /api/kr/realtime-prices",
    "POST", "/api/kr/realtime-prices",
    body={"tickers": ["005930"]},
    check=lambda d: isinstance(d.get("prices"), dict),
)

test(
    "7. GET /api/kr/vcp-cumulative",
    "GET", "/api/kr/vcp-cumulative",
    check=lambda d: isinstance(d.get("stats"), dict),
)

test(
    "8. GET /api/kr/jongga-v2/cumulative",
    "GET", "/api/kr/jongga-v2/cumulative",
    check=lambda d: isinstance(d.get("stats"), dict) and "signals" in d,
)

print()
print("-" * 55)
passed = sum(results)
failed = len(results) - passed
color = "\033[92m" if failed == 0 else "\033[93m"
print(f"  결과: {color}{passed}/{len(results)} 통과, {failed} 실패\033[0m")
print("-" * 55)
