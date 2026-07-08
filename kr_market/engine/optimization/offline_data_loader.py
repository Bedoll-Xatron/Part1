import os
import pandas as pd
from typing import Dict, Optional, List

_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
_UNIVERSE_CSV = os.path.join(_DATA_DIR, 'universe_ohlcv.csv')

class OfflineDataLoader:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OfflineDataLoader, cls).__new__(cls)
            cls._instance._load_data()
        return cls._instance

    def _load_data(self):
        print(f"Loading {_UNIVERSE_CSV} into memory...")
        if not os.path.exists(_UNIVERSE_CSV):
            raise FileNotFoundError(f"Missing {_UNIVERSE_CSV}. Run fetch_universe_ohlcv.py first.")
        
        # dtype 지정으로 메모리 최적화 및 로드 속도 향상
        self.df = pd.read_csv(
            _UNIVERSE_CSV, 
            dtype={
                'Code': str, 
                'Open': float, 
                'High': float, 
                'Low': float, 
                'Close': float, 
                'Volume': float
            }
        )
        self.df['Date'] = pd.to_datetime(self.df['Date'])
        self.df.sort_values(by=['Code', 'Date'], inplace=True)
        
        # 거래대금 추정치 계산 (종가 * 거래량)
        self.df['TradingValue'] = self.df['Close'] * self.df['Volume']
        
        # 종목별로 인덱싱하여 빠른 접근
        self.stock_dict: Dict[str, pd.DataFrame] = {}
        for code, group in self.df.groupby('Code'):
            # 날짜를 인덱스로 설정
            group_indexed = group.set_index('Date').sort_index()
            self.stock_dict[code] = group_indexed
            
        print(f"Loaded {len(self.stock_dict)} stocks.")
        
        # 유니버스 캐시
        self.all_dates = sorted(self.df['Date'].dt.strftime('%Y-%m-%d').unique().tolist())

    def get_available_dates(self) -> List[str]:
        return self.all_dates
        
    def get_chart_slice(self, code: str, target_date: str, lookback_days: int = 80) -> Optional[pd.DataFrame]:
        """
        특정 종목의 target_date 기준 과거 lookback_days 만큼의 차트를 반환 (target_date 포함)
        컬럼: ['open', 'high', 'low', 'close', 'volume', 'date'] - 소문자 호환성
        """
        if code not in self.stock_dict:
            return None
            
        df_stock = self.stock_dict[code]
        # target_date 이하의 데이터만 필터링
        past_data = df_stock.loc[:target_date]
        
        if len(past_data) == 0:
            return None
            
        # 최근 lookback_days 개만 가져오기
        sliced = past_data.tail(lookback_days).copy()
        
        if len(sliced) < 20: # 최소 20일 데이터는 있어야 분석 의미가 있음
            return None
            
        # 기존 스크립트들과의 호환성을 위해 컬럼명을 소문자로 변경하고 date를 컬럼으로 복원
        sliced.reset_index(inplace=True)
        sliced['date'] = sliced['Date'].dt.strftime('%Y-%m-%d')
        sliced = sliced.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        return sliced[['date', 'open', 'high', 'low', 'close', 'volume']]

    def get_universe_on_date(self, target_date: str, min_volume_ratio_to_avg: float = 0.0) -> pd.DataFrame:
        """
        특정 날짜 기준 활성화된 전 종목의 당일 종가, 거래대금, 전일비 등 기본 정보를 반환
        """
        # target_date의 정확한 데이터
        date_dt = pd.to_datetime(target_date)
        day_data = self.df[self.df['Date'] == date_dt].copy()
        
        if day_data.empty:
            return day_data
            
        return day_data
        
    def get_forward_return(self, code: str, entry_date: str, hold_days: int = 10) -> Optional[float]:
        """
        진입일(entry_date) 다음 날 시가 진입, hold_days 이후 종가 청산 기준의 수익률 반환
        """
        if code not in self.stock_dict:
            return None
            
        df_stock = self.stock_dict[code]
        future_data = df_stock.loc[entry_date:]
        
        if len(future_data) <= hold_days:
            return None
            
        # entry_date 익일의 시가
        entry_price = future_data.iloc[1]['Open']
        if pd.isna(entry_price) or entry_price <= 0:
            return None
            
        # hold_days째 날의 종가
        exit_price = future_data.iloc[hold_days]['Close']
        
        return ((exit_price - entry_price) / entry_price) * 100.0
