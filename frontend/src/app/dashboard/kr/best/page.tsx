'use client';

import { useEffect, useRef, useState } from 'react';
import { krAPI } from '@/lib/api';
import StockChart from '@/components/ui/StockChart';

/* ── types ───────────────────────────────────────────────────── */

interface BestSignal {
  ticker: string;
  name: string;
  market: string;
  score: number;
  source_strategy: 'flow-momentum' | 'narrative-momentum' | 'sector-rotation' | 'contrarian-reversal';
  key_metric_label: string;
  key_metric_value: string;
}

interface KRStockAISummary {
  ticker: string;
  summary: string;
  outlook: string;
  risk_factors: string[];
  catalysts: string[];
}

interface AggregatedBestSignal {
  ticker: string;
  name: string;
  market: string;
  maxScore: number;
  signals: BestSignal[];
}

interface StrategyStats {
  total: number;
  avg_score: number;
}

/* ── constants ───────────────────────────────────────────────── */

const STRATEGY_META = {
  'flow-momentum': {
    label: '수급',
    icon: 'fa-water',
    color: 'cyan',
    border: 'hover:border-cyan-500/30',
    iconCls: 'text-cyan-400',
    textCls: 'text-cyan-400',
    bgCls: 'bg-cyan-400/15',
  },
  'narrative-momentum': {
    label: '테마',
    icon: 'fa-newspaper',
    color: 'orange',
    border: 'hover:border-orange-500/30',
    iconCls: 'text-orange-400',
    textCls: 'text-orange-400',
    bgCls: 'bg-orange-400/15',
  },
  'sector-rotation': {
    label: '섹터',
    icon: 'fa-rotate',
    color: 'emerald',
    border: 'hover:border-emerald-500/30',
    iconCls: 'text-emerald-400',
    textCls: 'text-emerald-400',
    bgCls: 'bg-emerald-400/15',
  },
  'contrarian-reversal': {
    label: '역발상',
    icon: 'fa-arrow-trend-up',
    color: 'rose',
    border: 'hover:border-rose-500/30',
    iconCls: 'text-rose-400',
    textCls: 'text-rose-400',
    bgCls: 'bg-rose-400/15',
  },
} as const;

const MEDAL_LABELS = ['1st', '2nd', '3rd'];
const MEDAL_CLS = [
  'text-amber-400 font-bold',
  'text-gray-300 font-bold',
  'text-amber-600 font-bold',
];

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
  aggSignal,
  onClose,
}: {
  ticker: string;
  name: string;
  aggSignal: AggregatedBestSignal;
  onClose: () => void;
}) {
  const [analysis, setAnalysis] = useState<KRStockAISummary | null>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  useEffect(() => {
    setLoadingAnalysis(true);
    krAPI.getStockAISummary(ticker)
      .then(setAnalysis)
      .catch(() => { })
      .finally(() => setLoadingAnalysis(false));
  }, [ticker]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl my-auto" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="p-5 border-b border-white/5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-2xl flex items-center justify-center text-xs font-bold text-white shadow-lg ${!(aggSignal.market?.toUpperCase().includes('KOSDAQ'))
                ? 'bg-gradient-to-br from-rose-500 to-orange-500 shadow-rose-500/20'
                : 'bg-gradient-to-br from-blue-500 to-cyan-500 shadow-blue-500/20'
                }`}>
                {!(aggSignal.market?.toUpperCase().includes('KOSDAQ')) ? 'KOSPI' : 'KOSDAQ'}
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">{name}</h3>
                <p className="text-gray-500 text-sm tracking-widest">{ticker}</p>
              </div>
            </div>
            <button onClick={onClose} className="w-10 h-10 rounded-xl flex items-center justify-center text-gray-500 hover:text-white hover:bg-white/5 transition-colors">
              <i className="fa-solid fa-xmark text-lg" />
            </button>
          </div>

          <div className="flex flex-col gap-3">
            {aggSignal.signals.map((s, idx) => {
              const meta = STRATEGY_META[s.source_strategy as keyof typeof STRATEGY_META];
              return (
                <div key={idx} className="flex items-center gap-8 py-2 px-4 bg-white/[0.02] rounded-xl border border-white/5">
                  <div className="flex items-center gap-2 min-w-[100px]">
                    <i className={`fa-solid ${meta?.icon} ${meta?.iconCls} text-xs`} />
                    <span className={`text-xs font-bold ${meta?.textCls}`}>{meta?.label}</span>
                  </div>
                  <div className="w-px h-6 bg-white/10" />
                  <SignalMeta label="Score" value={`${s.score}/10`} className="text-amber-400" />
                  <div className="w-px h-6 bg-white/10" />
                  <SignalMeta label={s.key_metric_label} value={s.key_metric_value} className="text-white" />
                </div>
              );
            })}
          </div>
        </div>

        {/* Scrollable Container */}
        <div className="max-h-[70vh] overflow-y-auto scrollbar-hide">
          {/* Chart View */}
          <div className="p-5 h-[400px]">
            <StockChart ticker={ticker} marketType="KR" />
          </div>

          {/* AI Analysis Section */}
          <div className="px-5 pb-8 space-y-6">
            <div className="h-px bg-white/5" />

            <div className="flex items-center gap-2 text-amber-400">
              <i className="fa-solid fa-wand-magic-sparkles text-sm" />
              <h4 className="text-sm font-bold uppercase tracking-widest">AI 분석 근거</h4>
            </div>

            {loadingAnalysis ? (
              <div className="space-y-3 animate-pulse">
                <div className="h-4 bg-white/5 rounded w-3/4" />
                <div className="h-4 bg-white/5 rounded w-full" />
                <div className="h-4 bg-white/5 rounded w-1/2" />
              </div>
            ) : analysis ? (
              <div className="space-y-5">
                <div>
                  <p className="text-gray-200 text-sm leading-relaxed whitespace-pre-wrap">
                    {analysis.summary}
                  </p>
                  <p className="text-gray-400 text-xs mt-2 italic font-serif">
                    {analysis.outlook}
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Catalysts */}
                  <div className="space-y-2">
                    <p className="text-[10px] text-emerald-400 font-bold uppercase tracking-tighter">Catalysts (호재)</p>
                    <div className="flex flex-wrap gap-1.5">
                      {analysis.catalysts.map((c, i) => (
                        <span key={i} className="px-2 py-1 bg-emerald-500/10 text-emerald-300 text-[11px] rounded-lg border border-emerald-500/20">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Risks */}
                  <div className="space-y-2">
                    <p className="text-[10px] text-rose-400 font-bold uppercase tracking-tighter">Risk Factors (리스크)</p>
                    <div className="flex flex-wrap gap-1.5">
                      {analysis.risk_factors.map((r, i) => (
                        <span key={i} className="px-2 py-1 bg-rose-500/10 text-rose-300 text-[11px] rounded-lg border border-rose-500/20">
                          {r}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-gray-500 text-sm italic">분석 리포트를 불러올 수 없습니다.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── StrategyCard ─────────────────────────────────────────────── */

function StrategyCard({
  stratKey,
  stats,
}: {
  stratKey: keyof typeof STRATEGY_META;
  stats: StrategyStats | null;
}) {
  const meta = STRATEGY_META[stratKey];
  return (
    <div
      className={`bg-[#1a1f2e] border border-white/10 rounded-xl p-4 transition-all ${meta.border}`}
    >
      <div className="flex items-center gap-2 mb-3">
        <i className={`fa-solid ${meta.icon} ${meta.iconCls}`} />
        <span className="text-white font-medium text-xs">{meta.label} 모멘텀</span>
      </div>
      <p className="text-2xl font-bold text-white">{stats?.total ?? '--'}</p>
      <div className="flex items-center justify-between mt-1">
        <p className={`text-[10px] ${meta.textCls}`}>
          Avg Score {stats ? stats.avg_score.toFixed(1) : '--'}
        </p>
      </div>
    </div>
  );
}

/* ── StrategyBadge ───────────────────────────────────────────── */

function StrategyBadge({ strategy }: { strategy: string }) {
  const meta = STRATEGY_META[strategy as keyof typeof STRATEGY_META];
  if (!meta) return null;
  return (
    <span title={meta.label} className={`w-8 h-8 rounded-xl flex items-center justify-center text-xs ${meta.bgCls} ${meta.textCls} border border-white/10 shadow-lg`}>
      <i className={`fa-solid ${meta.icon}`} />
    </span>
  );
}

/* ── page ────────────────────────────────────────────────────── */

export default function BestOfBestPage() {
  const [signals, setSignals] = useState<AggregatedBestSignal[]>([]);
  const [stats, setStats] = useState<StrategyStats | null>(null);
  const [subStats, setSubStats] = useState<Record<string, StrategyStats>>({});
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<{ ticker: string; name: string; aggSignal: AggregatedBestSignal } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [best, flow, narrative, sector, contrarian] = await Promise.all([
          krAPI.getBestStrategy(),
          krAPI.getStrategy('flow-momentum'),
          krAPI.getStrategy('narrative-momentum'),
          krAPI.getStrategy('sector-rotation'),
          krAPI.getStrategy('contrarian-reversal'),
        ]);
        if (cancelled) return;

        const rawSignals = (best.signals ?? []) as BestSignal[];
        const grouped = new Map<string, BestSignal[]>();
        rawSignals.forEach((s) => {
          if (!grouped.has(s.ticker)) grouped.set(s.ticker, []);
          grouped.get(s.ticker)!.push(s);
        });

        const aggregated: AggregatedBestSignal[] = Array.from(grouped.entries()).map(([ticker, sigs]) => {
          const first = sigs[0];
          return {
            ticker,
            name: first.name,
            market: first.market,
            maxScore: Math.max(...sigs.map(s => s.score)),
            signals: sigs.sort((a, b) => b.score - a.score),
          };
        }).sort((a, b) => b.maxScore - a.maxScore);

        setSignals(aggregated);
        setStats(best.stats ?? null);
        setSubStats({
          'flow-momentum': flow.stats,
          'narrative-momentum': narrative.stats,
          'sector-rotation': sector.stats,
          'contrarian-reversal': contrarian.stats,
        });
      } catch { /* no-op */ }
      if (!cancelled) setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  const sortedStrategies = Object.keys(STRATEGY_META) as (keyof typeof STRATEGY_META)[];

  return (
    <>
      {modal && (
        <ChartModal
          ticker={modal.ticker}
          name={modal.name}
          aggSignal={modal.aggSignal}
          onClose={() => setModal(null)}
        />
      )}

      <div className="space-y-4">
        {/* ── 헤더 ── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Best of Best</h1>
            <p className="text-gray-400 mt-1">전 전략 통합 랭킹 · 중복 전략 자동 취합</p>
          </div>
          {stats && (
            <span className="bg-amber-500/15 text-amber-400 px-3 py-1 rounded-full text-sm font-medium">
              {stats.total}개 시그널
            </span>
          )}
        </div>

        {/* ── 전략 피트니스 카드 ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {sortedStrategies.map(key => (
            <StrategyCard key={key} stratKey={key} stats={subStats[key] ?? null} />
          ))}
        </div>

        {/* ── 통합 랭킹 테이블 ── */}
        <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl overflow-hidden mt-4">
          <div className="grid grid-cols-[2rem_2.75rem_1fr_4.5rem_8rem_1.2fr] gap-3 px-5 py-3 border-b border-white/10 text-[10px] text-gray-500 uppercase tracking-widest font-bold">
            <span>#</span>
            <span></span>
            <span>종목</span>
            <span className="text-center">최고점</span>
            <span className="text-center">취합 전략</span>
            <span>통합 지표</span>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-16 text-gray-500 gap-2">
              <i className="fa-solid fa-spinner fa-spin" />
              <span>로딩 중...</span>
            </div>
          )}

          {!loading && signals.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-gray-600 gap-3">
              <i className="fa-solid fa-trophy text-4xl text-amber-800/50" />
              <p className="text-sm">각 전략 엔진을 먼저 실행하세요</p>
            </div>
          )}

          {!loading && signals.map((agg, idx) => {
            const isMedal = idx < 3;
            const isKospi = !(agg.market?.toUpperCase().includes('KOSDAQ'));
            const rowCls = isMedal
              ? 'bg-amber-500/5 hover:bg-amber-500/10'
              : 'hover:bg-white/5';

            return (
              <div
                key={agg.ticker}
                className={`grid grid-cols-[2rem_2.75rem_1fr_4.5rem_8rem_1.2fr] gap-3 px-5 py-3.5 border-b border-white/5 last:border-0 cursor-pointer transition-colors ${rowCls}`}
                onClick={() => setModal({ ticker: agg.ticker, name: agg.name, aggSignal: agg })}
              >
                <span className={`text-sm self-center ${isMedal ? MEDAL_CLS[idx] : 'text-gray-600'}`}>
                  {isMedal ? MEDAL_LABELS[idx] : idx + 1}
                </span>

                <div className={`w-9 h-9 rounded-xl self-center flex items-center justify-center text-[10px] font-black text-white flex-shrink-0 ${isKospi
                  ? 'bg-gradient-to-br from-rose-500 to-orange-500 shadow-lg shadow-rose-500/10'
                  : 'bg-gradient-to-br from-blue-500 to-cyan-500 shadow-lg shadow-blue-500/10'
                  }`}>
                  {isKospi ? 'KP' : 'KQ'}
                </div>

                <div className="self-center min-w-0">
                  <p className="text-white text-sm font-bold leading-tight truncate">{agg.name}</p>
                  <p className="text-gray-600 text-[10px] font-medium tracking-wider uppercase mt-0.5">{agg.ticker}</p>
                </div>

                <div className="self-center text-center">
                  <span className={`text-lg font-black ${isMedal ? 'text-amber-400' : 'text-amber-300'}`}>
                    {agg.maxScore}
                  </span>
                </div>

                <div className="self-center flex items-center justify-center gap-2 flex-wrap">
                  {agg.signals.map(s => (
                    <StrategyBadge key={s.source_strategy} strategy={s.source_strategy} />
                  ))}
                </div>

                <div className="self-center space-y-1">
                  {agg.signals.slice(0, 2).map((s, idx) => (
                    <div key={idx} className="flex items-center gap-1.5 overflow-hidden">
                      <span className={`text-[10px] font-bold ${STRATEGY_META[s.source_strategy as keyof typeof STRATEGY_META]?.textCls} whitespace-nowrap`}>
                        {STRATEGY_META[s.source_strategy as keyof typeof STRATEGY_META]?.label}
                      </span>
                      <span className="text-[10px] text-gray-400 truncate opacity-80">{s.key_metric_value}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
