"""실제 네이버 데이터 + Gemini LLM으로 Scorer 전체 파이프라인을 실행한다."""
import asyncio
import os
import time
from datetime import date
from pathlib import Path

from config import SignalConfig
from collectors import get_top_gainers, get_chart_data, get_supply_data, get_stock_news
from llm_analyzer import GeminiAnalyzer
from scorer import Scorer


def bar(val, mx, width=5):
    filled = round(val / mx * width) if mx > 0 else 0
    return "█" * filled + "░" * (width - filled)


def fmt_value(tv):
    if tv >= 1_000_000_000_000:
        return f"{tv / 1_000_000_000_000:.1f}조"
    return f"{tv / 100_000_000:,.0f}억"


def icon(v):
    return "✅" if v else "❌"


def _grade_style(grade_val):
    if grade_val == "A":
        return "linear-gradient(135deg, #065f46, #34d399)", "#34d399"
    if grade_val == "B":
        return "linear-gradient(135deg, #78350f, #fbbf24)", "#fbbf24"
    return "linear-gradient(135deg, #7f1d1d, #f87171)", "#f87171"


def _bar_pct(val, mx):
    return round(val / mx * 100, 1) if mx > 0 else 0


def _bar_color(val, mx):
    ratio = val / mx if mx > 0 else 0
    if ratio >= 0.67:
        return "linear-gradient(90deg,#065f46,#34d399)"
    if ratio >= 0.34:
        return "linear-gradient(90deg,#78350f,#fbbf24)"
    if val > 0:
        return "linear-gradient(90deg,#7f1d1d,#f87171)"
    return "#1a1a1a"


def _pts_color(val, mx):
    ratio = val / mx if mx > 0 else 0
    if ratio >= 0.67:
        return "#34d399"
    if ratio >= 0.34:
        return "#fbbf24"
    if val > 0:
        return "#f87171"
    return "#444"


def _esc(text):
    """HTML-escape a string."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _quality_label(q):
    if q >= 80:
        return "매우 우수"
    if q >= 60:
        return "우수"
    if q >= 40:
        return "보통"
    return "미흡"


def _cl_item(passed, text, detail=None):
    """Generate a checklist item HTML."""
    if passed:
        icon_cls, icon_char, text_cls = "ci-pass", "✓", "cl-text on"
    else:
        icon_cls, icon_char, text_cls = "ci-fail", "–", "cl-text"
    html = f'<div class="cl-item"><div class="cl-icon {icon_cls}">{icon_char}</div><span class="{text_cls}">{_esc(text)}</span></div>\n'
    if detail:
        html += f'<div class="cl-detail">{_esc(detail)}</div>\n'
    return html


def _fmt_supply(val):
    if val >= 0:
        return f"+{val:,}"
    return f"{val:,}"


def generate_html(results, today):
    """결과 리스트를 받아 scoring_checklist.html 콘텐츠를 생성한다."""
    cards_html = ""

    for r in results:
        stock = r["stock"]
        sc = r["score"]
        cl = r["checklist"]
        grade = r["grade"]
        quality = r["quality"]
        supply = r["supply"]
        llm = r["llm_result"]

        g = grade.value
        grade_bg, grade_color = _grade_style(g)

        # ── 카드 1: 스코어링 결과 ──
        # 뉴스 태그
        news_tags = ""
        if sc.llm_reason:
            news_tags += f'<span class="tag tg">{_esc(sc.llm_reason[:40])}</span>'
        themes = llm.get("themes", [])
        for t in themes[:3]:
            news_tags += f'<span class="tag tb">{_esc(t)}</span>'

        # 거래대금 태그
        vol_tags = f'<span class="tag tg">{_esc(fmt_value(stock.trading_value))}</span>'

        # 차트 태그
        chart_tags = ""
        if cl.ma_aligned:
            chart_tags += '<span class="tag tg">정배열</span>'
        else:
            chart_tags += '<span class="tag tx">정배열 —</span>'
        if cl.is_new_high:
            chart_tags += '<span class="tag tg">신고가 근접</span>'
        elif cl.is_breakout:
            chart_tags += '<span class="tag tg">돌파</span>'
        else:
            chart_tags += '<span class="tag tx">신고가 —</span>'

        # 캔들 태그
        candle_tags = ""
        if cl.good_candle:
            candle_tags += '<span class="tag tg">좋은 캔들</span>'
        if cl.upper_wick_long:
            candle_tags += '<span class="tag tr">윗꼬리 김</span>'
        else:
            candle_tags += '<span class="tag tg">윗꼬리 짧음</span>'

        # 수급 태그
        supply_tags = ""
        if supply:
            if supply.foreign_net_5d > 0:
                supply_tags += f'<span class="tag tg">외국인 순매수</span>'
            elif supply.foreign_net_5d < 0:
                supply_tags += f'<span class="tag tr">외국인 순매도</span>'
            if supply.inst_net_5d > 0:
                supply_tags += f'<span class="tag tg">기관 순매수</span>'
            elif supply.inst_net_5d < 0:
                supply_tags += f'<span class="tag tr">기관 순매도</span>'
            if sc.supply == 2:
                supply_tags += '<span class="tag tb">쌍매수</span>'

        # 보너스 태그
        bonus_val = sc.retracement + sc.pullback_support
        bonus_tags = ""
        if sc.retracement:
            bonus_tags += '<span class="tag tg">조정폭 회복</span>'
        else:
            bonus_tags += '<span class="tag tx">조정폭 회복 —</span>'
        if sc.pullback_support:
            bonus_tags += '<span class="tag tg">되돌림 지지</span>'
        else:
            bonus_tags += '<span class="tag tx">되돌림 지지 —</span>'

        # 등급 설명
        grade_desc = {"A": "A등급 (9점 이상)", "B": "B등급 (7~8점)", "C": "C등급 (6점 이하)"}

        # 필수 조건 텍스트
        mandatory_text = "PASS" if sc.mandatory_passed else "FAIL"
        mandatory_color = "#34d399" if sc.mandatory_passed else "#f87171"

        score_rows = [
            ("뉴스/재료", sc.news, 3, news_tags),
            ("거래대금", sc.volume, 3, vol_tags),
            ("차트 패턴", sc.chart, 3, chart_tags),
            ("캔들 형태", sc.candle, 1, candle_tags),
            ("기간 조정", sc.consolidation, 1, ""),
            ("수급", sc.supply, 2, supply_tags),
            ("보너스", bonus_val, 2, bonus_tags),
        ]

        rows_html = ""
        for label, val, mx, tags in score_rows:
            pct = _bar_pct(val, mx)
            color = _bar_color(val, mx)
            pc = _pts_color(val, mx)
            rows_html += f'''  <div class="row">
    <div class="row-label">{label}</div>
    <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color};"></div></div>
    <div class="row-pts" style="color:{pc};">{val}/{mx}</div>
  </div>
'''
            if tags:
                rows_html += f'  <div class="tags">{tags}</div>\n'

        card1 = f'''<div class="card">
  <div class="header">
    <div>
      <h1>{_esc(stock.name)}</h1>
      <span class="code">{_esc(stock.code)} · {_esc(stock.market)} · {stock.change_pct:+.1f}%</span>
    </div>
    <div class="grade" style="background:{grade_bg};color:#0a0a0a;">{g}</div>
  </div>

  <div class="summary">
    <div class="sum-box">
      <div class="lbl">총점</div>
      <div class="val" style="color:{grade_color};">{sc.total}<span>/15</span></div>
      <div class="sub">{grade_desc.get(g, "")}</div>
    </div>
    <div class="sum-box">
      <div class="lbl">품질 점수</div>
      <div class="val" style="color:#60a5fa;">{quality:.0f}<span>/100</span></div>
      <div class="sub">{_quality_label(quality)}</div>
    </div>
    <div class="sum-box">
      <div class="lbl">필수 조건</div>
      <div class="val" style="color:{mandatory_color};">{mandatory_text}</div>
      <div class="sub">뉴스 + 거래대금</div>
    </div>
  </div>

  <div class="section-title">점수 상세</div>
{rows_html}</div>'''

        # ── 카드 2: 체크리스트 ──
        checklist_html = ""

        # 필수 조건
        checklist_html += '<div class="cl-group">필수 조건 (미통과 시 자동 C등급)</div>\n'
        news_detail = f'{_esc(sc.llm_reason[:50])} — {sc.news}/3점' if sc.llm_reason else f'{sc.news}/3점'
        checklist_html += _cl_item(cl.has_news, "뉴스/재료 확인됨", news_detail)
        vol_detail = f'{_esc(fmt_value(stock.trading_value))} (기준: 500억 이상) — {sc.volume}/3점'
        checklist_html += _cl_item(cl.volume_sufficient, "거래대금 충족", vol_detail)

        # 기술적 분석
        checklist_html += '<div class="cl-group">기술적 분석</div>\n'
        checklist_html += _cl_item(cl.ma_aligned, "이평선 정배열 (close > MA5 > MA10 > MA20)")
        checklist_html += _cl_item(cl.is_new_high, "52주 신고가 근접 (현재가 ≥ 고가의 95%)")
        if not cl.is_new_high:
            checklist_html += _cl_item(cl.is_breakout, "60일 고가 돌파")
        checklist_html += _cl_item(cl.good_candle, "좋은 캔들 — 장대양봉, body 비율 높음")
        checklist_html += _cl_item(not cl.upper_wick_long, "윗꼬리 짧음 — 매도 압력 낮음")
        checklist_html += _cl_item(cl.has_consolidation, "기간조정 후 돌파",
                                   None if cl.has_consolidation else "최근 20일 횡보 + 돌파 조건 미충족")

        # 수급
        checklist_html += '<div class="cl-group">수급</div>\n'
        if supply:
            checklist_html += _cl_item(supply.foreign_net_5d > 0,
                                       f'외국인 5일 순매수 {_fmt_supply(supply.foreign_net_5d)}')
            checklist_html += _cl_item(supply.inst_net_5d > 0,
                                       f'기관 5일 순매수 {_fmt_supply(supply.inst_net_5d)}')
            sup_label = "쌍매수" if sc.supply == 2 else ("한쪽 매수" if sc.supply == 1 else "매수 없음")
            checklist_html += _cl_item(sc.supply >= 1, f'{sup_label} 확인 — 수급 {sc.supply}/2점')
        else:
            checklist_html += _cl_item(False, "수급 데이터 없음")

        # 보너스
        checklist_html += '<div class="cl-group">보너스 패턴</div>\n'
        checklist_html += _cl_item(cl.has_consolidation, "기간조정 후 돌파 패턴",
                                   None if cl.has_consolidation else "최근 20일 횡보 + 돌파 조건 미충족")
        checklist_html += _cl_item(cl.retracement_recovery, "조정폭 50% 회복",
                                   None if cl.retracement_recovery else "최근 10일 내 3% 이상 조정 후 반등 패턴 없음")
        checklist_html += _cl_item(cl.pullback_support_confirmed, "되돌림 지지 확인",
                                   None if cl.pullback_support_confirmed else "돌파 후 이전 저항선에서 지지 패턴 없음")

        # 부정적 조건
        checklist_html += '<div class="cl-group">부정적 조건</div>\n'
        checklist_html += _cl_item(not cl.negative_news, "부정적 뉴스 없음")

        # 품질 점수 산출 내역
        checklist_html += f'<div class="cl-group">품질 점수 산출 내역 ({quality:.0f}/100)</div>\n'

        # 수급 점수
        if sc.supply >= 2:
            checklist_html += _cl_item(True, "수급 — 쌍매수 +30점")
        elif sc.supply == 1:
            checklist_html += _cl_item(True, "수급 — 한쪽 매수 +15점")
        else:
            checklist_html += _cl_item(False, "수급 — 0점")

        # 총점 기반
        if sc.total >= 10:
            checklist_html += _cl_item(True, f"총점 {sc.total}점 — +25점")
        elif sc.total >= 9:
            checklist_html += _cl_item(True, f"총점 {sc.total}점 — +20점")
        elif sc.total >= 8:
            checklist_html += _cl_item(True, f"총점 {sc.total}점 — +15점")
        elif sc.total >= 7:
            checklist_html += _cl_item(True, f"총점 {sc.total}점 — +10점")
        else:
            checklist_html += _cl_item(False, f"총점 {sc.total}점 — +0점")

        # 당일 상승률
        chg = abs(stock.change_pct)
        if chg <= 5:
            q_chg = 20
        elif chg <= 10:
            q_chg = 15
        elif chg <= 15:
            q_chg = 10
        elif chg <= 20:
            q_chg = 5
        else:
            q_chg = 0
        chg_detail = "5% 이내면 +20점 가능" if q_chg < 20 else None
        checklist_html += _cl_item(q_chg > 0, f"당일 상승률 {stock.change_pct:+.1f}% — +{q_chg}점", chg_detail)

        # 인사이트
        total_pass = sum([
            cl.has_news, cl.volume_sufficient, cl.ma_aligned, cl.is_new_high or cl.is_breakout,
            cl.good_candle, not cl.upper_wick_long, cl.has_consolidation,
            cl.supply_positive, cl.retracement_recovery, cl.pullback_support_confirmed,
        ])
        total_items = 10
        fail_count = total_items - total_pass

        fail_items = []
        if not cl.has_consolidation:
            fail_items.append("기간조정")
        if not cl.retracement_recovery:
            fail_items.append("조정폭 회복")
        if not cl.pullback_support_confirmed:
            fail_items.append("되돌림 지지")
        if not cl.ma_aligned:
            fail_items.append("정배열")
        if not (cl.is_new_high or cl.is_breakout):
            fail_items.append("신고가/돌파")

        fail_str = ", ".join(fail_items[:5]) if fail_items else "없음"

        insight_html = f'''<div class="insight">
    <div class="insight-icon">💡</div>
    <div>
      <p>
        총점 <span class="hl-g">{sc.total}/15</span>으로 <span class="hl-{g.lower() if g == "A" else ("y" if g == "B" else "r")}">{g}등급</span> 달성.
        필수 조건(뉴스+거래대금) {"모두 통과" if sc.mandatory_passed else '<span class="hl-r">미통과</span>'}.<br>
        품질 점수 <span class="hl-{"g" if quality >= 70 else ("y" if quality >= 40 else "r")}">{quality:.0f}점</span>은 {_quality_label(quality)}.'''

        if fail_items:
            insight_html += f'''<br>
        <span class="hl-r">미충족 {len(fail_items)}개</span>: {_esc(fail_str)}'''

        insight_html += '''
      </p>
    </div>
  </div>'''

        card2 = f'''<div class="cl-card">
  <h2>완료 점검 체크리스트 — {_esc(stock.name)}</h2>
{checklist_html}
  {insight_html}
</div>'''

        cards_html += f"\n{card1}\n\n{card2}\n"

    # 전체 HTML 조립
    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>스코어링 체크리스트 — {_esc(today)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0a0a0a;
    color: #e0e0e0;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 20px;
    gap: 40px;
  }}

  .date-header {{
    font-size: 14px; color: #555; letter-spacing: 1px;
    text-transform: uppercase; margin-bottom: -20px;
  }}

  .card {{
    background: #141414;
    border: 1px solid #222;
    border-radius: 24px;
    padding: 44px 52px 40px;
    max-width: 780px;
    width: 100%;
  }}

  .header {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 28px; padding-bottom: 20px; border-bottom: 1px solid #222;
  }}
  .header h1 {{ font-size: 24px; font-weight: 800; }}
  .header .code {{ font-size: 13px; color: #666; }}
  .grade {{
    width: 64px; height: 64px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 32px; font-weight: 900;
    color: #0a0a0a; box-shadow: 0 0 20px rgba(52,211,153,0.25);
  }}

  .summary {{ display: flex; gap: 14px; margin-bottom: 32px; }}
  .sum-box {{
    flex: 1; background: #1a1a1a; border: 1px solid #2a2a2a;
    border-radius: 14px; padding: 16px 20px; text-align: center;
  }}
  .sum-box .lbl {{ font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }}
  .sum-box .val {{ font-size: 26px; font-weight: 800; }}
  .sum-box .val span {{ font-size: 14px; color: #555; }}
  .sum-box .sub {{ font-size: 11px; color: #555; margin-top: 2px; }}

  .section-title {{
    font-size: 13px; font-weight: 700; color: #666;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px;
  }}
  .row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
  .row-label {{ width: 80px; font-size: 13px; color: #ccc; font-weight: 600; text-align: right; flex-shrink: 0; }}
  .bar-track {{
    flex: 1; height: 30px; background: #1a1a1a; border-radius: 8px;
    overflow: hidden; position: relative;
  }}
  .bar-fill {{
    height: 100%; border-radius: 8px;
    display: flex; align-items: center; padding-left: 10px;
    font-size: 11px; font-weight: 700; color: #0a0a0a;
  }}
  .row-pts {{ width: 38px; font-size: 13px; font-weight: 800; text-align: center; flex-shrink: 0; }}
  .tags {{ display: flex; flex-wrap: wrap; gap: 5px; margin: 0 0 8px 92px; }}
  .tag {{
    font-size: 10px; font-weight: 600; padding: 3px 9px; border-radius: 10px;
    display: inline-flex; align-items: center; gap: 3px;
  }}
  .tg {{ background: #052e16; color: #34d399; }}
  .ty {{ background: #1a1508; color: #fbbf24; }}
  .tr {{ background: #1a0a0a; color: #f87171; }}
  .tb {{ background: #0c1a3a; color: #60a5fa; }}
  .tx {{ background: #1a1a1a; color: #555; }}

  .cl-card {{
    background: #141414; border: 1px solid #222; border-radius: 24px;
    padding: 44px 52px 40px; max-width: 780px; width: 100%;
  }}
  .cl-card h2 {{ font-size: 20px; font-weight: 800; margin-bottom: 24px; }}
  .cl-group {{
    font-size: 11px; font-weight: 700; color: #666;
    text-transform: uppercase; letter-spacing: 1px;
    margin: 18px 0 10px; padding-top: 14px; border-top: 1px solid #1a1a1a;
  }}
  .cl-group:first-of-type {{ margin-top: 0; padding-top: 0; border-top: none; }}
  .cl-item {{ display: flex; align-items: center; gap: 12px; padding: 7px 0; font-size: 14px; }}
  .cl-icon {{
    width: 24px; height: 24px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 800; flex-shrink: 0;
  }}
  .ci-pass {{ background: #052e16; color: #34d399; }}
  .ci-fail {{ background: #1a1a1a; color: #444; }}
  .ci-warn {{ background: #1a0a0a; color: #f87171; }}
  .cl-text {{ color: #888; }}
  .cl-text.on {{ color: #e0e0e0; }}
  .cl-detail {{ font-size: 12px; color: #555; margin-left: 36px; padding-bottom: 2px; }}

  .insight {{
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 14px;
    padding: 20px 24px; margin-top: 24px; display: flex; gap: 14px;
  }}
  .insight-icon {{ font-size: 20px; flex-shrink: 0; }}
  .insight p {{ font-size: 13px; color: #999; line-height: 1.7; }}
  .hl-g {{ color: #34d399; font-weight: 700; }}
  .hl-y {{ color: #fbbf24; font-weight: 700; }}
  .hl-r {{ color: #f87171; font-weight: 700; }}
  .hl-a {{ color: #34d399; font-weight: 700; }}
  .hl-b {{ color: #fbbf24; font-weight: 700; }}
  .hl-c {{ color: #f87171; font-weight: 700; }}
</style>
</head>
<body>

<div class="date-header">📊 스코어링 결과 — {_esc(today)}</div>
{cards_html}
</body>
</html>'''

    return html


async def run():
    config = SignalConfig()
    scorer = Scorer(config)
    analyzer = GeminiAnalyzer()
    today = date.today().strftime("%Y-%m-%d")

    print("=" * 70)
    print(f"  📊 실전 스코어링 (LLM 연동)  |  {today}")
    print("=" * 70)

    # 1. 종목 수집
    print("\n[1] 종목 수집 중...")
    kospi = get_top_gainers("KOSPI", config)
    kosdaq = get_top_gainers("KOSDAQ", config)
    combined = sorted(kospi + kosdaq, key=lambda x: x.change_pct, reverse=True)
    print(f"  총 {len(combined)}개 종목 (KOSPI {len(kospi)} + KOSDAQ {len(kosdaq)})")

    if not combined:
        print("\n  ⚠️  필터 조건에 맞는 종목이 없습니다.")
        return

    targets = combined[:5]
    print(f"  상위 {len(targets)}개 종목 분석 시작\n")

    results = []

    for i, stock in enumerate(targets, 1):
        print(f"  [{i}/{len(targets)}] {stock.name} ({stock.code})")

        # 차트 데이터 (60일)
        print(f"    차트 수집...")
        charts = get_chart_data(stock.code, days=60)
        time.sleep(0.3)

        # 수급 데이터
        print(f"    수급 수집...")
        supply = get_supply_data(stock.code)
        time.sleep(0.3)

        # 52주 고가/저가 & OHLC 보완
        if charts:
            stock.high_52w = max(c.high for c in charts)
            stock.low_52w = min(c.low for c in charts)
            latest = charts[-1]
            if stock.open == 0:
                stock.open = latest.open
            if stock.high == 0:
                stock.high = latest.high
            if stock.low == 0:
                stock.low = latest.low

        # 뉴스 수집 (3건)
        print(f"    뉴스 수집...")
        news = get_stock_news(stock.code, stock.name, limit=3)
        time.sleep(0.3)

        # LLM 분석
        print(f"    LLM 분석 중...")
        news_items = [{"title": n.title, "summary": n.summary} for n in news]
        llm_result = await analyzer.analyze_news(stock.name, news_items)
        llm_score = llm_result.get("score", 0)
        llm_source = llm_result.get("source", "?")
        print(f"    → LLM 점수: {llm_score}/3 ({llm_source}) - {llm_result.get('reason', '')[:40]}")

        # 스코어링
        score, checklist = scorer.calculate(stock, charts, news, supply, llm_result)
        grade = scorer.determine_grade(stock, score)
        quality = scorer.calculate_quality(stock, charts, score)

        results.append({
            "stock": stock,
            "charts": charts,
            "supply": supply,
            "news": news,
            "llm_result": llm_result,
            "score": score,
            "checklist": checklist,
            "grade": grade,
            "quality": quality,
        })

        # Rate limit
        if i < len(targets):
            await asyncio.sleep(2)

    # 2. 결과 요약
    print("\n" + "=" * 70)
    print(f"  📋 스코어링 결과 요약")
    print("=" * 70)
    print(f"  {'#':>2}  {'등급':>2}  {'종목명':<12} {'총점':>5} {'품질':>6}  {'뉴스':>4}  {'거래대금':>8}  {'수급':>4}  {'정배열':>4}")
    print("-" * 70)

    for i, r in enumerate(results, 1):
        s = r["stock"]
        sc = r["score"]
        g = r["grade"].value
        q = r["quality"]
        cl = r["checklist"]
        sup = "쌍매수" if sc.supply == 2 else ("한쪽" if sc.supply == 1 else "없음")
        ma = "O" if cl.ma_aligned else "X"
        print(f"  {i:>2}   {g}   {s.name:<12} {sc.total:>3}/15 {q:>5.1f}/100  {sc.news:>2}/3  {fmt_value(s.trading_value):>8}  {sup:>4}    {ma}")

    # 3. 종목별 상세
    for i, r in enumerate(results, 1):
        s = r["stock"]
        sc = r["score"]
        cl = r["checklist"]
        g = r["grade"]
        q = r["quality"]
        llm = r["llm_result"]

        print(f"\n{'=' * 70}")
        print(f"  📊 {s.name} ({s.code})  |  {s.market}  |  {s.change_pct:+.1f}%")
        print(f"{'=' * 70}")

        print(f"\n  [점수 상세] ({sc.total}/15점)")
        items = [
            ("뉴스/재료", sc.news, 3),
            ("거래대금 ", sc.volume, 3),
            ("차트 패턴", sc.chart, 3),
            ("캔들 형태", sc.candle, 1),
            ("기간 조정", sc.consolidation, 1),
            ("수급     ", sc.supply, 2),
            ("조정 회복", sc.retracement, 1),
            ("되돌림  ", sc.pullback_support, 1),
        ]
        for name, val, mx in items:
            extra = ""
            if name.strip() == "뉴스/재료" and sc.llm_reason:
                extra = f'  "{sc.llm_reason[:35]}"'
            print(f"    {name}:  {bar(val, mx)} {val}/{mx}{extra}")

        print(f"\n  [등급] {g.value} (총점 {sc.total}점)")
        print(f"  [품질] {q}/100")

        print(f"\n  [체크리스트]")
        print(f"    필수: {icon(cl.has_news)} 뉴스  {icon(cl.volume_sufficient)} 거래대금({fmt_value(s.trading_value)})")
        print(f"    차트: {icon(cl.ma_aligned)} 정배열  {icon(cl.is_new_high)} 신고가  {icon(cl.is_breakout)} 돌파")
        print(f"    캔들: {icon(cl.good_candle)} 좋은캔들  {icon(not cl.upper_wick_long)} 윗꼬리짧음")
        print(f"    수급: {icon(cl.supply_positive)} 수급양호 ({sc.supply}점)")
        print(f"    보너스: {icon(cl.has_consolidation)} 기간조정  {icon(cl.retracement_recovery)} 조정회복  {icon(cl.pullback_support_confirmed)} 되돌림지지")

        themes = llm.get("themes", [])
        if themes:
            print(f"\n  [테마] {', '.join(themes)}")

        if r["news"]:
            print(f"\n  [뉴스]")
            for n in r["news"]:
                print(f"    - [{n.source}] {n.title[:50]}")

    # 4. 최종 요약
    a_count = sum(1 for r in results if r["grade"].value == "A")
    b_count = sum(1 for r in results if r["grade"].value == "B")
    c_count = sum(1 for r in results if r["grade"].value == "C")

    print(f"\n{'=' * 70}")
    print(f"  🏁 최종 요약  |  A: {a_count}개  B: {b_count}개  C: {c_count}개")
    print(f"{'=' * 70}")

    for r in sorted(results, key=lambda x: x["score"].total, reverse=True):
        s = r["stock"]
        sc = r["score"]
        g = r["grade"].value
        q = r["quality"]
        reason = sc.llm_reason[:30] if sc.llm_reason else "-"
        print(f"  [{g}] {s.name:<12} {sc.total:>2}/15  품질 {q:>5.1f}  {reason}")

    print(f"{'=' * 70}")

    # 5. HTML 리포트 저장
    out_dir = Path(__file__).resolve().parent.parent / "시각화_결과물"
    out_dir.mkdir(parents=True, exist_ok=True)

    html = generate_html(results, today)
    (out_dir / "scoring_checklist.html").write_text(html, encoding="utf-8")
    print(f"\n  📄 {out_dir / 'scoring_checklist.html'} 저장 완료")

    # 6. 웹 대시보드 저장
    dash = generate_dashboard(results, today)
    (out_dir / "웹대시보드.html").write_text(dash, encoding="utf-8")
    print(f"  📄 {out_dir / '웹대시보드.html'} 저장 완료")


def generate_dashboard(results, today):
    """결과 리스트를 받아 반응형 웹 대시보드 HTML을 생성한다."""

    total = len(results)
    a_cnt = sum(1 for r in results if r["grade"].value == "A")
    b_cnt = sum(1 for r in results if r["grade"].value == "B")
    c_cnt = sum(1 for r in results if r["grade"].value == "C")

    # 테마 수집 및 그룹핑
    theme_count = {}
    for r in results:
        for t in r["llm_result"].get("themes", []):
            theme_count[t] = theme_count.get(t, 0) + 1
    sorted_themes = sorted(theme_count.items(), key=lambda x: x[1], reverse=True)

    # 종목 카드 생성
    stock_cards = ""
    for r in sorted(results, key=lambda x: x["score"].total, reverse=True):
        s = r["stock"]
        sc = r["score"]
        g = r["grade"].value
        q = r["quality"]
        cl = r["checklist"]

        if g == "A":
            g_color, g_bg, border = "#34d399", "rgba(52,211,153,0.12)", "#065f46"
        elif g == "B":
            g_color, g_bg, border = "#fbbf24", "rgba(251,191,36,0.12)", "#78350f"
        else:
            g_color, g_bg, border = "#f87171", "rgba(248,113,113,0.12)", "#7f1d1d"

        # 태그
        tags = []
        if cl.ma_aligned:
            tags.append("정배열")
        if cl.is_new_high:
            tags.append("신고가")
        elif cl.is_breakout:
            tags.append("돌파")
        if sc.supply == 2:
            tags.append("쌍매수")
        elif sc.supply == 1:
            tags.append("수급↑")
        if cl.good_candle:
            tags.append("양봉")
        if cl.retracement_recovery:
            tags.append("조정회복")
        if cl.pullback_support_confirmed:
            tags.append("되돌림지지")

        tags_html = ""
        for t in tags[:4]:
            tags_html += f'<span class="stag">{_esc(t)}</span>'

        # 점수 바
        pct = round(sc.total / 15 * 100)

        # LLM 이유
        reason = _esc(sc.llm_reason[:35]) if sc.llm_reason else ""

        stock_cards += f'''
    <div class="stock-card" style="border-left:3px solid {g_color};">
      <div class="sc-top">
        <div>
          <div class="sc-name">{_esc(s.name)}</div>
          <div class="sc-code">{_esc(s.code)} · {_esc(s.market)} · {s.change_pct:+.1f}%</div>
        </div>
        <div class="sc-grade" style="background:{g_bg};color:{g_color};">{g}</div>
      </div>
      <div class="sc-scores">
        <div class="sc-total"><span style="color:{g_color};">{sc.total}</span>/15</div>
        <div class="sc-bar-track"><div class="sc-bar-fill" style="width:{pct}%;background:{g_color};"></div></div>
        <div class="sc-quality">Q {q:.0f}</div>
      </div>
      <div class="sc-detail">
        <span>뉴스 {sc.news}/3</span>
        <span>거래대금 {sc.volume}/3</span>
        <span>차트 {sc.chart}/3</span>
        <span>수급 {sc.supply}/2</span>
      </div>
      <div class="sc-tags">{tags_html}</div>
      {"<div class='sc-reason'>" + reason + "</div>" if reason else ""}
    </div>'''

    # 테마 태그 생성
    theme_colors = ["#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#f87171",
                    "#fb923c", "#38bdf8", "#c084fc", "#4ade80", "#facc15"]
    themes_html = ""
    for i, (theme, cnt) in enumerate(sorted_themes[:10]):
        color = theme_colors[i % len(theme_colors)]
        themes_html += f'<span class="theme-tag" style="border-color:{color};color:{color};">{_esc(theme)} ({cnt})</span>\n'

    # 상위 종목 요약
    top_stocks = sorted(results, key=lambda x: x["score"].total, reverse=True)[:3]
    top_html = ""
    for r in top_stocks:
        s = r["stock"]
        sc = r["score"]
        g = r["grade"].value
        g_color = "#34d399" if g == "A" else ("#fbbf24" if g == "B" else "#f87171")
        top_html += f'''
      <div class="top-item">
        <span class="top-grade" style="color:{g_color};">{g}</span>
        <span class="top-name">{_esc(s.name)}</span>
        <span class="top-score">{sc.total}/15</span>
      </div>'''

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>주식 시그널 대시보드 — {_esc(today)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0a0a0a; color: #e0e0e0;
    padding: 0; min-height: 100vh;
  }}

  /* Header */
  .dash-header {{
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
    border-bottom: 1px solid #1e293b;
    padding: 24px 32px;
    display: flex; justify-content: space-between; align-items: center;
    flex-wrap: wrap; gap: 16px;
  }}
  .dash-title {{ font-size: 20px; font-weight: 800; }}
  .dash-date {{ font-size: 13px; color: #64748b; margin-top: 2px; }}
  .dash-stats {{ display: flex; gap: 12px; flex-wrap: wrap; }}
  .stat-box {{
    background: rgba(255,255,255,0.04); border: 1px solid #1e293b;
    border-radius: 10px; padding: 10px 18px; text-align: center; min-width: 80px;
  }}
  .stat-box .sv {{ font-size: 22px; font-weight: 800; }}
  .stat-box .sl {{ font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }}

  .main {{ max-width: 1200px; margin: 0 auto; padding: 28px 24px; }}

  /* Summary row */
  .summary-row {{
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px;
    margin-bottom: 28px;
  }}
  .sum-card {{
    background: #141414; border: 1px solid #222; border-radius: 14px;
    padding: 20px;
  }}
  .sum-card h3 {{ font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }}

  /* Top stocks */
  .top-item {{ display: flex; align-items: center; gap: 10px; padding: 6px 0; }}
  .top-grade {{ font-size: 16px; font-weight: 900; width: 24px; }}
  .top-name {{ flex: 1; font-size: 14px; }}
  .top-score {{ font-size: 13px; color: #888; font-weight: 700; }}

  /* Grade distribution */
  .grade-dist {{ display: flex; gap: 10px; }}
  .gd-box {{ flex: 1; text-align: center; padding: 12px 8px; border-radius: 10px; }}
  .gd-box .gd-label {{ font-size: 24px; font-weight: 900; }}
  .gd-box .gd-count {{ font-size: 11px; color: #888; margin-top: 2px; }}

  /* Themes */
  .theme-tag {{
    display: inline-block; padding: 4px 12px; border-radius: 14px;
    font-size: 12px; font-weight: 600; margin: 3px 4px;
    border: 1px solid; background: transparent;
  }}

  /* Stock cards grid */
  .grid-title {{
    font-size: 14px; font-weight: 700; color: #888; text-transform: uppercase;
    letter-spacing: 0.5px; margin: 28px 0 14px;
  }}
  .stock-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 14px;
  }}
  .stock-card {{
    background: #141414; border: 1px solid #222; border-radius: 14px;
    padding: 20px; transition: border-color 0.2s;
  }}
  .stock-card:hover {{ border-color: #444; }}
  .sc-top {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }}
  .sc-name {{ font-size: 16px; font-weight: 800; }}
  .sc-code {{ font-size: 11px; color: #666; margin-top: 2px; }}
  .sc-grade {{
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; font-weight: 900;
  }}
  .sc-scores {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }}
  .sc-total {{ font-size: 14px; font-weight: 800; min-width: 40px; }}
  .sc-total span {{ font-size: 18px; }}
  .sc-bar-track {{ flex: 1; height: 8px; background: #1a1a1a; border-radius: 4px; overflow: hidden; }}
  .sc-bar-fill {{ height: 100%; border-radius: 4px; }}
  .sc-quality {{ font-size: 12px; color: #888; font-weight: 700; }}
  .sc-detail {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; font-size: 11px; color: #555; }}
  .sc-detail span {{ background: #1a1a1a; padding: 2px 8px; border-radius: 6px; }}
  .sc-tags {{ display: flex; gap: 5px; flex-wrap: wrap; }}
  .stag {{
    font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 8px;
    background: #052e16; color: #34d399;
  }}
  .sc-reason {{ font-size: 11px; color: #666; margin-top: 8px; font-style: italic; }}

  /* Footer */
  .footer {{
    text-align: center; padding: 32px 0; font-size: 11px; color: #333;
    border-top: 1px solid #1a1a1a; margin-top: 40px;
  }}

  /* Responsive */
  @media (max-width: 700px) {{
    .summary-row {{ grid-template-columns: 1fr; }}
    .stock-grid {{ grid-template-columns: 1fr; }}
    .dash-header {{ padding: 16px; }}
    .main {{ padding: 16px; }}
  }}
</style>
</head>
<body>

<div class="dash-header">
  <div>
    <div class="dash-title">📊 주식 시그널 대시보드</div>
    <div class="dash-date">{_esc(today)} · 등락률 상위 {total}개 종목 분석</div>
  </div>
  <div class="dash-stats">
    <div class="stat-box">
      <div class="sv">{total}</div>
      <div class="sl">분석</div>
    </div>
    <div class="stat-box">
      <div class="sv" style="color:#34d399;">{a_cnt}</div>
      <div class="sl">A등급</div>
    </div>
    <div class="stat-box">
      <div class="sv" style="color:#fbbf24;">{b_cnt}</div>
      <div class="sl">B등급</div>
    </div>
    <div class="stat-box">
      <div class="sv" style="color:#f87171;">{c_cnt}</div>
      <div class="sl">C등급</div>
    </div>
  </div>
</div>

<div class="main">

  <!-- 요약 3칸 -->
  <div class="summary-row">
    <div class="sum-card">
      <h3>상위 종목</h3>
      {top_html}
    </div>
    <div class="sum-card">
      <h3>등급 분포</h3>
      <div class="grade-dist">
        <div class="gd-box" style="background:rgba(52,211,153,0.08);">
          <div class="gd-label" style="color:#34d399;">{a_cnt}</div>
          <div class="gd-count">A등급</div>
        </div>
        <div class="gd-box" style="background:rgba(251,191,36,0.08);">
          <div class="gd-label" style="color:#fbbf24;">{b_cnt}</div>
          <div class="gd-count">B등급</div>
        </div>
        <div class="gd-box" style="background:rgba(248,113,113,0.08);">
          <div class="gd-label" style="color:#f87171;">{c_cnt}</div>
          <div class="gd-count">C등급</div>
        </div>
      </div>
    </div>
    <div class="sum-card">
      <h3>🤖 AI 발견 테마</h3>
      <div>{themes_html if themes_html else '<span style="color:#555;">테마 없음</span>'}</div>
    </div>
  </div>

  <!-- 종목 카드 그리드 -->
  <div class="grid-title">종목별 상세 ({total}개)</div>
  <div class="stock-grid">
    {stock_cards}
  </div>

  <div class="footer">
    Part1 주식 시그널 분석 시스템 — {_esc(today)} 자동 생성
  </div>
</div>

</body>
</html>'''

    return html


if __name__ == "__main__":
    asyncio.run(run())
