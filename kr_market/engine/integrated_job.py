"""
통합 전략 실행 및 상위 종목 텔레그램 알림 스크립트
==================================================
1. 모든 전략 스캐너를 순차적으로 실행 (VCP, 종가베팅, 수급, 테마, 섹터, 역발상)
2. 각 결과에서 상위 3종목씩 추출
3. 통합된 리스트를 텔레그램으로 전송
"""

import os
import sys
import json
import subprocess
import logging
from datetime import datetime

# 로거 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 경로 설정
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ENGINE_DIR, '..', 'data')
sys.path.insert(0, ENGINE_DIR)

from notifier import send_telegram

def run_script(script_name, args=None):
    """외부 파이썬 스크립트 실행 및 결과 스트리밍"""
    script_path = os.path.join(ENGINE_DIR, script_name)
    cmd = [sys.executable, "-u", script_path] # -u for unbuffered output
    if args:
        cmd.extend(args)
    
    logger.info(f"--- 실행 시작: {script_name} ---")
    try:
        # 개별 스크립트 내부의 텔레그램 전송을 막기 위해 --no-telegram 인자 추가
        # stdout/stderr를 실시간으로 출력하기 위해 subprocess.Popen 사용
        process = subprocess.Popen(
            cmd + ["--no-telegram"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='cp949',  # Windows 한글 환경 대응 (CP949)
            errors='replace',  # 디코딩 에러 발생 시 물음표 등으로 대체하여 중단 방지
            bufsize=1
        )
        
        for line in process.stdout:
            print(f"  [{script_name}] {line}", end="")
            
        process.wait()
        logger.info(f"--- 실행 완료: {script_name} (Exit Code {process.returncode}) ---")
        return process.returncode == 0
    except Exception as e:
        logger.error(f"{script_name} 실행 중 예외 발생: {e}")
        return False

def get_top_3(filename, strategy_name):
    """JSON 결과 파일에서 상위 3종목 추출"""
    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        logger.warning(f"파일을 찾을 수 없음: {filename}")
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        signals = data.get('signals', [])
        if not signals:
            return []

        # 전략별 상위 추출 및 포맷팅
        top_3 = []
        
        if strategy_name == "VCP":
            # A, B 등급 위주
            sorted_sigs = sorted(signals, key=lambda x: ({"A":0, "B":1, "C":2, "D":3}.get(x.get('grade','D'), 9), -x.get('score', 0)))
            for s in sorted_sigs[:3]:
                top_3.append(f"[{s['grade']}] {s['name']} (점수:{s['score']})")
                
        elif strategy_name == "종가베팅":
            # S, A 등급 위주
            sorted_sigs = sorted(signals, key=lambda x: ({"S":0, "A":1, "B":2, "C":3}.get(x.get('grade','C'), 9), -x.get('score', {}).get('total', 0)))
            for s in sorted_sigs[:3]:
                top_3.append(f"[{s['grade']}] {s['stock_name']} (점수:{s['score']['total']})")
                
        elif strategy_name == "수급 모멘텀":
            # strong 위주
            sorted_sigs = sorted(signals, key=lambda x: (0 if x.get('signal_strength')=='strong' else 1, -x.get('score', 0)))
            for s in sorted_sigs[:3]:
                top_3.append(f"[{s['signal_strength'][:1].upper()}] {s['name']} ({s['score']}점, 외:{s['foreign_flow']:.0f}억)")
                
        elif strategy_name == "테마 모멘텀":
            sorted_sigs = sorted(signals, key=lambda x: -x.get('narrative_score', 0))
            for s in sorted_sigs[:3]:
                top_3.append(f"{s['name']} (점수:{s['narrative_score']:.1f}, {s['theme'][:10]})")
                
        elif strategy_name == "섹터 로테이션":
            # markup 위주
            sorted_sigs = sorted(signals, key=lambda x: (0 if x.get('rotation_phase')=='markup' else 1, -x.get('relative_strength', 0)))
            for s in sorted_sigs[:3]:
                top_3.append(f"[{s['rotation_phase'][:1].upper()}] {s['name']} ({s['sector']}, RS:{s['relative_strength']:.1f})")
                
        elif strategy_name == "역발상":
            sorted_sigs = sorted(signals, key=lambda x: -x.get('reversal_prob', 0))
            for s in sorted_sigs[:3]:
                top_3.append(f"{s['name']} (반전확률:{s['reversal_prob']:.0f}%, 점수:{s['score']})")

        return top_3
    except Exception as e:
        logger.error(f"{strategy_name} 자료 분석 중 에러: {e}")
        return []

def main():
    logger.info("필터링 및 알림 통합 작업 시작")
    
    # 1. 모든 전략 스크립트 실행
    strategies = [
        ("vcp_scanner.py", "VCP"),
        ("run_engine.py", "종가베팅"),
        ("run_flow_momentum.py", "수급 모멘텀"),
        ("run_narrative_momentum.py", "테마 모멘텀"),
        ("run_sector_rotation.py", "섹터 로테이션"),
        ("run_contrarian_reversal.py", "역발상")
    ]
    
    for script, name in strategies:
        run_script(script)
    
    # 2. 결과 집계
    results_map = [
        ("vcp_signals.json", "VCP"),
        ("jongga_v2_latest.json", "종가베팅"),
        ("flow_momentum_latest.json", "수급 모멘텀"),
        ("narrative_momentum_latest.json", "테마 모멘텀"),
        ("sector_rotation_latest.json", "섹터 로테이션"),
        ("contrarian_latest.json", "역발상")
    ]
    
    report_lines = [
        f"🚀 *MarketFlow 전략별 상위 3선* ({datetime.now().strftime('%Y-%m-%d')})",
        "──────────────────────"
    ]
    
    found_any = False
    for filename, name in results_map:
        top_list = get_top_3(filename, name)
        if top_list:
            found_any = True
            report_lines.append(f"📌 *{name}*")
            for i, line in enumerate(top_list, 1):
                report_lines.append(f"  {i}. {line}")
            report_lines.append("")
    
    if not found_any:
        report_lines.append("포착된 시그널이 없습니다.")
    
    report_lines.append("──────────────────────")
    report_lines.append("💡 상세 내용은 대시보드를 확인하세요.")
    
    # 3. 텔레그램 전송
    msg = "\n".join(report_lines)
    logger.info("텔레그램 전송 중...")
    if send_telegram(msg):
        logger.info("알림 전송 성공!")
    else:
        logger.error("알림 전송 실패")

if __name__ == "__main__":
    main()
