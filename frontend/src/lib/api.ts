const TIMEOUT_MS = 15_000;

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(endpoint, { ...options, signal: controller.signal });
    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timer);
  }
}

export type KRSignal = {
  ticker: string;
  name: string;
  market: 'KOSPI' | 'KOSDAQ';
  signal_date: string;
  entry_price: number;
  current_price: number;
  return_pct: number;
  score: number;
  grade?: string;
  themes?: string[];
};

export type KRSignalsResponse = {
  signals: KRSignal[];
};

export type KRSector = {
  name: string;
  change_pct: number;
  signal: 'bullish' | 'neutral' | 'bearish';
};

export type KRMarketGate = {
  score: number;
  label: string;
  kospi_close: number;
  kospi_change_pct: number;
  kosdaq_close: number;
  kosdaq_change_pct: number;
  sectors: KRSector[];
};

export type BacktestSummary = {
  vcp: { status: string; count: number; win_rate: number; avg_return: number; profit_factor?: number };
  closing_bet: { status: string; count: number; win_rate: number; avg_return: number; profit_factor?: number };
};

export type KRStrategyResponse = {
  strategy: string;
  description: string;
  signals: any[];
  stats: { total: number; avg_score: number };
};

export type FlowMomentumSignal = {
  ticker: string;
  name: string;
  market: string;
  score: number;
  foreign_flow: number;
  institution_flow: number;
  volume_ratio: number;
  signal_strength: string;
};

export type NarrativeSignal = {
  ticker: string;
  name: string;
  market: string;
  score: number;
  theme: string;
  narrative_score: number;
  news_sentiment: number;
  social_momentum: number;
};

export type SectorRotationSignal = {
  ticker: string;
  name: string;
  market: string;
  score: number;
  sector: string;
  rotation_phase: string;
  relative_strength: number;
};

export type ContrarianSignal = {
  ticker: string;
  name: string;
  market: string;
  score: number;
  oversold_score: number;
  reversal_probability: number;
  support_level: number;
};

export type KRStockSearchResult = {
  ticker: string;
  name: string;
  market: string;
};

export type KRStockSummary = {
  ticker: string;
  name: string;
  market: string;
  current_price: number;
  change_pct: number;
  volume: number;
  market_cap: number;
  per: number | string;
  pbr: number;
  factors: Record<string, number>;
  signals: { vcp: boolean; closing_bet: boolean };
};

export type KRStockAISummary = {
  ticker: string;
  summary: string;
  outlook: string;
  risk_factors: string[];
  catalysts: string[];
};

export type ChartSignal = 'BUY' | 'HOLD' | 'SELL' | 'ERROR';

export type ChartAnalysisResult = {
  종목코드: string;
  종목명: string;
  시장: string;
  signal: ChartSignal;
  confidence: number;
  ma_status: string;
  rsi_zone: string;
  volume_trend: string;
  reasons: string;
};

export type ChartAnalysisStatus = {
  running: boolean;
  total: number;
  current: number;
  status: 'idle' | 'running' | 'done' | 'error';
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  pct: number;
};

export type ChartAnalysisResponse = {
  results: ChartAnalysisResult[];
  summary: Record<ChartSignal, number>;
};

export const chartAnalysisAPI = {
  run: () => fetchAPI<{ ok: boolean; message: string }>('/api/chart-analysis/run', { method: 'POST' }),
  getStatus: () => fetchAPI<ChartAnalysisStatus>('/api/chart-analysis/status'),
  getResults: () => fetchAPI<ChartAnalysisResponse>('/api/chart-analysis/results'),
  chartUrl: (ticker: string) => `/api/chart-analysis/charts/${ticker}`,
};

export const chartAnalysisUsAPI = {
  run: () => fetchAPI<{ ok: boolean; message: string }>('/api/us/chart-analysis/run', { method: 'POST' }),
  getStatus: () => fetchAPI<ChartAnalysisStatus>('/api/us/chart-analysis/status'),
  getResults: () => fetchAPI<ChartAnalysisResponse>('/api/us/chart-analysis/results'),
  chartUrl: (ticker: string) => `/api/us/chart-analysis/charts/${ticker}`,
};

export const krAPI = {
  getSignals: () => fetchAPI<KRSignalsResponse>('/api/kr/signals'),
  getMarketGate: () => fetchAPI<KRMarketGate>('/api/kr/market-gate'),
  getBacktestSummary: () => fetchAPI<BacktestSummary>('/api/kr/backtest-summary'),
  getClosingBet: () => fetch('/api/kr/jongga-v2/latest').then((r) => r.json()),
  getVCPCumulative: () => fetchAPI('/api/kr/vcp-cumulative'),
  getClosingBetCumulative: () => fetchAPI('/api/kr/jongga-v2/cumulative'),
  getStrategy: (name: string) => fetchAPI<KRStrategyResponse>(`/api/kr/strategies/${name}`),
  getBestStrategy: () => fetchAPI<KRStrategyResponse>('/api/kr/strategies/best'),
  searchStock: (query: string) => fetchAPI<KRStockSearchResult[]>(`/api/kr/stock-search?q=${query}`),
  getStockSummary: (ticker: string) => fetchAPI<KRStockSummary>(`/api/kr/stock-summary/${ticker}`),
  getStockAISummary: (ticker: string) => fetchAPI<KRStockAISummary>(`/api/kr/stock-ai-summary/${ticker}`),
  // 날짜별 히스토리
  getVCPDates: () => fetchAPI<{ dates: string[]; count: number; counts: Record<string, number> }>('/api/kr/vcp/dates'),
  getVCPHistory: (date: string) => fetchAPI<KRSignalsResponse & { generated_at: string }>(`/api/kr/vcp/history/${date}`),
  getClosingBetDates: () => fetchAPI<{ dates: string[]; count: number; counts: Record<string, number> }>('/api/kr/jongga-v2/dates'),
  getClosingBetHistory: (date: string) => fetch(`/api/kr/jongga-v2/history/${date}`).then((r) => r.json()),
  getFlowMomentumDates: () => fetchAPI<{ dates: string[]; count: number; counts: Record<string, number> }>('/api/kr/flow-momentum/dates'),
  getFlowMomentumHistory: (date: string) => fetchAPI<any>(`/api/kr/flow-momentum/history/${date}`),
  getNarrativeMomentumDates: () => fetchAPI<{ dates: string[]; count: number; counts: Record<string, number> }>('/api/kr/narrative-momentum/dates'),
  getNarrativeMomentumHistory: (date: string) => fetchAPI<any>(`/api/kr/narrative-momentum/history/${date}`),
  getSectorRotationDates: () => fetchAPI<{ dates: string[]; count: number; counts: Record<string, number> }>('/api/kr/sector-rotation/dates'),
  getSectorRotationHistory: (date: string) => fetchAPI<any>(`/api/kr/sector-rotation/history/${date}`),
  getContrarianDates: () => fetchAPI<{ dates: string[]; count: number; counts: Record<string, number> }>('/api/kr/contrarian/dates'),
  getContrarianHistory: (date: string) => fetchAPI<any>(`/api/kr/contrarian/history/${date}`),
  // 포지션 사이징
  calcPositionSize: (body: Record<string, any>) => fetchAPI<any>('/api/kr/position-size', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  // 시장 고점 탐지
  getMarketTop: () => fetchAPI<any>('/api/kr/market-top'),
  // 시그널 사후 분석
  getPostmortem: () => fetchAPI<any>('/api/kr/postmortem'),
  // PEAD / 갭 스크리너
  getPead: (params?: { min_gap?: number; min_vol?: number; lookback?: number }) => {
    const q = new URLSearchParams();
    if (params?.min_gap) q.set('min_gap', String(params.min_gap));
    if (params?.min_vol) q.set('min_vol', String(params.min_vol));
    if (params?.lookback) q.set('lookback', String(params.lookback));
    return fetchAPI<any>(`/api/kr/pead?${q}`);
  },
  // 시장 폭 분석
  getBreadth: () => fetchAPI<any>('/api/kr/breadth'),
  // FTD Detector
  getFtd: () => fetchAPI<any>('/api/kr/ftd'),
  // Backtest Expert
  getBacktestDetail: () => fetchAPI<any>('/api/kr/backtest/detail'),
  getIntradayGems: () => fetchAPI<any>('/api/kr/intraday-gems').catch(() => null),
};
