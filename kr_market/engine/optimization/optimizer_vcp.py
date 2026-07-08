import os
import sys
import pandas as pd
from typing import List, Dict

# 상위 폴더 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optimization.offline_data_loader import OfflineDataLoader
from vcp_detector import detect_vcp, VCPResult
from config import VCPConfig, VCPGradeParams

def run_vcp_grid_search():
    print("Loading data...")
    loader = OfflineDataLoader()
    all_dates = loader.get_available_dates()
    
    # Train/Test Split (2026-04-15 기준)
    split_date = '2026-04-15'
    train_dates = [d for d in all_dates if d <= split_date]
    test_dates = [d for d in all_dates if d > split_date]
    
    # 계산량을 줄이기 위해 매주 금요일(또는 일주일 간격)로 샘플링하여 Train 수행
    # 전체를 다 돌리면 너무 오래 걸립니다.
    sampled_train_dates = train_dates[::5] 
    
    print(f"Train dates sampled: {len(sampled_train_dates)} dates (up to {split_date})")
    print(f"Test dates: {len(test_dates)} dates")
    
    # ── 파라미터 그리드 정의 ──
    # 기본 VCP는 4개 등급이 있지만, 여기서는 A등급 조건(최적의 돌파) 하나만 두고
    # 그 조건의 파라미터를 변경하며 테스트합니다.
    grid = [
        {"name": "Strict_HighR", "r12": 1.5, "r23": 1.2, "trend": "STRICT", "desc": True},
        {"name": "Strict_Base", "r12": 1.2, "r23": 1.15, "trend": "STRICT", "desc": True},
        {"name": "Loose_Base", "r12": 1.1, "r23": 1.05, "trend": "ABOVE_MA20", "desc": False},
        {"name": "VeryLoose", "r12": 1.05, "r23": 1.02, "trend": "ABOVE_MA60", "desc": False},
    ]
    
    best_param = None
    best_return = -999.0
    
    print("\n--- [TRAIN] 파라미터 최적화 시작 ---")
    results = []
    
    for p in grid:
        config = VCPConfig()
        # A등급만 남기고 나머지는 탐색하지 않도록 꼼수 세팅
        test_grade = VCPGradeParams(
            min_r12=p["r12"],
            min_r23=p["r23"],
            require_descending_highs=p["desc"],
            require_ascending_lows=False,
            trend_mode=p["trend"]
        )
        config.grade_a = test_grade
        # B, C, D는 불가능한 수치로 덮어씌워서 무시
        config.grade_b = VCPGradeParams(99, 99, True, True, "STRICT")
        config.grade_c = VCPGradeParams(99, 99, True, True, "STRICT")
        config.grade_d = VCPGradeParams(99, 99, True, True, "STRICT")
        
        total_signals = 0
        returns = []
        
        for t_date in sampled_train_dates:
            universe_df = loader.get_universe_on_date(t_date)
            # 거래대금 100억 이상 종목만 필터링해서 연산 속도 확보
            valid_codes = universe_df[universe_df['TradingValue'] >= 10_000_000_000]['Code'].tolist()
            
            for code in valid_codes:
                slice_df = loader.get_chart_slice(code, t_date, lookback_days=80)
                if slice_df is None or len(slice_df) < 60:
                    continue
                    
                res = detect_vcp(slice_df, config)
                if res.detected and res.grade == "A":
                    total_signals += 1
                    fwd_ret = loader.get_forward_return(code, t_date, hold_days=10)
                    if fwd_ret is not None:
                        returns.append(fwd_ret)
        
        avg_ret = sum(returns) / len(returns) if returns else 0
        win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100 if returns else 0
        
        print(f"[{p['name']}] 시그널: {total_signals}개 | D10 평균수익률: {avg_ret:+.2f}% | 승률: {win_rate:.1f}%")
        
        if avg_ret > best_return and total_signals >= 10:
            best_return = avg_ret
            best_param = p
            
    print(f"\n=> 가장 이상적인 파라미터: {best_param['name']} (평균수익 {best_return:+.2f}%)")
    
    # ── Test 구간 검증 ──
    print("\n--- [TEST] 최근 1개월 검증 시작 ---")
    config = VCPConfig()
    test_grade = VCPGradeParams(
        min_r12=best_param["r12"],
        min_r23=best_param["r23"],
        require_descending_highs=best_param["desc"],
        require_ascending_lows=False,
        trend_mode=best_param["trend"]
    )
    config.grade_a = test_grade
    config.grade_b = VCPGradeParams(99, 99, True, True, "STRICT")
    config.grade_c = VCPGradeParams(99, 99, True, True, "STRICT")
    config.grade_d = VCPGradeParams(99, 99, True, True, "STRICT")
    
    test_returns = []
    test_signals = 0
    
    for t_date in test_dates:
        universe_df = loader.get_universe_on_date(t_date)
        valid_codes = universe_df[universe_df['TradingValue'] >= 10_000_000_000]['Code'].tolist()
        
        for code in valid_codes:
            slice_df = loader.get_chart_slice(code, t_date, lookback_days=80)
            if slice_df is None or len(slice_df) < 60:
                continue
                
            res = detect_vcp(slice_df, config)
            if res.detected and res.grade == "A":
                test_signals += 1
                fwd_ret = loader.get_forward_return(code, t_date, hold_days=10)
                if fwd_ret is not None:
                    test_returns.append(fwd_ret)
                    
    test_avg_ret = sum(test_returns) / len(test_returns) if test_returns else 0
    test_win_rate = sum(1 for r in test_returns if r > 0) / len(test_returns) * 100 if test_returns else 0
    
    print(f"[TEST 결과] 최적 파라미터({best_param['name']}) 적용")
    print(f"시그널 수: {test_signals}개")
    print(f"D10 평균수익률: {test_avg_ret:+.2f}%")
    print(f"승률: {test_win_rate:.1f}%")
    
    if test_avg_ret >= 5.0:
        print("\n✅ 목표 달성! Test 구간 수익률 5% 이상 확인됨.")
    else:
        print("\n❌ 5% 목표 미달. 다른 전략이나 파라미터 확장이 필요합니다.")

if __name__ == '__main__':
    run_vcp_grid_search()
