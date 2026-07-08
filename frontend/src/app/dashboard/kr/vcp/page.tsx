'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { krAPI } from '@/lib/api';
import { usePriceStream } from '@/hooks/usePriceStream';
import DateFilter from '@/components/ui/DateFilter';

/* ── helpers ─────────────────────────────────────────────────── */

function getTicker(s: any): string { return s.stock_code ?? s.ticker ?? ''; }
function getName(s: any): string { return s.stock_name ?? s.name ?? ''; }
function getScore(s: any): number {
  if (s?.score && typeof s.score === 'object') return s.score.total ?? 0;
  return typeof s.score === 'number' ? s.score : 0;
}

const GRADE_STYLE: Record<string, { bg: string; text: string; ring: string }> = {
  A: { bg: 'bg-emerald-500/20', text: 'text-emerald-300', ring: 'ring-1 ring-emerald-500/40' },
  B: { bg: 'bg-blue-500/20', text: 'text-blue-300', ring: 'ring-1 ring-blue-500/40' },
  C: { bg: 'bg-yellow-500/20', text: 'text-yellow-300', ring: 'ring-1 ring-yellow-500/40' },
  D: { bg: 'bg-gray-500/20', text: 'text-gray-400', ring: 'ring-1 ring-gray-500/30' },
};

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
  signal: any;
  onClose: () => void;
}) {
  // ESC to close
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
        {signal && (
          <div className="grid grid-cols-3 gap-3 mb-4 p-3 rounded-xl bg-white/5 border border-white/8">
            <SignalMeta label="진입가" value={signal.entry_price > 0 ? `₩${signal.entry_price.toLocaleString()}` : '--'} className="text-white" />
            <SignalMeta label="손절가" value={signal.stop_price > 0 ? `₩${signal.stop_price.toLocaleString()}` : '--'} className="text-blue-400" />
            <SignalMeta label="목표가" value={signal.target_price > 0 ? `₩${signal.target_price.toLocaleString()}` : '--'} className="text-emerald-400" />
          </div>
        )}
        {signal && (signal.atrp > 0 || signal.c1 || signal.c2 || signal.c3) && (
          <div className="grid grid-cols-5 gap-2 mb-4 p-3 rounded-xl bg-white/5 border border-white/8">
            <SignalMeta label="ATRp" value={signal.atrp > 0 ? `${signal.atrp}%` : '--'} />
            <SignalMeta label="C1" value={signal.c1 ? `${signal.c1}%` : '--'} />
            <SignalMeta label="C2" value={signal.c2 ? `${signal.c2}%` : '--'} />
            <SignalMeta label="C3" value={signal.c3 ? `${signal.c3}%` : '--'} />
            <div className="flex flex-col gap-0.5">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">수축비</span>
              <span className="text-sm font-semibold text-gray-200">
                {signal.r12 ? signal.r12 : '--'} / {signal.r23 ? signal.r23 : '--'}
              </span>
            </div>
          </div>
        )}

        <div className="h-[400px]">
          <StockChart ticker={ticker} marketType="KR" />
        </div>
      </div>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────── */

export default function VCPSignalsPage() {
  const [signals, setSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [dates, setDates] = useState<string[]>([]);
  const [dateCounts, setDateCounts] = useState<Record<string, number>>({});
  const [selectedDate, setSelectedDate] = useState<string | null>(null); // null = 최신
  const [signalDate, setSignalDate] = useState<string>('');
  const [gradeFilter, setGradeFilter] = useState<Set<string>>(new Set());

  // 날짜 목록 로드
  useEffect(() => {
    krAPI.getVCPDates()
      .then((res) => { setDates(res?.dates ?? []); setDateCounts(res?.counts ?? {}); })
      .catch(() => { });
  }, []);

  // 시그널 로드 (날짜 변경 시 재로드)
  useEffect(() => {
    setLoading(true);
    const fetch = selectedDate
      ? krAPI.getVCPHistory(selectedDate)
      : krAPI.getSignals();
    fetch
      .then((res: any) => {
        setSignals(res?.signals ?? []);
        setSignalDate(res?.generated_at ?? res?.date ?? '');
      })
      .catch(() => setSignals([]))
      .finally(() => setLoading(false));
  }, [selectedDate]);

  const tickers = signals.map(getTicker).filter(Boolean);
  const { prices, connected } = usePriceStream(tickers);

  const toggleGrade = (g: string) =>
    setGradeFilter((prev) => {
      const next = new Set(prev);
      next.has(g) ? next.delete(g) : next.add(g);
      return next;
    });

  const sorted = [...signals]
    .sort((a, b) => getScore(b) - getScore(a))
    .filter((s) => gradeFilter.size === 0 || gradeFilter.has((s.grade as string) || ''));
  const selectedSignal = signals.find((s) => getTicker(s) === selectedTicker) ?? null;

  return (
    <div className="space-y-6">

      {/* ── Header ───────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">VCP Signals</h1>
          <p className="text-gray-400 text-sm mt-1">Volatility Contraction Pattern</p>
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
              {gradeFilter.size > 0 ? `${sorted.length} / ${signals.length}개` : `${signals.length}개`}
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

      {/* ── Grade filter ─────────────────────────────────────── */}
      <div className="flex items-center gap-2 text-[11px]">
        {(['A', 'B', 'C', 'D'] as const).map((g) => {
          const st = GRADE_STYLE[g];
          const active = gradeFilter.has(g);
          const label = g === 'A' ? '최우선' : g === 'B' ? '양호' : g === 'C' ? '관찰' : '참고';
          const cnt = signals.filter((s) => (s.grade as string) === g).length;
          return (
            <button
              key={g}
              onClick={() => toggleGrade(g)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition-all select-none ${active
                ? `${st.bg} ${st.ring} opacity-100`
                : 'bg-white/5 ring-1 ring-white/10 opacity-50 hover:opacity-80'
                }`}
            >
              <span className={`font-bold ${active ? st.text : 'text-gray-400'}`}>{g}등급</span>
              <span className={active ? 'text-gray-300' : 'text-gray-600'}>{label}</span>
              {cnt > 0 && (
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${active ? `${st.bg} ${st.text}` : 'bg-white/5 text-gray-500'
                  }`}>
                  {cnt}
                </span>
              )}
            </button>
          );
        })}
        {gradeFilter.size > 0 && (
          <button
            onClick={() => setGradeFilter(new Set())}
            className="ml-1 text-gray-500 hover:text-white transition-colors text-[11px]"
          >
            <i className="fa-solid fa-xmark mr-1" />전체
          </button>
        )}
      </div>

      {/* ── Signal list ──────────────────────────────────────── */}
      {loading ? (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-2 space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 rounded-lg bg-white/5 animate-pulse" />
          ))}
        </div>
      ) : sorted.length === 0 ? (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-14 flex flex-col items-center text-center">
          <i className="fa-solid fa-crosshairs text-gray-700 text-5xl mb-4" />
          {gradeFilter.size > 0 ? (
            <>
              <p className="text-gray-400 font-medium">
                {[...gradeFilter].join(', ')}등급 시그널이 없습니다.
              </p>
              <button
                onClick={() => setGradeFilter(new Set())}
                className="mt-3 text-sm text-blue-400 hover:text-blue-300 transition-colors"
              >
                필터 해제하기
              </button>
            </>
          ) : (
            <>
              <p className="text-gray-400 font-medium">현재 활성 VCP 시그널이 없습니다.</p>
              <p className="text-gray-600 text-sm mt-1">다음 스캔 결과를 기다려 주세요.</p>
            </>
          )}
        </div>
      ) : (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-2">
          {sorted.map((s, i) => {
            const ticker = getTicker(s);
            const name = getName(s);
            const score = getScore(s);
            const grade = (s.grade as string) || '';
            const gradeSt = grade ? (GRADE_STYLE[grade] ?? GRADE_STYLE['D']) : null;
            const isKospi = (s.market ?? '').toUpperCase().includes('KOSPI');
            const livePrice = prices[ticker.toUpperCase()]?.price ?? s.current_price ?? 0;
            const liveReturn = s.entry_price > 0
              ? (livePrice - s.entry_price) / s.entry_price * 100
              : 0;

            return (
              <div
                key={ticker + s.signal_date}
                onClick={() => setSelectedTicker(ticker)}
                className={`flex items-center gap-4 px-4 py-3.5 hover:bg-white/[0.04] rounded-xl transition-colors cursor-pointer group ${i < sorted.length - 1 ? 'border-b border-white/5' : ''
                  }`}
              >
                {/* 순위 */}
                <span className="text-sm font-bold text-gray-500 w-6 text-center flex-shrink-0">
                  {i + 1}
                </span>

                {/* 종목 텍스트 */}
                <div className="w-[320px] flex-shrink-0 min-w-0">
                  <div className="min-w-0 flex flex-col justify-center gap-1">
                    <p className="text-sm font-semibold text-white truncate group-hover:text-rose-300 transition-colors">
                      {name}
                      <span className="ml-2 inline text-[10px] px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-400 font-medium">
                        {score}점
                      </span>
                      <span className="ml-2 text-[11px] font-normal text-gray-500">{ticker}</span>
                      {s.signal_date && <span className="ml-3 text-[11px] text-gray-600">{s.signal_date}</span>}
                    </p>
                    <p className="text-[11px] text-gray-500">
                      {s.entry_price > 0 && <span>진입 <span className="text-gray-300">₩{s.entry_price.toLocaleString()}</span></span>}
                      {s.stop_price > 0 && <span> · 손절 <span className="text-blue-400">₩{s.stop_price.toLocaleString()}</span></span>}
                      {s.target_price > 0 && <span> · 목표 <span className="text-emerald-400">₩{s.target_price.toLocaleString()}</span></span>}
                    </p>
                  </div>
                </div>

                {/* KP/KQ 배지 컬럼 */}
                <div className="w-14 flex-shrink-0 flex items-center justify-center">
                  <div className={`w-11 h-11 rounded-full flex items-center justify-center text-xs font-bold text-white ${isKospi
                    ? 'bg-gradient-to-br from-rose-500 to-orange-500'
                    : 'bg-gradient-to-br from-blue-500 to-cyan-500'
                    }`}>
                    {isKospi ? 'KP' : 'KQ'}
                  </div>
                </div>

                {/* 등급 배지 컬럼 */}
                <div className="w-14 flex-shrink-0 flex items-center justify-center">
                  {gradeSt && (
                    <div className={`w-11 h-11 rounded-xl flex items-center justify-center text-base font-extrabold ${gradeSt.bg} ${gradeSt.text} ${gradeSt.ring}`}>
                      {grade}
                    </div>
                  )}
                </div>

                {/* 우측 공백 (가변) */}
                <div className="flex-1" />

                {/* 실시간 수익률 */}
                <div className="text-right min-w-[80px] flex-shrink-0">
                  <p className={`text-sm font-bold ${liveReturn >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    {liveReturn >= 0 ? '+' : ''}{liveReturn.toFixed(2)}%
                  </p>
                  <p className="text-[10px] text-gray-500">
                    ₩{livePrice > 0 ? livePrice.toLocaleString() : '--'}
                  </p>
                </div>

                <i className="fa-solid fa-chevron-right text-gray-600 group-hover:text-gray-300 text-xs transition-colors flex-shrink-0" />
              </div>
            );
          })}
        </div>
      )}

      {/* ── Footer link ──────────────────────────────────────── */}
      <div className="flex justify-end pt-2">
        <Link
          href="/dashboard/kr/vcp/history"
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          누적 성과 보기 →
        </Link>
      </div>

      {/* ── Chart modal ──────────────────────────────────────── */}
      {selectedTicker && selectedSignal && (
        <ChartModal
          ticker={selectedTicker}
          name={getName(selectedSignal)}
          signal={selectedSignal}
          onClose={() => setSelectedTicker(null)}
        />
      )}

    </div>
  );
}
