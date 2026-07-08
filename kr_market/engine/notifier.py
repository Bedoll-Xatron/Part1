"""텔레그램 알림 모듈."""

import json
import logging
import time

import requests
from dotenv import load_dotenv
import os

logger = logging.getLogger(__name__)


def send_telegram(text: str) -> bool:
    """텔레그램 메시지 전송. 성공 시 True, 실패 시 False."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env")
    load_dotenv(env_path, override=True)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 .env에 없습니다.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Markdown으로 먼저 시도
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }, timeout=10)

    if resp.status_code == 200:
        return True

    # Markdown 파싱 에러(400) → plain text 재전송
    if resp.status_code == 400:
        logger.warning("Markdown 파싱 실패, plain text로 재전송합니다.")
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
        }, timeout=10)
        return resp.status_code == 200

    logger.error("텔레그램 전송 실패: %s %s", resp.status_code, resp.text)
    return False


def _send_long_telegram(msg: str) -> int:
    """긴 메시지를 4000자 청크로 분할 전송. 전송된 청크 수 반환."""
    if len(msg) <= 4000:
        send_telegram(msg)
        return 1

    lines = msg.split("\n")
    chunks = []
    current = ""

    for line in lines:
        candidate = current + "\n" + line if current else line
        if len(candidate) > 4000:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)

    for i, chunk in enumerate(chunks):
        send_telegram(chunk)
        if i < len(chunks) - 1:
            time.sleep(0.5)

    return len(chunks)


def _quality_stars(quality: float) -> str:
    """품질 점수를 별점으로 변환."""
    if quality >= 80:
        return "★★★★★"
    elif quality >= 60:
        return "★★★★☆"
    elif quality >= 40:
        return "★★★☆☆"
    elif quality >= 20:
        return "★★☆☆☆"
    return "★☆☆☆☆"


def _grade_emoji(grade: str) -> str:
    """등급별 이모지."""
    return {"S": "🏆", "A": "🥇", "B": "📌"}.get(grade, "📋")


def _format_signal_detail(sig: dict) -> str:
    """S/A/B 등급 시그널을 상세 포맷."""
    score = sig["score"]
    quality = sig.get("quality", 0)
    stars = _quality_stars(quality)
    emoji = _grade_emoji(sig["grade"])

    # 수급 쌍매수 표시
    foreign = sig.get("foreign_5d", 0)
    inst = sig.get("inst_5d", 0)
    dual_buy = " 🟢" if foreign > 0 and inst > 0 else ""

    # 뉴스 헤드라인 (첫 번째)
    news_items = sig.get("news_items", [])
    news_headline = news_items[0]["title"] if news_items else "없음"

    # 테마
    themes = sig.get("themes", [])
    theme_str = ", ".join(themes) if themes else "없음"

    lines = [
        "──────────────────────",
        f"{emoji} *{sig['stock_name']}* ({sig['stock_code']}) — {sig['grade']}등급",
        "",
        f"📊 총점: {score['total']}/15 | 품질: {quality:.0f} [{stars}]",
        f"💰 현재가: {sig['current_price']:,}원 ({sig['change_pct']:+.1f}%)",
        f"🎯 매수 참고가: {sig['entry_price']:,}원",
        f"🛑 손절가: {sig['stop_price']:,}원 (-5%)",
        f"🎯 목표가: {sig['target_price']:,}원 (+15%)",
        f"📦 수량: {sig['quantity']}주 | 포지션: {sig['position_size']:,}원",
        "",
        f"📰 뉴스: {news_headline} ({score['news']}/3점)",
        f"🏷️ 테마: {theme_str}",
        f"📈 수급: 외인 {foreign:+,} / 기관 {inst:+,}{dual_buy}",
        "",
        f"[점수 상세] 뉴스{score['news']} 거래대금{score['volume']} 차트{score['chart']} 캔들{score['candle']} 수급{score['supply']} = {score['total']}",
        "──────────────────────",
    ]
    return "\n".join(lines)


def notify_signal_results() -> bool:
    """jongga_v2_latest.json을 읽어 텔레그램으로 전송."""
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "jongga_v2_latest.json")

    if not os.path.exists(data_path):
        logger.warning("결과 파일이 없습니다: %s", data_path)
        return False

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    signals = data.get("signals", [])
    date = data.get("date", "")
    total = len(signals)

    # 헤더
    lines = [
        f"🏆 *종가베팅 시그널* ({date})",
        f"총 {total}개 시그널 발견",
        "",
    ]

    # S/A/B 등급 상세, C등급 분류
    c_grade_names = []
    for sig in signals:
        if sig["grade"] in ("S", "A", "B"):
            lines.append(_format_signal_detail(sig))
            lines.append("")
        else:
            c_grade_names.append(sig["stock_name"])

    # C등급 한줄 요약
    if c_grade_names:
        lines.append(f"📋 C등급 {len(c_grade_names)}개: {', '.join(c_grade_names)}")
        lines.append("")

    # 푸터
    lines.append("💡 S=최상급 A=우수 B=보통 C=참고")
    lines.append("⚠️ 투자 참고용이며, 매매의 책임은 본인에게 있습니다.")

    msg = "\n".join(lines)
    _send_long_telegram(msg)
    return True


if __name__ == "__main__":
    # 1) 기본 전송 테스트
    print("[1/2] 기본 메시지 전송...")
    ok = send_telegram("🧪 테스트!")
    print(f"  → {'성공' if ok else '실패'}")

    # 2) 시그널 포맷팅 전송 테스트
    print("[2/2] 시그널 결과 전송...")
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "jongga_v2_latest.json")

    if not os.path.exists(data_path):
        # 가짜 시그널 데이터 생성
        print("  → jongga_v2_latest.json 없음, 가짜 데이터로 테스트")
        fake = {
            "date": "2026-03-05",
            "signals": [
                {
                    "stock_code": "005930", "stock_name": "삼성전자", "grade": "A",
                    "score": {"news": 3, "volume": 3, "chart": 2, "candle": 1,
                              "consolidation": 0, "supply": 2, "retracement": 0,
                              "pullback_support": 0, "total": 11},
                    "current_price": 95000, "entry_price": 95000,
                    "stop_price": 90250, "target_price": 109250,
                    "quantity": 10, "position_size": 950000,
                    "change_pct": 5.2, "foreign_5d": 500000, "inst_5d": 300000,
                    "quality": 75.0,
                    "news_items": [{"title": "[테스트] 삼성전자 AI 반도체 수주 급증"}],
                    "themes": ["AI반도체", "HBM"],
                },
                {
                    "stock_code": "000660", "stock_name": "SK하이닉스", "grade": "B",
                    "score": {"news": 2, "volume": 2, "chart": 1, "candle": 1,
                              "consolidation": 1, "supply": 1, "retracement": 0,
                              "pullback_support": 0, "total": 8},
                    "current_price": 220000, "entry_price": 220000,
                    "stop_price": 209000, "target_price": 253000,
                    "quantity": 5, "position_size": 1100000,
                    "change_pct": 3.8, "foreign_5d": 120000, "inst_5d": -50000,
                    "quality": 55.0,
                    "news_items": [{"title": "[테스트] HBM4 양산 본격화"}],
                    "themes": ["HBM"],
                },
                {
                    "stock_code": "035720", "stock_name": "카카오", "grade": "C",
                    "score": {"news": 1, "volume": 1, "chart": 1, "candle": 0,
                              "consolidation": 0, "supply": 0, "retracement": 0,
                              "pullback_support": 0, "total": 3},
                    "current_price": 55000, "entry_price": 55000,
                    "stop_price": 52250, "target_price": 63250,
                    "quantity": 0, "position_size": 0,
                    "change_pct": 1.2, "foreign_5d": -10000, "inst_5d": -5000,
                    "quality": 20.0,
                    "news_items": [], "themes": [],
                },
            ],
        }
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(fake, f, ensure_ascii=False, indent=2)
        ok = notify_signal_results()
        os.remove(data_path)
    else:
        print("  → 실제 데이터로 전송")
        ok = notify_signal_results()

    print(f"  → {'성공' if ok else '실패'}")
