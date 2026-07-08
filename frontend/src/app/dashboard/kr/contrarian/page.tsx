'use client';

import { useEffect, useRef, useState } from 'react';
import StockChart from '@/components/ui/StockChart';
import { krAPI } from '@/lib/api';
import { usePriceStream } from '@/hooks/usePriceStream';
import DateFilter from '@/components/ui/DateFilter';

/* ── types ───────────────────────────────────────────────────── */

interface ContrarianSignal {
  ticker: string;
  name: string;
  market: string;
  score: number;
  oversold_score: number;        // 0 ~ 100
  reversal_probability: number;  // 0 ~ 1
  support_level: number;
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

function ChartModal({ ticker, name, signal, onClose }: { ticker: string; name: string; signal: ContrarianSignal; onClose: () => void }) {
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
          <SignalMeta label="종합점수" value={`${signal.score}점`} className="text-rose-400" />
          <SignalMeta label="과매도점수" value={`${signal.oversold_score}점`} className="text-rose-400" />
          <SignalMeta label="반등확률" value={`${(signal.reversal_probability * 100).toFixed(0)}%`} className="text-emerald-400" />
          <SignalMeta label="지지선" value={signal.support_level > 0 ? `₩${signal.support_level.toLocaleString()}` : '--'} className="text-white" />
        </div>
        <div className="h-[400px]">
          <StockChart ticker={ticker} marketType="KR" />
        </div>
      </div>
    </div>
  );
}

/* ── Oversold bar ────────────────────────────────────────────── */

function OversoldBar({ value }: { value: number }) {
  const pct = Math.min(Math.max(value, 0), 100);
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-16 h-2 bg-white/5 rounded-full overflow-hidden flex-shrink-0">
        <div className="h-full rounded-full bg-rose-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] text-rose-400 font-semibold tabular-nums w-6 text-right">{pct.toFixed(0)}</span>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────── */

export default function ContrarianPage() {
  const [signals, setSignals] = useState<ContrarianSignal[]>([]);
  const [stats, setStats] = useState({ total: 0, avg_score: 0 });
  const [loading, setLoading] = useState(true);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [dates, setDates] = useState<string[]>([]);
  const [dateCounts, setDateCounts] = useState<Record<string, number>>({});
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [signalDate, setSignalDate] = useState<string>('');

  useEffect(() => {
    krAPI.getContrarianDates()
      .then((res) => { setDates(res?.dates ?? []); setDateCounts(res?.counts ?? {}); })
      .catch(() => { });
  }, []);

  useEffect(() => {
    setLoading(true);
    const req = selectedDate
      ? krAPI.getContrarianHistory(selectedDate)
      : krAPI.getStrategy('contrarian-reversal');
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

  const highProbCount = signals.filter((s) => (s.reversal_probability ?? 0) > 0.7).length;
  const avgOversold = signals.length
    ? (signals.reduce((a, s) => a + (s.oversold_score ?? 0), 0) / signals.length).toFixed(1)
    : '0.0';

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">역발상 전략</h1>
          <p className="text-gray-400 text-sm mt-1">과매도 반전 시그널</p>
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
            <p className="text-2xl font-bold text-rose-400">{stats.total}<span className="text-sm font-normal text-gray-500 ml-1">종목</span></p>
          </div>
          <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
            <p className="text-xs text-gray-500 mb-1">Avg Score</p>
            <p className="text-2xl font-bold text-white">{stats.avg_score}<span className="text-sm font-normal text-gray-500 ml-1">점</span></p>
          </div>
          <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
            <p className="text-xs text-gray-500 mb-1">High Probability</p>
            <p className="text-2xl font-bold text-green-400">{highProbCount}<span className="text-sm font-normal text-gray-500 ml-1">종목</span></p>
          </div>
          <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
            <p className="text-xs text-gray-500 mb-1">Avg Oversold</p>
            <p className="text-2xl font-bold text-rose-400">{avgOversold}</p>
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
          <i className="fa-solid fa-undo text-gray-700 text-5xl mb-4" />
          <p className="text-gray-400 font-medium">역발상 시그널이 없습니다.</p>
          <p className="text-gray-600 text-sm mt-1">다음 스캔 결과를 기다려 주세요.</p>
        </div>
      ) : (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-2">
          <div className="flex items-center gap-5 px-4 py-2 text-[10px] font-semibold text-gray-600 uppercase tracking-wider border-b border-white/5 mb-1">
            <span className="w-6 text-center flex-shrink-0">#</span>
            <span className="w-[320px] flex-shrink-0">종목</span>
            <span className="w-14 flex-shrink-0 text-center">시장</span>
            <div className="flex-1" />
            <span className="hidden sm:block w-28">과매도 점수</span>
            <span className="hidden sm:block w-16 text-right">반전 확률</span>
            <span className="hidden md:block w-28 text-right">지지선</span>
            <span className="w-14 text-right">현재가</span>
          </div>

          {signals.map((s, i) => {
            const isKospi = (s.market ?? '').toUpperCase().includes('KOSPI');
            const livePrice = prices[s.ticker.toUpperCase()]?.price ?? 0;
            const prob = s.reversal_probability ?? 0;
            const probCls = prob >= 0.7 ? 'text-green-400 font-bold' : prob >= 0.5 ? 'text-yellow-400' : 'text-gray-400';
            return (
              <div key={s.ticker} onClick={() => setSelectedTicker(s.ticker)}
                className={`flex items-center gap-5 px-4 py-3.5 hover:bg-white/[0.04] rounded-xl transition-colors cursor-pointer group ${i < signals.length - 1 ? 'border-b border-white/5' : ''}`}>
                <span className="text-sm font-bold text-gray-500 w-6 text-center flex-shrink-0">{i + 1}</span>
                <div className="w-[320px] flex-shrink-0 min-w-0">
                  <div className="min-w-0 flex flex-col justify-center gap-1">
                    <p className="text-sm font-semibold text-white truncate group-hover:text-rose-300 transition-colors">
                      {s.name}
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-rose-500/15 text-orange-400 font-medium">{s.score}점</span>
                      <span className="ml-2 text-[11px] font-normal text-gray-500">{s.ticker}</span>
                      {s.signal_date && <span className="ml-3 text-[11px] text-gray-600">{s.signal_date}</span>}
                    </p>
                    {(s.support_level ?? 0) > 0 && (
                      <p className="text-[11px] text-gray-500">
                        지지 <span className="text-gray-300">₩{s.support_level.toLocaleString()}</span>
                      </p>
                    )}
                  </div>
                </div>
                <div className="w-14 flex-shrink-0 flex items-center justify-center">
                  <div className={`w-11 h-11 rounded-full flex items-center justify-center text-xs font-bold text-white ${isKospi ? 'bg-gradient-to-br from-rose-500 to-orange-500' : 'bg-gradient-to-br from-blue-500 to-cyan-500'}`}>
                    {isKospi ? 'KP' : 'KQ'}
                  </div>
                </div>
                <div className="flex-1" />
                <div className="hidden sm:block w-28 flex-shrink-0">
                  <OversoldBar value={s.oversold_score ?? 0} />
                </div>
                <div className="hidden sm:block w-16 text-right flex-shrink-0">
                  <span className={`text-xs tabular-nums ${probCls}`}>{(prob * 100).toFixed(0)}%</span>
                </div>
                <div className="hidden md:block w-28 text-right flex-shrink-0">
                  <span className="text-sm text-gray-400">
                    {(s.support_level ?? 0) > 0 ? `₩${s.support_level.toLocaleString()}` : '--'}
                  </span>
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
