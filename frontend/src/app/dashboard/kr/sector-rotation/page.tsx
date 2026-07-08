'use client';

import { useEffect, useRef, useState } from 'react';
import { krAPI } from '@/lib/api';
import { usePriceStream } from '@/hooks/usePriceStream';
import DateFilter from '@/components/ui/DateFilter';

/* ── types ───────────────────────────────────────────────────── */

type RotationPhase = 'accumulation' | 'markup' | 'distribution' | 'markdown';

interface SectorRotationSignal {
  ticker: string;
  name: string;
  market: string;
  score: number;
  sector: string;
  rotation_phase: RotationPhase;
  relative_strength: number;  // 0 ~ 100
  signal_date: string;
}

import StockChart from '@/components/ui/StockChart';

/* ── ChartModal ──────────────────────────────────────────────── */

function SignalMeta({ label, value, className = '' }: { label: string; value: string | number; className?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</span>
      <span className={`text-sm font-semibold ${className || 'text-gray-200'}`}>{value}</span>
    </div>
  );
}

function ChartModal({ ticker, name, signal, onClose }: { ticker: string; name: string; signal: SectorRotationSignal; onClose: () => void }) {
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
          <SignalMeta label="종합점수" value={`${signal.score}점`} className="text-emerald-400" />
          <SignalMeta label="로테이션 단계" value={PHASE_MAP[signal.rotation_phase]?.label || signal.rotation_phase} className={PHASE_MAP[signal.rotation_phase]?.cls || 'text-white'} />
          <SignalMeta label="상대강도(RS)" value={`${signal.relative_strength.toFixed(1)}%`} className="text-emerald-400" />
          <SignalMeta label="섹터" value={signal.sector || '--'} className="text-white truncate" />
        </div>
        <div className="h-[400px]">
          <StockChart ticker={ticker} marketType="KR" />
        </div>
      </div>
    </div>
  );
}

/* ── Phase badge ─────────────────────────────────────────────── */

const PHASE_MAP: Record<string, { label: string; cls: string }> = {
  accumulation: { label: '매집', cls: 'bg-green-500/15 text-green-400' },
  markup: { label: '상승', cls: 'bg-amber-500/15 text-amber-400' },
  distribution: { label: '분산', cls: 'bg-red-500/15   text-red-400' },
  markdown: { label: '하락', cls: 'bg-blue-500/15  text-blue-400' },
};

function PhaseBadge({ phase }: { phase: string }) {
  const { label, cls } = PHASE_MAP[phase] ?? { label: phase, cls: 'bg-gray-500/15 text-gray-400' };
  return <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${cls}`}>{label}</span>;
}

/* ── RS bar ──────────────────────────────────────────────────── */

function RSBar({ value }: { value: number }) {
  const pct = Math.min(Math.max(value, 0), 100);
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-20 h-2 bg-white/5 rounded-full overflow-hidden flex-shrink-0">
        <div className="h-full rounded-full bg-emerald-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] text-emerald-400 font-semibold tabular-nums w-8 text-right">{pct.toFixed(0)}</span>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────── */

export default function SectorRotationPage() {
  const [signals, setSignals] = useState<SectorRotationSignal[]>([]);
  const [stats, setStats] = useState({ total: 0, avg_score: 0 });
  const [loading, setLoading] = useState(true);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [dates, setDates] = useState<string[]>([]);
  const [dateCounts, setDateCounts] = useState<Record<string, number>>({});
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [signalDate, setSignalDate] = useState<string>('');

  useEffect(() => {
    krAPI.getSectorRotationDates()
      .then((res) => { setDates(res?.dates ?? []); setDateCounts(res?.counts ?? {}); })
      .catch(() => { });
  }, []);

  useEffect(() => {
    setLoading(true);
    const req = selectedDate
      ? krAPI.getSectorRotationHistory(selectedDate)
      : krAPI.getStrategy('sector-rotation');
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

  const sectorCount = new Set(signals.map((s) => s.sector).filter(Boolean)).size;
  const avgRS = signals.length
    ? (signals.reduce((a, s) => a + (s.relative_strength ?? 0), 0) / signals.length).toFixed(1)
    : '0.0';

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">섹터 로테이션</h1>
          <p className="text-gray-400 text-sm mt-1">업종 순환 기반 전략</p>
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
            <p className="text-2xl font-bold text-emerald-400">{stats.total}<span className="text-sm font-normal text-gray-500 ml-1">종목</span></p>
          </div>
          <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
            <p className="text-xs text-gray-500 mb-1">Avg Score</p>
            <p className="text-2xl font-bold text-white">{stats.avg_score}<span className="text-sm font-normal text-gray-500 ml-1">점</span></p>
          </div>
          <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
            <p className="text-xs text-gray-500 mb-1">Sectors</p>
            <p className="text-2xl font-bold text-emerald-400">{sectorCount}<span className="text-sm font-normal text-gray-500 ml-1">개 섹터</span></p>
          </div>
          <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
            <p className="text-xs text-gray-500 mb-1">Avg RS</p>
            <p className="text-2xl font-bold text-emerald-400">{avgRS}</p>
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
          <i className="fa-solid fa-sync text-gray-700 text-5xl mb-4" />
          <p className="text-gray-400 font-medium">섹터 로테이션 시그널이 없습니다.</p>
          <p className="text-gray-600 text-sm mt-1">다음 스캔 결과를 기다려 주세요.</p>
        </div>
      ) : (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-2">
          <div className="flex items-center gap-5 px-4 py-2 text-[10px] font-semibold text-gray-600 uppercase tracking-wider border-b border-white/5 mb-1">
            <span className="w-6 text-center flex-shrink-0">#</span>
            <span className="w-[320px] flex-shrink-0">종목</span>
            <span className="w-14 flex-shrink-0 text-center">시장</span>
            <div className="flex-1" />
            <span className="hidden sm:block w-24">섹터</span>
            <span className="hidden sm:block w-20 text-center">로테이션 단계</span>
            <span className="hidden md:block w-32">상대강도</span>
            <span className="w-14 text-right">현재가</span>
          </div>

          {signals.map((s, i) => {
            const isKospi = (s.market ?? '').toUpperCase().includes('KOSPI');
            const livePrice = prices[s.ticker.toUpperCase()]?.price ?? 0;
            return (
              <div key={s.ticker} onClick={() => setSelectedTicker(s.ticker)}
                className={`flex items-center gap-5 px-4 py-3.5 hover:bg-white/[0.04] rounded-xl transition-colors cursor-pointer group ${i < signals.length - 1 ? 'border-b border-white/5' : ''}`}>
                <span className="text-sm font-bold text-gray-500 w-6 text-center flex-shrink-0">{i + 1}</span>
                <div className="w-[320px] flex-shrink-0 min-w-0">
                  <div className="min-w-0 flex flex-col justify-center gap-1">
                    <p className="text-sm font-semibold text-white truncate group-hover:text-emerald-300 transition-colors">
                      {s.name}
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-medium">{s.score}점</span>
                      <span className="ml-2 text-[11px] font-normal text-gray-500">{s.ticker}</span>
                      {s.signal_date && <span className="ml-3 text-[11px] text-gray-600">{s.signal_date}</span>}
                    </p>
                    {s.sector && <p className="text-[11px] text-emerald-400/70">{s.sector}</p>}
                  </div>
                </div>
                <div className="w-14 flex-shrink-0 flex items-center justify-center">
                  <div className={`w-11 h-11 rounded-full flex items-center justify-center text-xs font-bold text-white ${isKospi ? 'bg-gradient-to-br from-rose-500 to-orange-500' : 'bg-gradient-to-br from-blue-500 to-cyan-500'}`}>
                    {isKospi ? 'KP' : 'KQ'}
                  </div>
                </div>
                <div className="flex-1" />
                <div className="hidden sm:block w-24 flex-shrink-0">
                  <span className="text-xs text-emerald-400 font-medium truncate block">{s.sector || '--'}</span>
                </div>
                <div className="hidden sm:block w-20 flex-shrink-0 flex justify-center">
                  <PhaseBadge phase={s.rotation_phase} />
                </div>
                <div className="hidden md:block w-32 flex-shrink-0">
                  <RSBar value={s.relative_strength ?? 0} />
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
