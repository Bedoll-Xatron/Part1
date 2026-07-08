'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { usePriceStream } from '@/hooks/usePriceStream';
import DateFilter from '@/components/ui/DateFilter';
import { krAPI } from '@/lib/api';
import StockChart from '@/components/ui/StockChart';

/* ── types ───────────────────────────────────────────────────── */

interface ScoreDetail {
  news?: number; volume?: number; chart?: number; candle?: number;
  consolidation?: number; supply?: number; retracement?: number;
  pullback_support?: number; total?: number; llm_reason?: string;
}

interface Checklist {
  mandatory?: { has_news?: boolean; volume_sufficient?: boolean; news_sources?: string[] };
  optional?: {
    is_new_high?: boolean; is_breakout?: boolean; ma_aligned?: boolean;
    good_candle?: boolean; has_consolidation?: boolean; supply_positive?: boolean;
    retracement_recovery?: boolean; pullback_support_confirmed?: boolean;
    upper_wick_long?: boolean;
  };
  negative?: { negative_news?: boolean };
}

interface Signal {
  stock_code: string;
  stock_name: string;
  market?: string;
  signal_date: string;
  grade?: string;
  score?: ScoreDetail | number;
  entry_price?: number;
  target_price?: number;
  stop_price?: number;
  current_price?: number;
  themes?: string[];
  checklist?: Checklist;
  news_items?: { title: string; summary?: string }[];
  quality?: number;
  change_pct?: number;
}

/* ── helpers ─────────────────────────────────────────────────── */

function getTotal(s: Signal): number {
  if (!s.score) return 0;
  if (typeof s.score === 'object') return s.score.total ?? 0;
  return s.score;
}

function getScoreObj(s: Signal): ScoreDetail {
  if (typeof s.score === 'object') return s.score;
  return {};
}

const GRADE_STYLE: Record<string, { text: string; bg: string; border: string }> = {
  A: { text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' },
  B: { text: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30' },
  C: { text: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30' },
};

const SCORE_BARS: { key: keyof ScoreDetail; label: string; max: number }[] = [
  { key: 'news', label: '뉴스/재료', max: 3 },
  { key: 'volume', label: '거래대금', max: 3 },
  { key: 'chart', label: '차트패턴', max: 3 },
  { key: 'supply', label: '수급', max: 2 },
  { key: 'candle', label: '캔들형태', max: 1 },
  { key: 'consolidation', label: '기간조정', max: 1 },
  { key: 'retracement', label: '조정폭회복', max: 1 },
  { key: 'pullback_support', label: '지지확인', max: 1 },
];

const CHECKLIST_ITEMS: { path: string[]; label: string; positive: boolean }[] = [
  { path: ['mandatory', 'has_news'], label: '뉴스 있음', positive: true },
  { path: ['mandatory', 'volume_sufficient'], label: '거래대금 충분', positive: true },
  { path: ['optional', 'is_new_high'], label: '신고가 돌파', positive: true },
  { path: ['optional', 'is_breakout'], label: '박스권 돌파', positive: true },
  { path: ['optional', 'ma_aligned'], label: '이평선 정렬', positive: true },
  { path: ['optional', 'good_candle'], label: '양호한 캔들', positive: true },
  { path: ['optional', 'supply_positive'], label: '수급 양호', positive: true },
  { path: ['optional', 'retracement_recovery'], label: '조정폭 회복', positive: true },
  { path: ['optional', 'pullback_support_confirmed'], label: '지지선 확인', positive: true },
  { path: ['negative', 'negative_news'], label: '부정 뉴스 없음', positive: false },
];

function getCheckVal(cl: Checklist | undefined, path: string[]): boolean | undefined {
  if (!cl) return undefined;
  const v = (cl as any)[path[0]]?.[path[1]];
  return typeof v === 'boolean' ? v : undefined;
}

function fmt(n?: number) {
  return n != null ? n.toLocaleString() : '--';
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

function ChartModal({ ticker, name, signal, onClose }: { ticker: string; name: string; signal: Signal; onClose: () => void }) {
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
        <div className="grid grid-cols-3 gap-3 mb-4 p-3 rounded-xl bg-white/5 border border-white/8">
          <SignalMeta label="진입가" value={signal.entry_price ? `₩${signal.entry_price.toLocaleString()}` : '--'} className="text-white" />
          <SignalMeta label="손절가" value={signal.stop_price ? `₩${signal.stop_price.toLocaleString()}` : '--'} className="text-blue-400" />
          <SignalMeta label="목표가" value={signal.target_price ? `₩${signal.target_price.toLocaleString()}` : '--'} className="text-emerald-400" />
        </div>

        <div className="grid grid-cols-4 gap-3 mb-4 p-3 rounded-xl bg-white/5 border border-white/8">
          <SignalMeta label="품질점수" value={signal.quality ? `${signal.quality}%` : '--'} className="text-amber-400" />
          <SignalMeta label="종합점수" value={`${getTotal(signal)}점`} className="text-white" />
          <SignalMeta label="주요테마" value={signal.themes?.[0] || '--'} className="text-white truncate col-span-2" />
        </div>
        <div className="h-[400px]">
          <StockChart ticker={ticker} marketType="KR" />
        </div>
      </div>
    </div>
  );
}

/* ── SignalCard ───────────────────────────────────────────────── */

function SignalCard({ signal, livePrice, onClick }: {
  signal: Signal;
  livePrice?: { price: number; change_pct: number };
  onClick: () => void;
}) {
  const grade = signal.grade ?? '';
  const gs = GRADE_STYLE[grade] ?? { text: 'text-gray-400', bg: 'bg-white/5', border: 'border-white/10' };
  const total = getTotal(signal);
  const sc = getScoreObj(signal);
  const isKospi = (signal.market ?? '').toUpperCase().includes('KOSPI');

  // checklist: 값 있는 항목만
  const checkItems = CHECKLIST_ITEMS.map((item) => {
    const val = getCheckVal(signal.checklist, item.path);
    if (val === undefined) return null;
    const pass = item.positive ? val : !val;
    return { label: item.label, pass };
  }).filter(Boolean) as { label: string; pass: boolean }[];

  const liveReturn = (livePrice && signal.entry_price && signal.entry_price > 0)
    ? ((livePrice.price - signal.entry_price) / signal.entry_price * 100)
    : null;

  return (
    <div
      onClick={onClick}
      className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5 cursor-pointer hover:border-violet-500/30 hover:bg-white/[0.02] transition-all group"
    >
      {/* 헤더 */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          {/* 마켓 뱃지 */}
          <div className={`w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-white ${isKospi ? 'bg-gradient-to-br from-rose-500 to-orange-500' : 'bg-gradient-to-br from-blue-500 to-cyan-500'
            }`}>
            {isKospi ? 'KP' : 'KQ'}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-semibold text-white group-hover:text-violet-300 transition-colors truncate">
                {signal.stock_name}
              </p>
              {grade && (
                <span className={`px-1.5 py-0.5 rounded text-[11px] font-bold border ${gs.bg} ${gs.text} ${gs.border}`}>
                  {grade}
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-500 mt-0.5">
              {signal.stock_code}{signal.market ? ` · ${signal.market}` : ''} · {signal.signal_date}
            </p>
          </div>
        </div>

        {/* 점수 + 실시간 */}
        <div className="flex items-center gap-4 flex-shrink-0">
          {liveReturn !== null && (
            <div className="text-right">
              <p className="text-[10px] text-gray-500 uppercase tracking-wide">수익률</p>
              <p className={`text-sm font-bold ${liveReturn >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                {liveReturn >= 0 ? '+' : ''}{liveReturn.toFixed(2)}%
              </p>
              <p className="text-[10px] text-gray-600">{livePrice!.price.toLocaleString()}</p>
            </div>
          )}
          <div className="text-right">
            <p className="text-[10px] text-gray-500 uppercase tracking-wide">Score</p>
            <p className="text-2xl font-black text-violet-400">{total}</p>
          </div>
          <i className="fa-solid fa-chevron-right text-gray-600 group-hover:text-gray-300 text-xs transition-colors" />
        </div>
      </div>

      {/* 진입/목표/손절 */}
      <div className="mt-3 flex gap-4 text-sm">
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wide">진입</p>
          <p className="font-semibold text-white">{fmt(signal.entry_price)}</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wide">목표</p>
          <p className="font-semibold text-emerald-400">{fmt(signal.target_price)}</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wide">손절</p>
          <p className="font-semibold text-red-400">{fmt(signal.stop_price)}</p>
        </div>
        {signal.change_pct != null && (
          <div className="ml-auto">
            <p className="text-[10px] text-gray-500 uppercase tracking-wide">등락률</p>
            <p className={`font-semibold ${signal.change_pct >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
              {signal.change_pct >= 0 ? '+' : ''}{signal.change_pct.toFixed(2)}%
            </p>
          </div>
        )}
      </div>

      {/* 점수 바 차트 */}
      <div className="mt-4 space-y-1.5">
        {SCORE_BARS.map(({ key, label, max }) => {
          const val = (sc[key] as number) ?? 0;
          if (val === 0 && max === 0) return null;
          const pct = max > 0 ? Math.min((val / max) * 100, 100) : 0;
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="text-[10px] text-gray-500 w-20 flex-shrink-0">{label}</span>
              <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full bg-violet-500 transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-[10px] text-gray-500 w-8 text-right">{val}/{max}</span>
            </div>
          );
        })}
      </div>

      {/* 체크리스트 */}
      {checkItems.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
          {checkItems.map(({ label, pass }) => (
            <div key={label} className="flex items-center gap-1.5">
              <i className={`fa-solid ${pass ? 'fa-check-circle text-green-500' : 'fa-times-circle text-red-500'} text-[11px]`} />
              <span className="text-[11px] text-gray-400">{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* 테마 태그 */}
      {(signal.themes ?? []).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {signal.themes!.map((t) => (
            <span key={t} className="px-2 py-0.5 bg-white/5 text-[11px] text-gray-400 rounded-full border border-white/5">
              {t}
            </span>
          ))}
        </div>
      )}

      {/* LLM 근거 */}
      {sc.llm_reason && (
        <p className="mt-3 text-[11px] text-gray-500 leading-relaxed border-t border-white/5 pt-3">
          {sc.llm_reason}
        </p>
      )}
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────── */

export default function ClosingBetPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [date, setDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [dates, setDates] = useState<string[]>([]);
  const [dateCounts, setDateCounts] = useState<Record<string, number>>({});
  const [selectedDate, setSelectedDate] = useState<string | null>(null); // null = 최신

  // 날짜 목록 로드
  useEffect(() => {
    krAPI.getClosingBetDates()
      .then((res) => { setDates(res?.dates ?? []); setDateCounts(res?.counts ?? {}); })
      .catch(() => { });
  }, []);

  const loadData = useCallback(async (dateStr: string | null = null) => {
    setLoading(true);
    try {
      const json = dateStr
        ? await krAPI.getClosingBetHistory(dateStr)
        : await krAPI.getClosingBet();
      setSignals(json.signals ?? []);
      setDate(json.date ?? null);
    } catch {
      setSignals([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(selectedDate); }, [loadData, selectedDate]);

  const tickers = signals.map((s) => s.stock_code).filter(Boolean);
  const { prices, connected } = usePriceStream(tickers);

  const sorted = useMemo(
    () => [...signals].sort((a, b) => getTotal(b) - getTotal(a)),
    [signals]
  );

  // 테마 빈도
  const themeCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of signals) {
      for (const t of s.themes ?? []) map.set(t, (map.get(t) ?? 0) + 1);
    }
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [signals]);

  const selectedSignal = signals.find((s) => s.stock_code === selectedTicker) ?? null;

  return (
    <div className="space-y-6">

      {/* ── Header ───────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">종가베팅</h1>
          <p className="text-gray-400 text-sm mt-1">장 마감 직전 베팅 시그널</p>
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
            <span className="px-3 py-1 rounded-full bg-violet-500/15 border border-violet-500/20 text-sm font-medium text-violet-400">
              {signals.length}개
            </span>
          )}
          <button
            onClick={() => loadData(selectedDate)}
            className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
          >
            <i className={`fa-solid fa-sync-alt text-sm ${loading ? 'animate-spin' : ''}`} />
          </button>
          <div className="flex items-center gap-1.5 text-xs">
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
            <span className={connected ? 'text-green-400' : 'text-gray-500'}>
              {connected ? 'LIVE' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Skeleton ─────────────────────────────────────────── */}
      {loading ? (
        <div className="space-y-4">
          <div className="h-28 rounded-2xl bg-white/5 animate-pulse" />
          <div className="h-24 rounded-2xl bg-white/5 animate-pulse" />
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-64 rounded-2xl bg-white/5 animate-pulse" />
          ))}
        </div>
      ) : sorted.length === 0 ? (

        /* ── Empty ───────────────────────────────────────────── */
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-14 flex flex-col items-center text-center">
          <i className="fa-solid fa-clock text-gray-700 text-5xl mb-4" />
          <p className="text-gray-400 font-medium">현재 활성 종가베팅 시그널이 없습니다.</p>
          <p className="text-gray-600 text-sm mt-1">다음 스캔 결과를 기다려 주세요.</p>
        </div>
      ) : (
        <>
          {/* ── Gate info ────────────────────────────────────── */}
          {date && (
            <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-violet-500/15 flex items-center justify-center flex-shrink-0">
                <i className="fa-solid fa-shield-halved text-violet-400" />
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider">시그널 날짜</p>
                <p className="text-white font-semibold">{date}</p>
              </div>
              <div className="ml-auto text-right">
                <p className="text-xs text-gray-500">총 후보</p>
                <p className="text-white font-semibold">{signals.length}종목</p>
              </div>
            </div>
          )}

          {/* ── Theme cloud ──────────────────────────────────── */}
          {themeCounts.length > 0 && (
            <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">테마 분포</p>
              <div className="flex flex-wrap gap-2">
                {themeCounts.map(([theme, count], idx) => (
                  <span
                    key={theme}
                    className={`px-3 py-1 rounded-full bg-white/5 border border-white/10 ${idx < 5 ? 'text-violet-400' : 'text-gray-400'
                      } ${count >= 3 ? 'text-base font-bold' : count >= 2 ? 'text-sm font-medium' : 'text-xs'}`}
                  >
                    {theme}
                    {count > 1 && (
                      <span className="ml-1 text-[10px] opacity-60">{count}</span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* ── Signal cards ─────────────────────────────────── */}
          <div className="space-y-4">
            {sorted.map((s) => (
              <SignalCard
                key={s.stock_code + s.signal_date}
                signal={s}
                livePrice={prices[s.stock_code.toUpperCase()]}
                onClick={() => setSelectedTicker(s.stock_code)}
              />
            ))}
          </div>
        </>
      )}

      {/* ── Footer ───────────────────────────────────────────── */}
      <div className="flex justify-end pt-2">
        <Link
          href="/dashboard/kr/closing-bet/history"
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          누적 성과 보기 →
        </Link>
      </div>

      {/* ── Chart modal ──────────────────────────────────────── */}
      {selectedTicker && selectedSignal && (
        <ChartModal
          ticker={selectedTicker}
          name={selectedSignal.stock_name}
          signal={selectedSignal}
          onClose={() => setSelectedTicker(null)}
        />
      )}

    </div>
  );
}
