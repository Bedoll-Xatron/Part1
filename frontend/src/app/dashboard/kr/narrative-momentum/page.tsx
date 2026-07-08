'use client';

import { useEffect, useRef, useState } from 'react';
import StockChart from '@/components/ui/StockChart';
import { krAPI } from '@/lib/api';
import { usePriceStream } from '@/hooks/usePriceStream';
import DateFilter from '@/components/ui/DateFilter';

/* ── types ───────────────────────────────────────────────────── */

interface NarrativeSignal {
  ticker: string;
  name: string;
  market: string;
  score: number;
  theme: string;
  news_sentiment: number;   // -1 ~ +1
  sns_momentum: number;     // 0 ~ 100
  narrative_score: number;  // 0 ~ 10
  signal_date: string;
}

/* ── ChartModal ──────────────────────────────────────────────── */

function SignalMeta({ label, value, className = '' }: { label: string; value: string | number; className?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</span>
      <span className={`text-sm font-semibold ${className || 'text-gray-200'}`}>{value}</span>
    </div>
  );
}

function ChartModal({ ticker, name, signal, onClose }: { ticker: string; name: string; signal: NarrativeSignal; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-6 w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
        {/* Modal header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <p className="font-semibold text-white text-lg">{name}</p>
            <p className="text-xs text-gray-500 mt-0.5">{ticker}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
          >
            <i className="fa-solid fa-times" />
          </button>
        </div>

        {/* Signal detail strip */}
        <div className="grid grid-cols-4 gap-3 mb-4 p-3 rounded-xl bg-white/5 border border-white/8">
          <SignalMeta label="종합점수" value={`${signal.score}점`} className="text-orange-400" />
          <SignalMeta label="뉴스심리" value={signal.news_sentiment > 0.3 ? '긍정' : signal.news_sentiment < -0.3 ? '부정' : '중립'} className={signal.news_sentiment > 0.3 ? 'text-emerald-400' : signal.news_sentiment < -0.3 ? 'text-rose-400' : 'text-gray-400'} />
          <SignalMeta label="SNS모멘텀" value={`${signal.sns_momentum}%`} className="text-sky-400" />
          <SignalMeta label="테마" value={signal.theme || '--'} className="text-white truncate" />
        </div>
        <div className="h-[400px]">
          <StockChart ticker={ticker} marketType="KR" />
        </div>
      </div>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────── */

export default function NarrativeMomentumPage() {
  const [signals, setSignals] = useState<NarrativeSignal[]>([]);
  const [stats, setStats] = useState({ total: 0, avg_score: 0 });
  const [loading, setLoading] = useState(true);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [dates, setDates] = useState<string[]>([]);
  const [dateCounts, setDateCounts] = useState<Record<string, number>>({});
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [signalDate, setSignalDate] = useState<string>('');

  useEffect(() => {
    krAPI.getNarrativeMomentumDates()
      .then((res) => { setDates(res?.dates ?? []); setDateCounts(res?.counts ?? {}); })
      .catch(() => { });
  }, []);

  useEffect(() => {
    setLoading(true);
    const req = selectedDate
      ? krAPI.getNarrativeMomentumHistory(selectedDate)
      : krAPI.getStrategy('narrative-momentum');
    req
      .then((d: any) => {
        setSignals(d?.signals ?? []);
        setStats(d?.stats ?? { total: 0, avg_score: 0 });
        setSignalDate(d?.date ?? d?.updated_at ?? '');
      })
      .catch(() => { })
      .finally(() => setLoading(false));
  }, [selectedDate]);

  const tickers = signals.map((s) => s.ticker).filter(Boolean);
  const { prices, connected } = usePriceStream(tickers);
  const selectedSignal = signals.find((s) => s.ticker === selectedTicker) ?? null;

  const topTheme = (() => {
    const cnt: Record<string, number> = {};
    signals.forEach((s) => { if (s.theme) cnt[s.theme] = (cnt[s.theme] ?? 0) + 1; });
    return Object.entries(cnt).sort(([, a], [, b]) => b - a)[0]?.[0] ?? '--';
  })();
  const avgSentiment = signals.length
    ? (signals.reduce((a, s) => a + (s.news_sentiment ?? 0), 0) / signals.length).toFixed(2)
    : '0.00';

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">테마 모멘텀</h1>
          <p className="text-gray-400 text-sm mt-1">뉴스/SNS 기반 테마 분석</p>
        </div>
        <div className="flex items-center gap-3 mt-1">
          {dates.length > 0 && (
            <DateFilter
              dates={dates}
              selected={selectedDate}
              onChange={(d) => { setSelectedDate(d); setSelectedTicker(null); }}
              loading={loading}
              counts={dateCounts}
            />
          )}
          {!loading && <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-sm font-medium text-white">{stats.total}개</span>}
          <div className="flex items-center gap-1.5 text-xs">
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
            <span className={connected ? 'text-green-400' : 'text-gray-500'}>{connected ? 'LIVE' : 'OFFLINE'}</span>
          </div>
        </div>
      </div>

      {/* Stats cards */}
      {!loading && stats.total > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
            <p className="text-xs text-gray-500 mb-1">Total Signals</p>
            <p className="text-2xl font-bold text-orange-400">{stats.total}<span className="text-sm font-normal text-gray-500 ml-1">종목</span></p>
          </div>
          <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
            <p className="text-xs text-gray-500 mb-1">Avg Score</p>
            <p className="text-2xl font-bold text-white">{stats.avg_score}<span className="text-sm font-normal text-gray-500 ml-1">점</span></p>
          </div>
          <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
            <p className="text-xs text-gray-500 mb-1">Top Theme</p>
            <p className="text-lg font-bold text-orange-400 truncate">{topTheme}</p>
          </div>
          <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
            <p className="text-xs text-gray-500 mb-1">Avg Sentiment</p>
            <p className={`text-2xl font-bold ${Number(avgSentiment) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{avgSentiment}</p>
          </div>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-2 space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 rounded-lg bg-white/5 animate-pulse" />)}
        </div>
      ) : signals.length === 0 ? (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-14 flex flex-col items-center text-center">
          <i className="fa-solid fa-fire text-gray-700 text-5xl mb-4" />
          <p className="text-gray-400 font-medium">테마 모멘텀 시그널이 없습니다.</p>
          <p className="text-gray-600 text-sm mt-1">다음 스캔 결과를 기다려 주세요.</p>
        </div>
      ) : (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-2">
          <div className="flex items-center gap-5 px-4 py-2 text-[10px] font-semibold text-gray-600 uppercase tracking-wider border-b border-white/5 mb-1">
            <span className="w-6 text-center flex-shrink-0">#</span>
            <span className="w-[320px] flex-shrink-0">종목</span>
            <span className="w-14 flex-shrink-0 text-center">시장</span>
            <div className="flex-1" />
            <span className="hidden sm:block w-24">테마</span>
            <span className="hidden sm:block w-20 text-right">뉴스 센티먼트</span>
            <span className="hidden md:block w-16 text-right">SNS 모멘텀</span>
            <span className="hidden md:block w-16 text-right">내러티브</span>
            <span className="w-14 text-right">현재가</span>
          </div>

          {signals.map((s, i) => {
            const isKospi = (s.market ?? '').toUpperCase().includes('KOSPI');
            const livePrice = prices[s.ticker.toUpperCase()]?.price ?? 0;
            const sentPos = (s.news_sentiment ?? 0) >= 0;
            const snsHigh = (s.sns_momentum ?? 0) > 70;
            return (
              <div key={s.ticker} onClick={() => setSelectedTicker(s.ticker)}
                className={`flex items-center gap-5 px-4 py-3.5 hover:bg-white/[0.04] rounded-xl transition-colors cursor-pointer group ${i < signals.length - 1 ? 'border-b border-white/5' : ''}`}>
                <span className="text-sm font-bold text-gray-500 w-6 text-center flex-shrink-0">{i + 1}</span>
                <div className="w-[320px] flex-shrink-0 min-w-0">
                  <div className="min-w-0 flex flex-col justify-center gap-1">
                    <p className="text-sm font-semibold text-white truncate group-hover:text-orange-300 transition-colors">
                      {s.name}
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-400 font-medium">{s.score}점</span>
                      <span className="ml-2 text-[11px] font-normal text-gray-500">{s.ticker}</span>
                      {s.signal_date && <span className="ml-3 text-[11px] text-gray-600">{s.signal_date}</span>}
                    </p>
                    {s.theme && <p className="text-[11px] text-orange-400/70">{s.theme}</p>}
                  </div>
                </div>
                <div className="w-14 flex-shrink-0 flex items-center justify-center">
                  <div className={`w-11 h-11 rounded-full flex items-center justify-center text-xs font-bold text-white ${isKospi ? 'bg-gradient-to-br from-rose-500 to-orange-500' : 'bg-gradient-to-br from-blue-500 to-cyan-500'}`}>
                    {isKospi ? 'KP' : 'KQ'}
                  </div>
                </div>
                <div className="flex-1" />
                <div className="hidden sm:block w-24 flex-shrink-0">
                  <span className="text-xs text-orange-400 font-medium truncate block">{s.theme || '--'}</span>
                </div>
                <div className="hidden sm:block w-20 text-right flex-shrink-0">
                  <span className={`text-xs font-semibold tabular-nums ${sentPos ? 'text-green-400' : 'text-red-400'}`}>
                    {sentPos ? '+' : ''}{(s.news_sentiment ?? 0).toFixed(2)}
                  </span>
                </div>
                <div className="hidden md:block w-16 text-right flex-shrink-0">
                  <span className={`text-xs tabular-nums ${snsHigh ? 'text-amber-400 font-bold' : 'text-white'}`}>{s.sns_momentum ?? 0}</span>
                </div>
                <div className="hidden md:block w-16 text-right flex-shrink-0">
                  <span className="text-xs text-orange-400 tabular-nums">{s.narrative_score ?? 0}</span>
                </div>
                <div className="w-14 text-right flex-shrink-0">
                  <span className="text-xs font-bold text-white">{livePrice > 0 ? `₩${livePrice.toLocaleString()}` : '--'}</span>
                </div>
                <i className="fa-solid fa-chevron-right text-gray-600 group-hover:text-gray-300 text-xs transition-colors flex-shrink-0" />
              </div>
            );
          })}
        </div>
      )}

      {/* Chart modal */}
      {selectedTicker && selectedSignal && (
        <ChartModal
          ticker={selectedTicker}
          name={selectedSignal.name}
          signal={selectedSignal}
          onClose={() => setSelectedTicker(null)}
        />
      )}
    </div>
  );
}
