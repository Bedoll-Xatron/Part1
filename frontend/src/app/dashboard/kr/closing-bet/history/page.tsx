'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Pagination from '@/components/ui/Pagination';

/* ── types ───────────────────────────────────────────────────── */

interface CBStats {
  total: number;
  wins: number;
  losses: number;
  open: number;
  win_rate: number;
  avg_roi: number;
  grade_roi?: Record<string, { count: number; win_rate: number; avg_roi: number }>;
}

interface CBSignal {
  stock_code: string;
  stock_name: string;
  signal_date: string;
  grade: string;
  outcome: string;   // STOP_HIT | TARGET_HIT | OPEN
  roi_pct: number;
  entry_price: number;
  target_price?: number;
  stop_price?: number;
  days_held?: number;
  themes?: string[];
}

type SortKey = 'signal_date' | 'roi_pct' | 'grade' | 'days_held' | 'outcome';

/* ── helpers ─────────────────────────────────────────────────── */

const PAGE_SIZE = 30;

const GRADE: Record<string, { text: string; bg: string; border: string }> = {
  A: { text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' },
  B: { text: 'text-blue-400',    bg: 'bg-blue-500/10',    border: 'border-blue-500/30'    },
  C: { text: 'text-yellow-400',  bg: 'bg-yellow-500/10',  border: 'border-yellow-500/30'  },
};

const OUTCOME_LABEL: Record<string, { label: string; color: string }> = {
  TARGET_HIT: { label: '목표달성', color: 'text-emerald-400' },
  STOP_HIT:   { label: '손절',     color: 'text-red-400'     },
  OPEN:       { label: '보유중',   color: 'text-amber-400'   },
};

function outcomeStyle(o: string) {
  return OUTCOME_LABEL[o] ?? { label: o, color: 'text-gray-400' };
}

/* ── SortTh ──────────────────────────────────────────────────── */

function SortTh({ label, colKey, current, dir, onSort }: {
  label: string; colKey: SortKey; current: SortKey;
  dir: 'asc' | 'desc'; onSort: (k: SortKey) => void;
}) {
  const active = colKey === current;
  return (
    <th onClick={() => onSort(colKey)} className="text-left px-4 py-3 cursor-pointer select-none group whitespace-nowrap">
      <span className={`inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider transition-colors ${active ? 'text-violet-400' : 'text-gray-500 group-hover:text-gray-300'}`}>
        {label}
        <span className="text-[10px]">
          {active ? (dir === 'asc' ? '↑' : '↓') : <span className="text-gray-600">↕</span>}
        </span>
      </span>
    </th>
  );
}

/* ── Page ────────────────────────────────────────────────────── */

export default function ClosingBetHistoryPage() {
  const [stats, setStats]     = useState<CBStats | null>(null);
  const [signals, setSignals] = useState<CBSignal[]>([]);
  const [loading, setLoading] = useState(true);

  const [outcomeFilter, setOutcomeFilter] = useState('ALL');
  const [gradeFilter,   setGradeFilter]   = useState('ALL');
  const [monthFilter,   setMonthFilter]   = useState('ALL');

  const [sortKey, setSortKey] = useState<SortKey>('signal_date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [page, setPage]       = useState(1);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef  = useRef<any>(null);

  /* ── load ───────────────────────────────────────────────────── */

  useEffect(() => {
    fetch('/api/kr/jongga-v2/cumulative?page=1&per_page=9999')
      .then((r) => r.json())
      .then((d) => {
        setStats(d?.stats ?? null);
        setSignals(d?.signals ?? []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  /* ── derived ────────────────────────────────────────────────── */

  const months = useMemo(() => {
    const s = new Set(signals.map((s) => s.signal_date.slice(0, 7)));
    return Array.from(s).sort((a, b) => b.localeCompare(a));
  }, [signals]);

  const filteredSorted = useMemo(() => {
    let arr = [...signals];
    if (outcomeFilter !== 'ALL') arr = arr.filter((s) => s.outcome === outcomeFilter);
    if (gradeFilter   !== 'ALL') arr = arr.filter((s) => s.grade   === gradeFilter);
    if (monthFilter   !== 'ALL') arr = arr.filter((s) => s.signal_date.startsWith(monthFilter));

    arr.sort((a, b) => {
      let av: any, bv: any;
      switch (sortKey) {
        case 'signal_date': av = a.signal_date; bv = b.signal_date; break;
        case 'roi_pct':     av = a.roi_pct;     bv = b.roi_pct;     break;
        case 'grade':       av = a.grade;       bv = b.grade;       break;
        case 'days_held':   av = a.days_held;   bv = b.days_held;   break;
        case 'outcome':     av = a.outcome;     bv = b.outcome;     break;
        default: av = 0; bv = 0;
      }
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return arr;
  }, [signals, outcomeFilter, gradeFilter, monthFilter, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filteredSorted.length / PAGE_SIZE));
  const paged = filteredSorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // 차트 데이터 (CLOSED만, 날짜 중복 제거)
  const chartData = useMemo(() => {
    const closed = signals
      .filter((s) => s.outcome !== 'OPEN')
      .sort((a, b) => a.signal_date.localeCompare(b.signal_date));
    let cum = 0;
    const cumByDate = new Map<string, number>();
    for (const s of closed) {
      cum = parseFloat((cum + s.roi_pct).toFixed(2));
      cumByDate.set(s.signal_date, cum);
    }
    return Array.from(cumByDate.entries())
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([time, value]) => ({ time, value }));
  }, [signals]);

  /* ── chart effect ───────────────────────────────────────────── */

  useEffect(() => {
    if (!chartContainerRef.current) return;
    let cancelled = false;
    let resizeObs: ResizeObserver | null = null;

    import('lightweight-charts').then((lc) => {
      if (cancelled || !chartContainerRef.current) return;

      const chart = (() => { try { return (lc as any).createChart(chartContainerRef.current!, {
        width:  chartContainerRef.current!.clientWidth,
        height: 260,
        layout: { background: { color: '#1c1c1e' } as any, textColor: '#9ca3af' },
        grid:   { vertLines: { color: 'rgba(255,255,255,0.03)' }, horzLines: { color: 'rgba(255,255,255,0.03)' } },
        rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)' },
        timeScale:       { borderColor: 'rgba(255,255,255,0.08)', timeVisible: false },
      }); } catch { return null; } })();
      if (!chart || cancelled) return;
      chartInstanceRef.current = chart;

      const seriesOpts = {
        baseValue:       { type: 'price' as const, price: 0 },
        topLineColor:    '#8b5cf6',
        topFillColor1:   'rgba(139,92,246,0.2)',
        topFillColor2:   'rgba(139,92,246,0.02)',
        bottomLineColor: '#ef4444',
        bottomFillColor1:'rgba(239,68,68,0.02)',
        bottomFillColor2:'rgba(239,68,68,0.2)',
        lineWidth: 2 as const,
      };
      let series: any;
      try { series = (chart as any).addSeries((lc as any).BaselineSeries, seriesOpts); }
      catch { series = (chart as any).addBaselineSeries(seriesOpts); }

      if (chartData.length > 0) {
        series.setData(chartData);
        (chart as any).timeScale().fitContent();
      }

      resizeObs = new ResizeObserver(() => {
        if (chartContainerRef.current && chartInstanceRef.current)
          chartInstanceRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      });
      resizeObs.observe(chartContainerRef.current);
    });

    return () => {
      cancelled = true;
      resizeObs?.disconnect();
      if (chartInstanceRef.current) { chartInstanceRef.current.remove(); chartInstanceRef.current = null; }
    };
  }, [chartData]);

  /* ── sort / filter handlers ─────────────────────────────────── */

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('desc'); }
    setPage(1);
  };

  /* ── render ─────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-56 rounded-lg bg-white/5 animate-pulse" />
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-20 rounded-xl bg-white/5 animate-pulse" />)}
        </div>
        <div className="h-[260px] rounded-2xl bg-white/5 animate-pulse" />
        <div className="h-[400px] rounded-2xl bg-white/5 animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-4">

      {/* ── Header ───────────────────────────────────────────── */}
      <div>
        <h1 className="text-3xl font-bold text-white">종가베팅 누적 성과</h1>
        <p className="text-gray-400 text-sm mt-1">전체 종가베팅 시그널 히스토리</p>
      </div>

      {/* ── Stats cards ──────────────────────────────────────── */}
      {stats ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            {[
              { label: 'Total',    value: String(stats.total),   color: 'text-white' },
              { label: 'Win',      value: String(stats.wins),    color: 'text-emerald-400' },
              { label: 'Loss',     value: String(stats.losses),  color: 'text-red-400' },
              { label: 'Open',     value: String(stats.open),    color: 'text-amber-400' },
              {
                label: 'Win Rate',
                value: `${stats.win_rate.toFixed(1)}%`,
                color: stats.win_rate >= 60 ? 'text-emerald-400' : stats.win_rate >= 40 ? 'text-yellow-400' : 'text-red-400',
              },
              {
                label: 'Avg ROI',
                value: `${stats.avg_roi >= 0 ? '+' : ''}${stats.avg_roi.toFixed(2)}%`,
                color: stats.avg_roi >= 0 ? 'text-violet-400' : 'text-red-400',
              },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-[#1a1f2e] border border-white/10 rounded-xl p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">{label}</p>
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Grade sub-stats */}
          {stats.grade_roi && Object.keys(stats.grade_roi).length > 0 && (
            <div className="flex gap-4 flex-wrap text-xs text-gray-500 px-1">
              {Object.entries(stats.grade_roi).map(([g, gs]) => (
                <span key={g}>
                  <span className={GRADE[g]?.text ?? 'text-gray-400'}>{g}등급</span>
                  {' '}{gs.count}건 · 승률 {gs.win_rate.toFixed(0)}% · 평균 {gs.avg_roi >= 0 ? '+' : ''}{gs.avg_roi.toFixed(1)}%
                </span>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-6 text-center text-gray-500 text-sm">
          통계 데이터가 없습니다.
        </div>
      )}

      {/* ── Cumulative ROI chart ──────────────────────────────── */}
      <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-4">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">누적 수익률 곡선</p>
        <div className="h-[260px] relative">
          <div ref={chartContainerRef} className="w-full h-full" />
          {chartData.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
              <i className="fa-solid fa-chart-line text-gray-700 text-3xl mb-2" />
              <p className="text-gray-500 text-sm">종결 시그널 데이터 없음</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Filters ──────────────────────────────────────────── */}
      <div className="flex gap-3 flex-wrap items-center">
        {/* Outcome */}
        <div className="flex rounded-lg overflow-hidden border border-white/10">
          {(['ALL', 'TARGET_HIT', 'STOP_HIT', 'OPEN'] as const).map((v) => (
            <button
              key={v}
              onClick={() => { setOutcomeFilter(v); setPage(1); }}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                outcomeFilter === v ? 'bg-white/10 text-white' : 'bg-white/5 text-gray-400 hover:text-white'
              }`}
            >
              {v === 'ALL' ? '전체' : v === 'TARGET_HIT' ? '목표달성' : v === 'STOP_HIT' ? '손절' : '보유중'}
            </button>
          ))}
        </div>

        {/* Grade */}
        <select
          value={gradeFilter}
          onChange={(e) => { setGradeFilter(e.target.value); setPage(1); }}
          className="bg-[#1a1f2e] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-gray-400 focus:outline-none focus:border-white/30"
        >
          <option value="ALL">등급 전체</option>
          {['A', 'B', 'C'].map((g) => <option key={g} value={g}>등급 {g}</option>)}
        </select>

        {/* Month */}
        <select
          value={monthFilter}
          onChange={(e) => { setMonthFilter(e.target.value); setPage(1); }}
          className="bg-[#1a1f2e] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-gray-400 focus:outline-none focus:border-white/30"
        >
          <option value="ALL">월 전체</option>
          {months.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>

        <span className="text-xs text-gray-600 ml-auto">{filteredSorted.length}건</span>
      </div>

      {/* ── Table ────────────────────────────────────────────── */}
      {filteredSorted.length === 0 ? (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-10 text-center text-gray-500 text-sm">
          조건에 맞는 시그널이 없습니다.
        </div>
      ) : (
        <>
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-white/5 border-b border-white/10">
                    <SortTh label="날짜"   colKey="signal_date" current={sortKey} dir={sortDir} onSort={handleSort} />
                    <th className="text-left px-4 py-3 text-[11px] text-gray-500 font-semibold uppercase tracking-wider">종목</th>
                    <SortTh label="등급"   colKey="grade"       current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="결과"   colKey="outcome"     current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="ROI"    colKey="roi_pct"     current={sortKey} dir={sortDir} onSort={handleSort} />
                    <th className="text-left px-4 py-3 text-[11px] text-gray-500 font-semibold uppercase tracking-wider whitespace-nowrap">진입가</th>
                    <th className="text-left px-4 py-3 text-[11px] text-gray-500 font-semibold uppercase tracking-wider whitespace-nowrap">목표가</th>
                    <th className="text-left px-4 py-3 text-[11px] text-gray-500 font-semibold uppercase tracking-wider whitespace-nowrap">손절가</th>
                    <SortTh label="보유일" colKey="days_held"   current={sortKey} dir={sortDir} onSort={handleSort} />
                    <th className="text-left px-4 py-3 text-[11px] text-gray-500 font-semibold uppercase tracking-wider">테마</th>
                  </tr>
                </thead>
                <tbody>
                  {paged.map((s, i) => {
                    const gs = GRADE[s.grade] ?? { text: 'text-gray-400', bg: 'bg-white/5', border: 'border-white/10' };
                    const os = outcomeStyle(s.outcome);
                    return (
                      <tr key={s.stock_code + s.signal_date + i} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                        <td className="px-4 py-3 text-gray-400 whitespace-nowrap">{s.signal_date}</td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-white">{s.stock_name}</p>
                          <p className="text-xs text-gray-600">{s.stock_code}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded text-xs font-bold border ${gs.bg} ${gs.text} ${gs.border}`}>
                            {s.grade || '-'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium ${os.color}`}>{os.label}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`font-semibold ${s.roi_pct >= 0 ? 'text-violet-400' : 'text-red-400'}`}>
                            {s.roi_pct >= 0 ? '+' : ''}{s.roi_pct.toFixed(2)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-300">{s.entry_price?.toLocaleString() ?? '-'}</td>
                        <td className="px-4 py-3 text-emerald-400/70">{s.target_price?.toLocaleString() ?? '-'}</td>
                        <td className="px-4 py-3 text-red-400/70">{s.stop_price?.toLocaleString() ?? '-'}</td>
                        <td className="px-4 py-3 text-gray-400">{s.days_held != null ? `${s.days_held}일` : '-'}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs">
                          {s.themes?.[0] ?? '-'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
