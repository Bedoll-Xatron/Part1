import os
import sys
import pandas as pd
from typing import List, Dict

# 상위 폴더 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optimization.offline_data_loader import OfflineDataLoader

def calc_rsi_series(close_series: pd.Series, period: int = 14) -> float:
    if len(close_series) < period + 1:
        return 50.0
    
    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.iloc[1:period+1].mean()
    avg_loss = loss.iloc[1:period+1].mean()
    
    for i in range(period+1, len(close_series)):
        avg_gain = (avg_gain * (period - 1) + gain.iloc[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss.iloc[i]) / period
        
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

def run_contrarian_grid_search():
    print("Loading data...")
    loader = OfflineDataLoader()
    all_dates = loader.get_available_dates()
    
    split_date = '2026-04-15'
    train_dates = [d for d in all_dates if d <= split_date]
    test_dates = [d for d in all_dates if d > split_date]
    
    sampled_train_dates = train_dates[::3]  # 3일 간격 샘플링
    print(f"Train dates sampled: {len(sampled_train_dates)} dates")
    
    # ── 파라미터 그리드 정의 ──
    grid = [
        {"name": "Strict_RSI30", "rsi_thresh": 30, "prob_thresh": 0.60},
        {"name": "Base_RSI35", "rsi_thresh": 35, "prob_thresh": 0.50},
        {"name": "Loose_RSI40", "rsi_thresh": 40, "prob_thresh": 0.40},
        {"name": "VeryLoose_RSI45", "rsi_thresh": 45, "prob_thresh": 0.30},
    ]
    
    best_param = None
    best_return = -999.0
    
    print("\n--- [TRAIN] 역발상 최적화 시작 ---")
    
    for p in grid:
        total_signals = 0
        returns = []
        
        for t_date in sampled_train_dates:
            universe_df = loader.get_universe_on_date(t_date)
            # 하락 종목 필터링 (당일 하락한 종목 중에서) & 거래대금 50억 이상
            valid_df = universe_df[(universe_df['TradingValue'] >= 5_000_000_000)]
            # 실제 스크립트에서는 change_pct < 0 인 종목을 1차 필터링함 (시가-종가 또는 전일종목 기준, 여기선 간단히)
            valid_codes = valid_df['Code'].tolist()
            
            for code in valid_codes:
                slice_df = loader.get_chart_slice(code, t_date, lookback_days=40)
                if slice_df is None or len(slice_df) < 20:
                    continue
                
                # 당일 종가 & 하락 여부 대략 판별
                today_close = slice_df.iloc[-1]['close']
                if slice_df.iloc[-2]['close'] <= today_close:
                    continue  # 상승 종목 패스
                    
                rsi = calc_rsi_series(slice_df['close'], period=14)
                
                if rsi <= p["rsi_thresh"]:
                    support = slice_df['low'].tail(20).min()
                    avg_vol = slice_df['volume'].tail(20).mean()
                    vol_today = slice_df['volume'].iloc[-1]
                    
                    # 기초 확률 (간소화)
                    prob = 0.48
                    if rsi <= 15: prob = 0.90
                    elif rsi <= 20: prob = 0.82
                    elif rsi <= 25: prob = 0.74
                    elif rsi <= 30: prob = 0.66
                    elif rsi <= 35: prob = 0.58
                    
                    if support > 0 and today_close <= support * 1.03:
                        prob += 0.10
                    if avg_vol > 0 and vol_today < avg_vol * 0.7:
                        prob += 0.05
                        
                    if prob >= p["prob_thresh"]:
                        total_signals += 1
                        fwd_ret = loader.get_forward_return(code, t_date, hold_days=10)
                        if fwd_ret is not None:
                            returns.append(fwd_ret)
                            
        avg_ret = sum(returns) / len(returns) if returns else 0
        win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100 if returns else 0
        print(f"[{p['name']}] 시그널: {total_signals}개 | D10: {avg_ret:+.2f}% | 승률: {win_rate:.1f}%")
        
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
            slice_df = loader.get_chart_slice(code, t_date, lookback_days=40)
            if slice_df is None or len(slice_df) < 20:
                continue
                
            today_close = slice_df.iloc[-1]['close']
            if slice_df.iloc[-2]['close'] <= today_close:
                continue
                
            rsi = calc_rsi_series(slice_df['close'], period=14)
            
            if rsi <= best_param["rsi_thresh"]:
                support = slice_df['low'].tail(20).min()
                avg_vol = slice_df['volume'].tail(20).mean()
                vol_today = slice_df['volume'].iloc[-1]
                
                prob = 0.48
                if rsi <= 15: prob = 0.90
                elif rsi <= 20: prob = 0.82
                elif rsi <= 25: prob = 0.74
                elif rsi <= 30: prob = 0.66
                elif rsi <= 35: prob = 0.58
                
                if support > 0 and today_close <= support * 1.03: prob += 0.10
                if avg_vol > 0 and vol_today < avg_vol * 0.7: prob += 0.05
                    
                if prob >= best_param["prob_thresh"]:
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
        print("\n❌ 5% 목표 미달.")

if __name__ == '__main__':
    run_contrarian_grid_search()
