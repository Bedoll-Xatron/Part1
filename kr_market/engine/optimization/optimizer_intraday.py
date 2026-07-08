import os
import sys
import pandas as pd
from typing import List, Dict

# 상위 폴더 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optimization.offline_data_loader import OfflineDataLoader

def run_intraday_grid_search():
    print("Loading data...")
    loader = OfflineDataLoader()
    all_dates = loader.get_available_dates()
    
    split_date = '2026-04-15'
    train_dates = [d for d in all_dates if d <= split_date]
    test_dates = [d for d in all_dates if d > split_date]
    
    sampled_train_dates = train_dates[::3]  # 3일 간격 샘플링
    print(f"Train dates sampled: {len(sampled_train_dates)} dates")
    
    # ── 파라미터 그리드 정의 ──
    # 장중원석 핵심 조건: 거래량 배수(vol_ratio), 당일 상승(등락률), MA20 위 (정배열)
    grid = [
        {"name": "Strict_Vol1.5", "min_vol_ratio": 1.5, "max_chg": 15.0, "req_ma20": True, "req_ma60": True},
        {"name": "Base_Vol1.0", "min_vol_ratio": 1.0, "max_chg": 15.0, "req_ma20": True, "req_ma60": False},
        {"name": "Loose_Vol0.8", "min_vol_ratio": 0.8, "max_chg": 20.0, "req_ma20": True, "req_ma60": False},
        {"name": "NoMA_Vol1.0", "min_vol_ratio": 1.0, "max_chg": 15.0, "req_ma20": False, "req_ma60": False},
    ]
    
    best_param = None
    best_return = -999.0
    
    print("\n--- [TRAIN] 장중 원석 최적화 시작 ---")
    
    for p in grid:
        total_signals = 0
        returns = []
        
        for t_date in sampled_train_dates:
            universe_df = loader.get_universe_on_date(t_date)
            # 거래대금 50억 이상, 당일 양봉(상승) 종목 위주
            valid_df = universe_df[(universe_df['TradingValue'] >= 5_000_000_000)]
            valid_codes = valid_df['Code'].tolist()
            
            for code in valid_codes:
                slice_df = loader.get_chart_slice(code, t_date, lookback_days=60)
                if slice_df is None or len(slice_df) < 60:
                    continue
                
                today = slice_df.iloc[-1]
                yesterday = slice_df.iloc[-2]
                
                # 당일 등락률 (간이 계산)
                if yesterday['close'] <= 0: continue
                chg_pct = (today['close'] - yesterday['close']) / yesterday['close'] * 100
                
                if chg_pct < 0 or chg_pct > p['max_chg']:
                    continue
                    
                # 이동평균
                ma20 = slice_df['close'].tail(20).mean()
                ma60 = slice_df['close'].tail(60).mean()
                
                if p['req_ma20'] and today['close'] < ma20: continue
                if p['req_ma60'] and today['close'] < ma60: continue
                
                # 거래량 배수
                avg_vol20 = slice_df['volume'].tail(20).mean()
                if avg_vol20 <= 0: continue
                vol_ratio = today['volume'] / avg_vol20
                
                if vol_ratio >= p['min_vol_ratio']:
                    total_signals += 1
                    fwd_ret = loader.get_forward_return(code, t_date, hold_days=5) # 단기스윙 5일
                    if fwd_ret is not None:
                        returns.append(fwd_ret)
                            
        avg_ret = sum(returns) / len(returns) if returns else 0
        win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100 if returns else 0
        print(f"[{p['name']}] 시그널: {total_signals}개 | D5: {avg_ret:+.2f}% | 승률: {win_rate:.1f}%")
        
        if avg_ret > best_return and total_signals >= 5:
            best_return = avg_ret
            best_param = p
            
    print(f"\n=> 가장 이상적인 파라미터: {best_param['name']} (평균수익 {best_return:+.2f}%)")
    
    # ── Test 구간 검증 ──
    print("\n--- [TEST] 최근 1개월 검증 시작 ---")
    test_returns = []
    test_signals = 0
    
    for t_date in test_dates:
        universe_df = loader.get_universe_on_date(t_date)
        valid_df = universe_df[(universe_df['TradingValue'] >= 5_000_000_000)]
        valid_codes = valid_df['Code'].tolist()
        
        for code in valid_codes:
            slice_df = loader.get_chart_slice(code, t_date, lookback_days=60)
            if slice_df is None or len(slice_df) < 60:
                continue
                
            today = slice_df.iloc[-1]
            yesterday = slice_df.iloc[-2]
            
            if yesterday['close'] <= 0: continue
            chg_pct = (today['close'] - yesterday['close']) / yesterday['close'] * 100
            
            if chg_pct < 0 or chg_pct > best_param['max_chg']:
                continue
                
            ma20 = slice_df['close'].tail(20).mean()
            ma60 = slice_df['close'].tail(60).mean()
            
            if best_param['req_ma20'] and today['close'] < ma20: continue
            if best_param['req_ma60'] and today['close'] < ma60: continue
            
            avg_vol20 = slice_df['volume'].tail(20).mean()
            if avg_vol20 <= 0: continue
            vol_ratio = today['volume'] / avg_vol20
            
            if vol_ratio >= best_param['min_vol_ratio']:
                test_signals += 1
                fwd_ret = loader.get_forward_return(code, t_date, hold_days=5)
                if fwd_ret is not None:
                    test_returns.append(fwd_ret)
                        
    test_avg_ret = sum(test_returns) / len(test_returns) if test_returns else 0
    test_win_rate = sum(1 for r in test_returns if r > 0) / len(test_returns) * 100 if test_returns else 0
    
    print(f"[TEST 결과] 최적 파라미터({best_param['name']}) 적용")
    print(f"시그널 수: {test_signals}개")
    print(f"D5 평균수익률: {test_avg_ret:+.2f}%")
    print(f"승률: {test_win_rate:.1f}%")
    
    if test_avg_ret >= 5.0:
        print("\n✅ 목표 달성! Test 구간 수익률 5% 이상 확인됨.")
    else:
        print("\n❌ 5% 목표 미달.")

if __name__ == '__main__':
    run_intraday_grid_search()
