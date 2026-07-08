import csv
import time
from datetime import date, datetime
from typing import List

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib
matplotlib.rcParams["font.family"] = "Apple SD Gothic Neo"
matplotlib.rcParams["axes.unicode_minus"] = False
import requests
from bs4 import BeautifulSoup

from config import SignalConfig
from models import StockData, SupplyData, ChartData, NewsData


def _parse_int(val):
    try:
        return int(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _parse_float(val):
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _fetch_gainers(market):
    """네이버 증권 API에서 상승 종목 원본 데이터를 가져온다."""
    url = f"https://m.stock.naver.com/api/stocks/up/{market}?page=1&pageSize=100"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    results: List[StockData] = []
    for stock in data.get("stocks", []):
        close = _parse_int(stock["closePrice"])
        results.append(StockData(
            code=stock["itemCode"],
            name=stock["stockName"],
            market=market.upper(),
            open=0, high=0, low=0, close=close,
            volume=_parse_int(stock["accumulatedTradingVolume"]),
            trading_value=_parse_int(stock["accumulatedTradingValue"]) * 1_000_000,
            change_pct=_parse_float(stock["fluctuationsRatio"]),
            high_52w=0, low_52w=0,
        ))
    return results


def _apply_filter(stocks: List[StockData], config) -> List[StockData]:
    """SignalConfig 조건에 따라 종목을 필터링한다."""
    filtered = []
    for s in stocks:
        if any(kw in s.name for kw in config.exclude_keywords):
            continue
        if config.exclude_preferred and s.name.endswith("우"):
            continue
        if not (config.min_price <= s.close <= config.max_price):
            continue
        if not (config.min_change_pct <= s.change_pct <= config.max_change_pct):
            continue
        if s.trading_value < config.min_trading_value:
            continue
        filtered.append(s)
    return filtered


def get_chart_data(code, days=60) -> List[ChartData]:
    """네이버 금융에서 특정 종목의 일봉 데이터를 가져온다.

    Args:
        code: 종목코드 (6자리)
        days: 가져올 일수 (기본 60일)

    Returns:
        날짜 오름차순 ChartData 리스트
    """
    base_url = f"https://finance.naver.com/item/sise_day.naver?code={code}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": base_url,
    }

    # MA20 계산을 위해 19일치 추가로 가져옴
    need = days + 19
    rows: List[ChartData] = []
    page = 1

    while len(rows) < need:
        resp = requests.get(f"{base_url}&page={page}", headers=headers)
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="type2")
        if not table:
            break

        found = False
        for tr in table.find_all("tr"):
            cols = tr.find_all("td")
            if len(cols) < 7:
                continue
            date_text = cols[0].get_text(strip=True)
            if not date_text:
                continue
            found = True
            rows.append(ChartData(
                code=code,
                date=datetime.strptime(date_text, "%Y.%m.%d").date(),
                close=_parse_int(cols[1].get_text()),
                open=_parse_int(cols[3].get_text()),
                high=_parse_int(cols[4].get_text()),
                low=_parse_int(cols[5].get_text()),
                volume=_parse_int(cols[6].get_text()),
            ))
            if len(rows) >= need:
                break

        if not found:
            break
        page += 1
        time.sleep(0.2)

    # 날짜 오름차순 정렬
    rows.reverse()

    # 이동평균선 계산
    closes = [r.close for r in rows]
    for i, row in enumerate(rows):
        for window, attr in [(5, "ma5"), (10, "ma10"), (20, "ma20")]:
            if i >= window - 1:
                setattr(row, attr, round(sum(closes[i - window + 1 : i + 1]) / window))
            else:
                setattr(row, attr, None)

    # 요청한 일수만 반환 (MA 계산용 앞부분 제거)
    return rows[-days:]


def _judge_supply(supply: SupplyData) -> str:
    """수급 데이터로 판정을 반환한다."""
    if supply.foreign_net_5d > 0 and supply.inst_net_5d > 0:
        return "쌍매수"
    elif supply.foreign_net_5d > 0:
        return "외인매수"
    elif supply.inst_net_5d > 0:
        return "기관매수"
    return "쌍매도"


def get_supply_data(code) -> SupplyData:
    """네이버 금융에서 외국인/기관 매매 동향을 가져온다.

    Args:
        code: 종목코드 (6자리)

    Returns:
        SupplyData
    """
    base_url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": base_url,
    }

    resp = requests.get(f"{base_url}&page=1", headers=headers)
    resp.encoding = "euc-kr"
    soup = BeautifulSoup(resp.text, "html.parser")

    # 두 번째 type2 테이블이 일별 외국인/기관 데이터
    tables = soup.find_all("table", class_="type2")
    if len(tables) < 2:
        return SupplyData(code=code, foreign_net_5d=0, inst_net_5d=0, foreign_hold_pct=0.0)

    table = tables[1]
    rows = []

    # 컬럼: 날짜(0) 종가(1) 전일비(2) 등락률(3) 거래량(4) 기관(5) 외국인(6) 보유주수(7) 보유율(8)
    for tr in table.find_all("tr"):
        cols = tr.find_all("td")
        if len(cols) < 9:
            continue
        date_text = cols[0].get_text(strip=True)
        if not date_text:
            continue

        rows.append({
            "기관순매수": _parse_int(cols[5].get_text()),
            "외국인순매수": _parse_int(cols[6].get_text()),
            "외국인보유율": cols[8].get_text(strip=True),
        })

        if len(rows) >= 5:
            break

    foreign_5d = sum(r["외국인순매수"] for r in rows)
    inst_5d = sum(r["기관순매수"] for r in rows)
    hold_pct = _parse_float(rows[0]["외국인보유율"].replace("%", "")) if rows else 0.0

    return SupplyData(
        code=code,
        foreign_net_5d=foreign_5d,
        inst_net_5d=inst_5d,
        foreign_hold_pct=hold_pct,
    )


def _fetch_news_body(url, max_chars=500):
    """뉴스 URL에서 본문 텍스트를 가져온다."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    try:
        # 1단계: finance.naver.com → 리다이렉트 URL 추출
        resp = requests.get(url, headers=headers, timeout=3)
        for encoding in ("cp949", "utf-8"):
            try:
                html = resp.content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            html = resp.content.decode("utf-8", errors="replace")

        soup = BeautifulSoup(html, "html.parser")

        # 리다이렉트 스크립트에서 실제 URL 추출
        script = soup.find("script")
        if script and "top.location.href" in script.get_text():
            real_url = script.get_text().split("'")[1]
        else:
            real_url = None

        # 2단계: 실제 뉴스 페이지에서 본문 추출
        if real_url:
            time.sleep(0.3)
            resp2 = requests.get(real_url, headers=headers, timeout=3)
            for encoding in ("utf-8", "cp949"):
                try:
                    html2 = resp2.content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                html2 = resp2.content.decode("utf-8", errors="replace")
            soup = BeautifulSoup(html2, "html.parser")

        # 본문 추출 (#dic_area가 네이버 뉴스 표준)
        body = soup.select_one("#dic_area") or soup.select_one("#newsct_article")
        if not body:
            return ""

        text = body.get_text(separator=" ", strip=True)
        return text[:max_chars] + ("..." if len(text) > max_chars else "")

    except (requests.RequestException, Exception):
        return ""


def get_stock_news(code, stock_name="", limit=3) -> List[NewsData]:
    """네이버 금융에서 특정 종목의 최신 뉴스를 가져온다.

    Args:
        code: 종목코드 (6자리)
        stock_name: 종목명 (표시용)
        limit: 가져올 뉴스 수 (기본 3건)

    Returns:
        List[NewsData]
    """
    base_url = f"https://finance.naver.com/item/news_news.naver?code={code}&page=1"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": f"https://finance.naver.com/item/main.naver?code={code}",
    }

    resp = requests.get(base_url, headers=headers, timeout=3)
    resp.encoding = "euc-kr"
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.find("table", class_="type5")
    if not table:
        return []

    results: List[NewsData] = []
    for tr in table.find_all("tr"):
        cols = tr.find_all("td")
        if len(cols) != 3:
            continue

        a_tag = cols[0].find("a")
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        if not title or title == "제목":
            continue

        href = a_tag.get("href", "")
        url = f"https://finance.naver.com{href}" if href else ""

        # 본문 가져오기
        time.sleep(0.3)
        body = _fetch_news_body(url) if url else ""

        # 날짜 파싱
        date_str = cols[2].get_text(strip=True)
        try:
            pub_dt = datetime.strptime(date_str, "%Y.%m.%d %H:%M")
        except ValueError:
            pub_dt = datetime.now()

        results.append(NewsData(
            code=code,
            title=title,
            source=cols[1].get_text(strip=True),
            published_at=pub_dt,
            url=url or None,
            summary=body,
        ))

        if len(results) >= limit:
            break

    return results


def plot_chart(chart: List[ChartData], name, code):
    """종목 차트를 캔들스틱 + 이동평균 + 거래량으로 그린다.

    Args:
        chart: get_chart_data()가 반환한 리스트
        name: 종목명
        code: 종목코드
    """
    dates = [r.date for r in chart]
    opens = [r.open for r in chart]
    highs = [r.high for r in chart]
    lows = [r.low for r in chart]
    closes = [r.close for r in chart]
    volumes = [r.volume for r in chart]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 8), height_ratios=[3, 1],
        sharex=True, gridspec_kw={"hspace": 0.05},
    )
    fig.suptitle(f"{name} ({code}) 일봉 차트", fontsize=14, fontweight="bold")

    # 캔들스틱
    width = 0.6
    for i, d in enumerate(dates):
        color = "#e74c3c" if closes[i] >= opens[i] else "#3498db"
        # 몸통
        body_bottom = min(opens[i], closes[i])
        body_height = abs(closes[i] - opens[i])
        ax1.bar(d, body_height, bottom=body_bottom, width=width, color=color, edgecolor=color)
        # 꼬리
        ax1.vlines(d, lows[i], highs[i], color=color, linewidth=0.8)

    # 이동평균선
    for attr, label, color, lw in [("ma5", "MA5", "#f39c12", 1.0), ("ma10", "MA10", "#2ecc71", 1.0), ("ma20", "MA20", "#9b59b6", 1.2)]:
        vals = [(dates[i], getattr(chart[i], attr)) for i in range(len(chart)) if getattr(chart[i], attr) is not None]
        if vals:
            ax1.plot([v[0] for v in vals], [v[1] for v in vals], label=label, color=color, linewidth=lw)

    ax1.legend(loc="upper left", fontsize=9)
    ax1.set_ylabel("Price (KRW)")
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    # 거래량
    colors = ["#e74c3c" if closes[i] >= opens[i] else "#3498db" for i in range(len(dates))]
    ax2.bar(dates, volumes, width=width, color=colors, alpha=0.7)
    ax2.set_ylabel("Volume")
    ax2.grid(True, alpha=0.3)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x / 1_000_000:.1f}M" if x >= 1_000_000 else f"{x:,.0f}"))

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.xticks(rotation=45)
    plt.tight_layout()

    filename = f"chart_{code}.png"
    fig.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  => {filename} 저장 완료")
    return filename


def analyze_stock(code, name=""):
    """종목의 기술적 분석 결과를 반환한다.

    Args:
        code: 종목코드 (6자리)
        name: 종목명 (표시용)

    Returns:
        dict: 정배열, 52주최고가, 52주최저가, MA5, MA10, MA20, 현재가위치(%)
    """
    chart = get_chart_data(code, days=250)

    # 52주 고가/저가 (고가의 max, 저가의 min)
    high_52w = max(r.high for r in chart)
    low_52w = min(r.low for r in chart)

    # 최근 날짜 기준 이동평균
    latest = chart[-1]
    ma5 = latest.ma5
    ma10 = latest.ma10
    ma20 = latest.ma20

    # 정배열 판단: MA5 > MA10 > MA20
    if ma5 is not None and ma10 is not None and ma20 is not None:
        정배열 = ma5 > ma10 > ma20
    else:
        정배열 = False

    # 52주 범위 내 현재 위치 (%)
    price = latest.close
    if high_52w != low_52w:
        position_52w = round((price - low_52w) / (high_52w - low_52w) * 100, 1)
    else:
        position_52w = 100.0

    return {
        "종목명": name,
        "종목코드": code,
        "현재가": price,
        "MA5": ma5,
        "MA10": ma10,
        "MA20": ma20,
        "정배열": 정배열,
        "52주최고": high_52w,
        "52주최저": low_52w,
        "52주위치": position_52w,
    }


def get_top_gainers(market="KOSPI", config=None) -> List[StockData]:
    """네이버 증권 API에서 상승 종목을 가져오고 필터링한다.

    Args:
        market: "KOSPI" 또는 "KOSDAQ"
        config: SignalConfig 인스턴스 (None이면 필터 미적용)

    Returns:
        List[StockData]
    """
    stocks = _fetch_gainers(market.upper())

    if config is None:
        return stocks

    before = len(stocks)
    stocks = _apply_filter(stocks, config)
    after = len(stocks)
    print(f"  [{market.upper()}] 필터 전: {before}개 → 필터 후: {after}개 ({before - after}개 제외)")

    return stocks


def generate_report():
    """전체 분석 리포트를 생성하고 텍스트 파일로 저장한다."""
    from collections import Counter
    from datetime import date

    today = date.today().strftime("%Y-%m-%d")
    config = SignalConfig()
    lines = []

    def log(text=""):
        print(text)
        lines.append(text)

    # ──────────────────────────────────────────────
    # 1. 헤더
    # ──────────────────────────────────────────────
    log("=" * 90)
    log(f"  상승 종목 종합 분석 리포트  |  {today}")
    log("=" * 90)

    # ──────────────────────────────────────────────
    # 2. 종목 수집 & 필터링
    # ──────────────────────────────────────────────
    log(f"\n[1] 종목 수집 & 필터링")
    log("-" * 90)
    log(f"  필터 조건: 등락률 {config.min_change_pct}~{config.max_change_pct}% | "
        f"가격 {config.min_price:,}~{config.max_price:,}원 | "
        f"거래대금 {config.min_trading_value / 100_000_000:,.0f}억 이상")
    log(f"  제외: ETF/ETN/스팩/우선주/리츠/인버스/레버리지\n")

    kospi = get_top_gainers("KOSPI", config)
    kosdaq = get_top_gainers("KOSDAQ", config)

    combined = sorted(kospi + kosdaq, key=lambda x: x.change_pct, reverse=True)
    log(f"\n  총 후보: {len(combined)}개 (KOSPI {len(kospi)} + KOSDAQ {len(kosdaq)})")

    # ──────────────────────────────────────────────
    # 3. 종합 분석 (차트 + 수급 + 뉴스)
    # ──────────────────────────────────────────────
    log(f"\n[2] 종합 분석 진행 중 ({len(combined)}개 종목)...\n")

    analyses = []
    for i, stock in enumerate(combined, 1):
        name = stock.name
        code = stock.code
        print(f"  [{i}/{len(combined)}] {name} ({code}) 분석 중...")

        result = analyze_stock(code, name)
        result["시장"] = stock.market
        result["등락률"] = stock.change_pct
        result["거래대금(억)"] = round(stock.trading_value / 100_000_000, 1)

        supply = get_supply_data(code)
        result["외국인5일"] = supply.foreign_net_5d
        result["기관5일"] = supply.inst_net_5d
        result["수급판정"] = _judge_supply(supply)
        result["외국인보유율"] = f"{supply.foreign_hold_pct:.2f}%"

        result["뉴스"] = get_stock_news(code, name, limit=3)
        analyses.append(result)

    # ──────────────────────────────────────────────
    # 4. 종합 분석표
    # ──────────────────────────────────────────────
    log(f"\n[3] 종합 분석표")
    log("=" * 120)
    log(
        f"{'#':>2} {'시장':<6} {'종목명':<14} {'코드':<8} "
        f"{'현재가':>10} {'등락률':>7} {'거래대금':>9} "
        f"{'정배열':>4} {'52주위치':>7} "
        f"{'외국인5일':>12} {'기관5일':>12} {'수급판정':>8}"
    )
    log("=" * 120)

    for i, a in enumerate(analyses, 1):
        배열 = "O" if a["정배열"] else "X"
        log(
            f"{i:>2} {a['시장']:<6} {a['종목명']:<14} {a['종목코드']:<8} "
            f"{a['현재가']:>10,} {a['등락률']:>+6.1f}% {a['거래대금(억)']:>8.1f}억 "
            f"{'  ' + 배열:>4} {a['52주위치']:>6.1f}% "
            f"{a['외국인5일']:>+12,} {a['기관5일']:>+12,} {a['수급판정']:>8}"
        )

    정배열_count = sum(1 for a in analyses if a["정배열"])
    판정_counts = Counter(a["수급판정"] for a in analyses)
    log("=" * 120)
    log(
        f"  정배열: {정배열_count}/{len(analyses)}개 | "
        + " | ".join(f"{k}: {v}개" for k, v in 판정_counts.most_common())
    )

    # ──────────────────────────────────────────────
    # 5. 종목별 상세 (뉴스 포함)
    # ──────────────────────────────────────────────
    log(f"\n[4] 종목별 상세 분석")

    for i, a in enumerate(analyses, 1):
        배열 = "정배열" if a["정배열"] else "역배열"
        log(f"\n{'─' * 90}")
        log(f"  {i}. {a['종목명']} ({a['종목코드']})  |  {a['시장']}")
        log(f"{'─' * 90}")
        log(f"  현재가: {a['현재가']:>10,}원   등락률: {a['등락률']:>+.2f}%   거래대금: {a['거래대금(억)']:,.1f}억")
        log(f"  MA5: {a['MA5']:,}  MA10: {a['MA10']:,}  MA20: {a['MA20']:,}  → {배열}")
        log(f"  52주 최고: {a['52주최고']:,}  최저: {a['52주최저']:,}  현재 위치: {a['52주위치']}%")
        log(f"  외국인 5일: {a['외국인5일']:+,}  기관 5일: {a['기관5일']:+,}  외인보유율: {a['외국인보유율']}  → {a['수급판정']}")
        log(f"  ┌{'─' * 86}┐")
        log(f"  │ 최신 뉴스{' ' * 76}│")
        if a["뉴스"]:
            for j, n in enumerate(a["뉴스"], 1):
                제목 = n.title[:50] + ("..." if len(n.title) > 50 else "")
                날짜 = n.published_at.strftime("%Y.%m.%d %H:%M")
                log(f"  │  {j}. [{n.source:<6}] {제목:<58} {날짜} │")
        else:
            log(f"  │  뉴스 없음{' ' * 74}│")
        log(f"  └{'─' * 86}┘")

    # ──────────────────────────────────────────────
    # 6. 요약
    # ──────────────────────────────────────────────
    쌍매수_정배열 = [a for a in analyses if a["수급판정"] == "쌍매수" and a["정배열"]]
    외인_정배열 = [a for a in analyses if a["수급판정"] == "외인매수" and a["정배열"]]

    log(f"\n{'=' * 90}")
    log(f"  [5] 핵심 요약")
    log(f"{'=' * 90}")
    log(f"  분석일: {today}")
    log(f"  총 후보: {len(analyses)}개  |  정배열: {정배열_count}개  |  " +
        " | ".join(f"{k}: {v}개" for k, v in 판정_counts.most_common()))

    if 쌍매수_정배열:
        log(f"\n  ** 정배열 + 쌍매수 (외국인/기관 동시 매수) **")
        for a in 쌍매수_정배열:
            log(f"    - {a['종목명']} ({a['종목코드']}) | {a['현재가']:,}원 | +{a['등락률']}% | 52주위치 {a['52주위치']}%")

    if 외인_정배열:
        log(f"\n  ** 정배열 + 외국인 매수 **")
        for a in 외인_정배열:
            log(f"    - {a['종목명']} ({a['종목코드']}) | {a['현재가']:,}원 | +{a['등락률']}% | 52주위치 {a['52주위치']}%")

    log(f"\n{'=' * 90}")

    # ──────────────────────────────────────────────
    # 파일 저장
    # ──────────────────────────────────────────────

    # 리포트 텍스트 저장
    report_filename = f"report_{today}.txt"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n=> {report_filename} 저장 완료")

    # 분석 결과 CSV 저장
    analysis_filename = "analysis_result.csv"
    fieldnames = [
        "시장", "종목명", "종목코드", "현재가", "등락률", "거래대금(억)",
        "MA5", "MA10", "MA20", "정배열", "52주최고", "52주최저", "52주위치",
        "외국인5일누적", "기관5일누적", "외국인보유율", "수급판정",
    ]
    with open(analysis_filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for a in analyses:
            writer.writerow({
                "시장": a["시장"], "종목명": a["종목명"], "종목코드": a["종목코드"],
                "현재가": a["현재가"], "등락률": a["등락률"], "거래대금(억)": a["거래대금(억)"],
                "MA5": a["MA5"], "MA10": a["MA10"], "MA20": a["MA20"],
                "정배열": a["정배열"], "52주최고": a["52주최고"], "52주최저": a["52주최저"],
                "52주위치": a["52주위치"], "외국인5일누적": a["외국인5일"],
                "기관5일누적": a["기관5일"], "외국인보유율": a["외국인보유율"],
                "수급판정": a["수급판정"],
            })
    print(f"=> {analysis_filename} 저장 완료 ({len(analyses)}건)")


if __name__ == "__main__":
    generate_report()
