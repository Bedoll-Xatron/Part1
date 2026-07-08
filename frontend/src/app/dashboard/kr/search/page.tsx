'use client';

import { useEffect, useState } from 'react';
import { krAPI, KRStockSearchResult, KRStockSummary, KRStockAISummary } from '@/lib/api';

/* ── 유틸 ────────────────────────────────────────────────────── */

const FACTOR_LABELS: Record<string, string> = {
  news:             '뉴스/재료',
  volume:           '거래대금',
  chart:            '차트패턴',
  candle:           '캔들형태',
  consolidation:    '기간조정',
  supply:           '수급',
  retracement:      '조정폭',
  pullback_support: '되돌림지지',
};

function fmtPrice(n: number): string {
  return n.toLocaleString('ko-KR');
}

function fmtCap(n: number): string {
  if (n >= 1_000_000_000_000) {
    const jo  = Math.floor(n / 1_000_000_000_000);
    const eok = Math.floor((n % 1_000_000_000_000) / 100_000_000);
    return eok > 0 ? `${jo}조 ${eok}억` : `${jo}조`;
  }
  if (n >= 100_000_000) return `${Math.floor(n / 100_000_000)}억`;
  return n.toLocaleString('ko-KR');
}

function fmtVol(n: number): string {
  if (n >= 10_000) return `${(n / 10_000).toFixed(1)}만`;
  return n.toLocaleString('ko-KR');
}

function fmtPer(v: number | string): string {
  if (typeof v === 'number') return v > 0 ? v.toFixed(1) : 'N/A';
  return v || 'N/A';
}

/* ── FactorBar ───────────────────────────────────────────────── */

function FactorBar({ label, value, maxValue }: { label: string; value: number; maxValue: number }) {
  const pct = maxValue > 0 ? (value / maxValue) * 100 : 0;
  const fill = value > 70 ? 'bg-green-500' : value > 40 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-gray-400 w-32 shrink-0">{label}</span>
      <div className="flex-1 h-3 bg-white/5 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${fill}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm text-white font-medium w-10 text-right">{value}</span>
    </div>
  );
}

/* ── AISkeleton ──────────────────────────────────────────────── */

function AISkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-4 bg-white/10 rounded w-full" />
      <div className="h-4 bg-white/10 rounded w-5/6" />
      <div className="h-4 bg-white/10 rounded w-4/6" />
    </div>
  );
}

/* ── page ────────────────────────────────────────────────────── */

export default function StockSearchPage() {
  const [query, setQuery]                   = useState('');
  const [searchResults, setSearchResults]   = useState<KRStockSearchResult[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [stockSummary, setStockSummary]     = useState<KRStockSummary | null>(null);
  const [aiSummary, setAISummary]           = useState<KRStockAISummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingAI, setLoadingAI]           = useState(false);

  /* ── 디바운스 검색 ── */
  useEffect(() => {
    if (selectedTicker) return;           // 종목 선택 후엔 검색 드롭다운 불필요
    if (query.length < 2) { setSearchResults([]); return; }

    const timer = setTimeout(async () => {
      try {
        const res = await krAPI.searchStock(query);
        setSearchResults(Array.isArray(res) ? res : []);
      } catch {
        setSearchResults([]);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query, selectedTicker]);

  /* ── 종목 선택 ── */
  const handleSelect = (stock: KRStockSearchResult) => {
    setSelectedTicker(stock.ticker);
    setQuery(stock.name);
    setSearchResults([]);
    setStockSummary(null);
    setAISummary(null);
    setLoadingSummary(true);
    setLoadingAI(true);

    krAPI.getStockSummary(stock.ticker)
      .then(s => setStockSummary(s))
      .catch(() => {})
      .finally(() => setLoadingSummary(false));

    krAPI.getStockAISummary(stock.ticker)
      .then(ai => setAISummary(ai))
      .catch(() => {})
      .finally(() => setLoadingAI(false));
  };

  /* ── query 지우면 선택 초기화 ── */
  const handleQueryChange = (v: string) => {
    setQuery(v);
    if (selectedTicker && v !== stockSummary?.name) {
      setSelectedTicker(null);
      setStockSummary(null);
      setAISummary(null);
    }
  };

  /* ── factors 정렬 (total 제외) ── */
  const factorEntries = stockSummary
    ? Object.entries(stockSummary.factors)
        .filter(([k]) => k !== 'total')
        .sort(([, a], [, b]) => b - a)
    : [];
  const maxFactor = factorEntries.length > 0 ? Math.max(...factorEntries.map(([, v]) => v), 1) : 1;

  return (
    <div className="space-y-4">
      {/* ── 헤더 ── */}
      <div>
        <h1 className="text-3xl font-bold text-white">종목 검색</h1>
        <p className="text-gray-400 mt-1">종목별 상세 분석</p>
      </div>

      {/* ── 검색 바 ── */}
      <div className="relative">
        <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-4">
          <input
            type="text"
            value={query}
            onChange={e => handleQueryChange(e.target.value)}
            placeholder="종목명 또는 티커 입력 (예: 삼성전자, 005930)"
            className="w-full bg-transparent border-b border-white/10 pb-2 text-lg text-white placeholder-gray-600 focus:border-blue-500 outline-none transition-colors"
          />
        </div>

        {/* 자동완성 드롭다운 */}
        {searchResults.length > 0 && !selectedTicker && (
          <div className="absolute z-10 w-full mt-1 bg-[#1e2635] border border-white/10 rounded-xl overflow-hidden shadow-2xl">
            {searchResults.slice(0, 10).map(s => (
              <button
                key={s.ticker}
                onClick={() => handleSelect(s)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 cursor-pointer border-b border-white/5 last:border-0 text-left transition-colors"
              >
                <span className="text-white font-medium">{s.name}</span>
                <span className="text-gray-500 text-sm">{s.ticker}</span>
                <span className={`ml-auto text-xs ${s.market === 'KOSPI' ? 'text-rose-400' : 'text-blue-400'}`}>
                  {s.market}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── 빈 상태 ── */}
      {!selectedTicker && (
        <div className="bg-[#1a1f2e] rounded-2xl p-12 text-center text-gray-500">
          <i className="fa-solid fa-search text-4xl mb-4 block" />
          <p>검색창에 종목명을 입력해보세요</p>
        </div>
      )}

      {/* ── 종목 요약 ── */}
      {selectedTicker && (
        <>
          {/* 기본 정보 카드 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5 mt-4">
            {loadingSummary ? (
              <div className="animate-pulse space-y-3">
                <div className="h-7 bg-white/10 rounded w-40" />
                <div className="h-10 bg-white/10 rounded w-32" />
              </div>
            ) : stockSummary ? (
              <>
                <div className="flex items-center gap-3 flex-wrap">
                  <h2 className="text-2xl font-bold text-white">{stockSummary.name}</h2>
                  <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                    stockSummary.market === 'KOSPI'
                      ? 'bg-rose-500/15 text-rose-400'
                      : 'bg-blue-500/15 text-blue-400'
                  }`}>
                    {stockSummary.market}
                  </span>
                </div>

                <div className="flex items-baseline gap-3 mt-2">
                  <span className="text-3xl font-bold text-white">
                    ₩{fmtPrice(stockSummary.current_price)}
                  </span>
                  <span className={`text-lg font-medium ${
                    stockSummary.change_pct >= 0 ? 'text-rose-400' : 'text-blue-400'
                  }`}>
                    {stockSummary.change_pct >= 0 ? '+' : ''}{stockSummary.change_pct.toFixed(2)}%
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                  {[
                    { label: '거래량',   value: fmtVol(stockSummary.volume) },
                    { label: '시가총액', value: fmtCap(stockSummary.market_cap) },
                    { label: 'PER',      value: fmtPer(stockSummary.per) },
                    { label: 'PBR',      value: stockSummary.pbr > 0 ? stockSummary.pbr.toFixed(2) : 'N/A' },
                  ].map(({ label, value }) => (
                    <div key={label}>
                      <p className="text-gray-500 text-xs">{label}</p>
                      <p className="text-white font-medium mt-0.5">{value}</p>
                    </div>
                  ))}
                </div>

                {/* 시그널 뱃지 */}
                {(stockSummary.signals.vcp || stockSummary.signals.closing_bet) && (
                  <div className="flex gap-2 mt-4">
                    {stockSummary.signals.vcp && (
                      <span className="bg-rose-500/15 text-rose-400 px-3 py-1 rounded-full text-xs font-medium">
                        VCP 시그널 활성
                      </span>
                    )}
                    {stockSummary.signals.closing_bet && (
                      <span className="bg-violet-500/15 text-violet-400 px-3 py-1 rounded-full text-xs font-medium">
                        종가베팅 활성
                      </span>
                    )}
                  </div>
                )}
              </>
            ) : (
              <p className="text-gray-500 text-sm">데이터를 불러올 수 없습니다.</p>
            )}
          </div>

          {/* 팩터 바 차트 */}
          {stockSummary && factorEntries.length > 0 && (
            <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
              <h3 className="text-white font-semibold mb-4">팩터 분석</h3>
              <div className="space-y-3">
                {factorEntries.map(([key, value]) => (
                  <FactorBar
                    key={key}
                    label={FACTOR_LABELS[key] ?? key}
                    value={value}
                    maxValue={maxFactor}
                  />
                ))}
              </div>
            </div>
          )}

          {/* AI 분석 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <i className="fa-solid fa-robot text-blue-400" />
              <h3 className="text-white font-semibold">AI 분석</h3>
            </div>

            {loadingAI && <AISkeleton />}

            {!loadingAI && aiSummary && (
              <>
                <p className="text-gray-300 leading-relaxed">{aiSummary.summary}</p>

                {aiSummary.outlook && (
                  <p className="text-white font-medium mt-3">{aiSummary.outlook}</p>
                )}

                {aiSummary.risk_factors?.length > 0 && (
                  <div className="mt-3">
                    <p className="text-sm text-red-400 font-medium mb-2">리스크 요인</p>
                    <div className="space-y-1.5">
                      {aiSummary.risk_factors.map((r, i) => (
                        <div key={i} className="flex items-start gap-2">
                          <i className="fa-solid fa-exclamation-triangle text-red-400 text-xs mt-1" />
                          <span className="text-sm text-gray-400">{r}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {aiSummary.catalysts?.length > 0 && (
                  <div className="mt-3">
                    <p className="text-sm text-green-400 font-medium mb-2">성장 촉매</p>
                    <div className="space-y-1.5">
                      {aiSummary.catalysts.map((c, i) => (
                        <div key={i} className="flex items-start gap-2">
                          <i className="fa-solid fa-rocket text-green-400 text-xs mt-1" />
                          <span className="text-sm text-gray-400">{c}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {!loadingAI && !aiSummary && (
              <p className="text-gray-600 text-sm">AI 분석 데이터가 없습니다.</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
