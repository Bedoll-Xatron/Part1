'use client';

import { useEffect, useRef, useState } from 'react';
import { krAPI } from '@/lib/api';
import { usePriceStream } from '@/hooks/usePriceStream';
import DateFilter from '@/components/ui/DateFilter';

/* ── types ───────────────────────────────────────────────────── */

interface FlowSignal {
  ticker: string;
  name: string;
  market: string;
  score: number;
  foreign_flow: number;      // 억원
  institution_flow: number;  // 억원
  volume_ratio: number;      // 0–9.9
  signal_strength: 'strong' | 'moderate' | 'weak';
  signal_date: string;
}

interface Stats {
  total: number;
  avg_score: number;
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

function ChartModal({
  ticker,
  name,
  signal,
  onClose,
}: {
  ticker: string;
  name: string;
  signal: FlowSignal;
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-6 w-full max-w-2xl"
        onClick={(e) => e.stopPropagation()}
      >
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
          <SignalMeta label="외국인순매수" value={`${signal.foreign_flow > 0 ? '+' : ''}${signal.foreign_flow}억`} className={signal.foreign_flow >= 0 ? 'text-rose-400' : 'text-blue-400'} />
          <SignalMeta label="기관순매수" value={`${signal.institution_flow > 0 ? '+' : ''}${signal.institution_flow}억`} className={signal.institution_flow >= 0 ? 'text-rose-400' : 'text-blue-400'} />
          <SignalMeta label="거래량비" value={`${signal.volume_ratio}x`} className="text-amber-400" />
        </div>

        <div className="h-[400px]">
          <StockChart ticker={ticker} marketType="KR" />
        </div>
      </div>
    </div>
  );
}

/* ── Flow bar ────────────────────────────────────────────────── */

function FlowBar({ value, max = 30 }: { value: number; max?: number }) {
  const pct = Math.min(Math.abs(value) / max * 100, 100);
  const isPos = value >= 0;
  return (
    <div className="flex items-center gap-1.5 min-w-[90px]">
      <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
        <div
          className={`h-full rounded-full ${isPos ? 'bg-rose-400' : 'bg-blue-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-[11px] font-semibold tabular-nums ${isPos ? 'text-rose-400' : 'text-blue-400'}`}>
        {isPos ? '+' : ''}{value}억
      </span>
    </div>
  );
}

/* ── Strength badge ──────────────────────────────────────────── */

function StrengthBadge({ strength }: { strength: FlowSignal['signal_strength'] }) {
  const map = {
    strong: { label: '강함', cls: 'bg-emerald-500/15 text-emerald-400' },
    moderate: { label: '보통', cls: 'bg-amber-500/15  text-amber-400' },
    weak: { label: '약함', cls: 'bg-gray-500/15   text-gray-400' },
  };
  const { label, cls } = map[strength] ?? map.weak;
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${cls}`}>
      {label}
    </span>
  );
}

/* ── Page ────────────────────────────────────────────────────── */

export default function FlowMomentumPage() {
  const [signals, setSignals] = useState<FlowSignal[]>([]);
  const [stats, setStats] = useState<Stats>({ total: 0, avg_score: 0 });
  const [loading, setLoading] = useState(true);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'strong' | 'moderate' | 'weak'>('all');
  const [dates, setDates] = useState<string[]>([]);
  const [dateCounts, setDateCounts] = useState<Record<string, number>>({});
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [signalDate, setSignalDate] = useState<string>('');

  useEffect(() => {
    krAPI.getFlowMomentumDates()
      .then((res) => { setDates(res?.dates ?? []); setDateCounts(res?.counts ?? {}); })
      .catch(() => { });
  }, []);

  useEffect(() => {
    setLoading(true);
    const req = selectedDate
      ? krAPI.getFlowMomentumHistory(selectedDate)
      : fetch('/api/kr/strategies/flow-momentum').then((r) => r.json());
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

  const filtered = filter === 'all' ? signals : signals.filter((s) => s.signal_strength === filter);

  const selectedSignal = signals.find((s) => s.ticker === selectedTicker) ?? null;

  const strengthCounts = {
    strong: signals.filter((s) => s.signal_strength === 'strong').length,
    moderate: signals.filter((s) => s.signal_strength === 'moderate').length,
    weak: signals.filter((s) => s.signal_strength === 'weak').length,
  };

  return (
    <div className="space-y-6">

      {/* ── Header ───────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">수급 모멘텀</h1>
          <p className="text-gray-400 text-sm mt-1">외국인 · 기관 Flow Momentum</p>
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
          {!loading && (
            <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-sm font-medium text-white">
              {stats.total}개
            </span>
          )}
          <div className="flex items-center gap-1.5 text-xs">
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
            <span className={connected ? 'text-green-400' : 'text-gray-500'}>
              {connected ? 'LIVE' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Summary cards ────────────────────────────────────── */}
      {!loading && stats.total > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: '전체', value: stats.total, unit: '종목', cls: 'text-sky-400' },
            { label: '평균 점수', value: stats.avg_score, unit: '점', cls: 'text-white' },
            { label: '강한 수급', value: strengthCounts.strong, unit: '종목', cls: 'text-emerald-400' },
            { label: '보통 수급', value: strengthCounts.moderate, unit: '종목', cls: 'text-amber-400' },
          ].map(({ label, value, unit, cls }) => (
            <div key={label} className="rounded-xl bg-[#1a1f2e] border border-white/10 p-4">
              <p className="text-xs text-gray-500 mb-1">{label}</p>
              <p className={`text-2xl font-bold ${cls}`}>
                {value}<span className="text-sm font-normal text-gray-500 ml-1">{unit}</span>
              </p>
            </div>
          ))}
        </div>
      )}

      {/* ── Filter tabs ──────────────────────────────────────── */}
      {!loading && signals.length > 0 && (
        <div className="flex gap-2">
          {(['all', 'strong', 'moderate', 'weak'] as const).map((f) => {
            const labels = { all: '전체', strong: '강함', moderate: '보통', weak: '약함' };
            const active = filter === f;
            return (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${active
                  ? 'bg-sky-500/20 border border-sky-500/40 text-sky-300'
                  : 'bg-white/5 border border-white/10 text-gray-400 hover:text-white'
                  }`}
              >
                {labels[f]}
                {f !== 'all' && (
                  <span className="ml-1.5 text-[10px] opacity-60">
                    {strengthCounts[f as keyof typeof strengthCounts]}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* ── Signal list ──────────────────────────────────────── */}
      {loading ? (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-2 space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 rounded-lg bg-white/5 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-14 flex flex-col items-center text-center">
          <i className="fa-solid fa-water text-gray-700 text-5xl mb-4" />
          <p className="text-gray-400 font-medium">표시할 수급 시그널이 없습니다.</p>
          <p className="text-gray-600 text-sm mt-1">다른 필터를 선택해 주세요.</p>
        </div>
      ) : (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-2">
          {/* 헤더 */}
          <div className="flex items-center gap-5 px-4 py-2 text-[10px] font-semibold text-gray-600 uppercase tracking-wider border-b border-white/5 mb-1">
            <span className="w-6 text-center flex-shrink-0">#</span>
            <span className="w-[320px] flex-shrink-0">종목</span>
            <span className="w-14 flex-shrink-0 text-center">시장</span>
            <div className="flex-1" />
            <span className="hidden sm:block w-[110px] text-left">외국인 순매수</span>
            <span className="hidden sm:block w-[110px] text-left">기관 순매수</span>
            <span className="hidden md:block w-16 text-left">거래량비</span>
            <span className="w-14 text-left">현재가</span>
            <div className="w-4 flex-shrink-0" />
          </div>

          {filtered.map((s, i) => {
            const isKospi = (s.market ?? '').toUpperCase().includes('KOSPI');
            const liveData = prices[s.ticker.toUpperCase()];
            const livePrice = liveData?.price ?? 0;

            return (
              <div
                key={s.ticker}
                onClick={() => setSelectedTicker(s.ticker)}
                className={`flex items-center gap-5 px-4 py-3.5 hover:bg-white/[0.04] rounded-xl transition-colors cursor-pointer group ${i < filtered.length - 1 ? 'border-b border-white/5' : ''
                  }`}
              >
                {/* 순위 */}
                <span className="text-sm font-bold text-gray-500 w-6 text-center flex-shrink-0">
                  {i + 1}
                </span>

                {/* 종목 텍스트 */}
                <div className="w-[320px] flex-shrink-0 min-w-0">
                  <div className="min-w-0 flex flex-col justify-center gap-1">
                    <p className="text-sm font-semibold text-white truncate group-hover:text-sky-300 transition-colors">
                      {s.name}
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-400 font-medium">
                        {s.score}점
                      </span>
                      <span className="ml-2 text-[11px] font-normal text-gray-500">{s.ticker}</span>
                      {s.signal_date && <span className="ml-3 text-[11px] text-gray-600">{s.signal_date}</span>}
                    </p>
                    <p className="text-[11px] text-gray-500">
                      <StrengthBadge strength={s.signal_strength} />
                    </p>
                  </div>
                </div>

                {/* KP/KQ 배지 컬럼 */}
                <div className="w-14 flex-shrink-0 flex items-center justify-center">
                  <div className="relative">
                    <div className={`w-11 h-11 rounded-full flex items-center justify-center text-xs font-bold text-white ${isKospi
                      ? 'bg-gradient-to-br from-rose-500 to-orange-500'
                      : 'bg-gradient-to-br from-blue-500 to-cyan-500'
                      }`}>
                      {isKospi ? 'KP' : 'KQ'}
                    </div>
                    {s.signal_strength === 'strong' && (
                      <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-emerald-500 rounded-full border-2 border-[#1a1f2e]" />
                    )}
                  </div>
                </div>

                {/* spacer */}
                <div className="flex-1" />

                {/* 외국인 */}
                <div className="hidden sm:block w-[110px] flex-shrink-0">
                  <FlowBar value={s.foreign_flow} />
                </div>

                {/* 기관 */}
                <div className="hidden sm:block w-[110px] flex-shrink-0">
                  <FlowBar value={s.institution_flow} />
                </div>

                {/* 거래량비 */}
                <div className="hidden md:block w-16 text-left flex-shrink-0 text-xs font-semibold text-amber-400">
                  {s.volume_ratio.toFixed(1)}x
                </div>

                {/* 현재가 */}
                <div className="w-14 text-left flex-shrink-0">
                  <p className="text-xs font-bold text-white">
                    {livePrice > 0 ? `₩${livePrice.toLocaleString()}` : '--'}
                  </p>
                </div>

                <i className="fa-solid fa-chevron-right text-gray-600 group-hover:text-gray-300 text-xs transition-colors flex-shrink-0" />
              </div>
            );
          })}
        </div>
      )}

      {/* ── Chart modal ──────────────────────────────────────── */}
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
