'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { krAPI } from '@/lib/api';
import Pagination from '@/components/ui/Pagination';

/* ── types ───────────────────────────────────────────────────── */

interface VCPStats {
  total: number;
  closed: number;
  open: number;
  win_rate: number;
  avg_return: number;
  total_return?: number;
  grade_stats?: Record<string, { count: number; win_rate: number; avg_return: number }>;
}

interface VCPCumulativeSignal {
  ticker?: string;
  stock_code?: string;
  name?: string;
  stock_name?: string;
  market: string;
  signal_date: string;
  entry_price: number;
  exit_price?: number;
  return_pct: number;
  score: number | { total: number };
  grade: string;
  hold_days: number;
  status: 'CLOSED' | 'OPEN';
}

type SortKey = 'signal_date' | 'return_pct' | 'score' | 'hold_days' | 'ticker' | 'grade';

/* ── helpers ─────────────────────────────────────────────────── */

const PAGE_SIZE = 30;

function getTicker(s: VCPCumulativeSignal): string { return s.stock_code ?? s.ticker ?? ''; }
function getName(s: VCPCumulativeSignal): string   { return s.stock_name ?? s.name ?? ''; }
function getScore(s: VCPCumulativeSignal): number {
  if (s.score && typeof s.score === 'object') return (s.score as any).total ?? 0;
  return typeof s.score === 'number' ? s.score : 0;
}

const GRADE: Record<string, { text: string; bg: string; border: string }> = {
  A: { text: 'text-green-400',  bg: 'bg-green-400/10',  border: 'border-green-400/30' },
  B: { text: 'text-blue-400',   bg: 'bg-blue-400/10',   border: 'border-blue-400/30' },
  C: { text: 'text-yellow-400', bg: 'bg-yellow-400/10', border: 'border-yellow-400/30' },
  D: { text: 'text-red-400',    bg: 'bg-red-400/10',    border: 'border-red-400/30' },
};

/* ── sub-components ──────────────────────────────────────────── */

function SortTh({
  label, colKey, current, dir, onSort,
}: {
  label: string;
  colKey: SortKey;
  current: SortKey;
  dir: 'asc' | 'desc';
  onSort: (k: SortKey) => void;
}) {
  const active = colKey === current;
  return (
    <th
      onClick={() => onSort(colKey)}
      className="text-left px-4 py-3 cursor-pointer select-none group whitespace-nowrap"
    >
      <span className={`inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider transition-colors ${active ? 'text-rose-400' : 'text-gray-500 group-hover:text-gray-300'}`}>
        {label}
        <span className="text-[10px]">
          {active ? (dir === 'asc' ? '↑' : '↓') : <span className="text-gray-600">↕</span>}
        </span>
      </span>
    </th>
  );
}

/* ── page ────────────────────────────────────────────────────── */

export default function VCPHistoryPage() {
  const [stats, setStats]     = useState<VCPStats | null>(null);
  const [signals, setSignals] = useState<VCPCumulativeSignal[]>([]);
  const [loading, setLoading] = useState(true);

  // filters
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'CLOSED' | 'OPEN'>('ALL');
  const [gradeFilter,  setGradeFilter]  = useState('ALL');
  const [monthFilter,  setMonthFilter]  = useState('ALL');

  // sort
  const [sortKey, setSortKey] = useState<SortKey>('signal_date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  // pagination
  const [page, setPage] = useState(1);

  // chart
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef  = useRef<any>(null);

  /* ── data load ─────────────────────────────────────────────── */

  useEffect(() => {
    krAPI.getVCPCumulative()
      .then((res: any) => {
        setStats(res?.stats ?? null);
        setSignals(res?.signals ?? []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  /* ── derived ───────────────────────────────────────────────── */

  const months = useMemo(() => {
    const set = new Set(signals.map((s) => s.signal_date.slice(0, 7)));
    return Array.from(set).sort((a, b) => b.localeCompare(a));
  }, [signals]);

  const filteredSorted = useMemo(() => {
    let arr = [...signals];
    if (statusFilter !== 'ALL') arr = arr.filter((s) => s.status === statusFilter);
    if (gradeFilter  !== 'ALL') arr = arr.filter((s) => s.grade  === gradeFilter);
    if (monthFilter  !== 'ALL') arr = arr.filter((s) => s.signal_date.startsWith(monthFilter));

    arr.sort((a, b) => {
      let av: any, bv: any;
      switch (sortKey) {
        case 'signal_date': av = a.signal_date; bv = b.signal_date; break;
        case 'return_pct':  av = a.return_pct;  bv = b.return_pct;  break;
        case 'score':       av = getScore(a);   bv = getScore(b);   break;
        case 'hold_days':   av = a.hold_days;   bv = b.hold_days;   break;
        case 'ticker':      av = getTicker(a);  bv = getTicker(b);  break;
        case 'grade':       av = a.grade;       bv = b.grade;       break;
        default:            av = 0;             bv = 0;
      }
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return arr;
  }, [signals, statusFilter, gradeFilter, monthFilter, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filteredSorted.length / PAGE_SIZE));
  const paged = filteredSorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const chartData = useMemo(() => {
    const closed = signals
      .filter((s) => s.status === 'CLOSED')
      .sort((a, b) => a.signal_date.localeCompare(b.signal_date));
    let cum = 0;
    const cumByDate = new Map<string, number>();
    for (const s of closed) {
      cum = parseFloat((cum + s.return_pct).toFixed(2));
      cumByDate.set(s.signal_date, cum);
    }
    return Array.from(cumByDate.entries())
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([time, value]) => ({ time: time as any, value }));
  }, [signals]);

  /* ── chart effect ──────────────────────────────────────────── */

  useEffect(() => {
    const el = chartContainerRef.current;
    if (!el || chartData.length === 0) return;
    let cancelled = false;

    import('lightweight-charts').then((lc) => {
      if (cancelled || !chartContainerRef.current) return;

      // 명시적 크기로 초기화
      const w = chartContainerRef.current.clientWidth  || 600;
      const h = chartContainerRef.current.clientHeight || 300;

      const chart = (() => { try {
        return (lc as any).createChart(chartContainerRef.current!, {
          width: w, height: h,
          layout: { background: { color: '#1c1c1e' } as any, textColor: '#9ca3af' },
          grid: { vertLines: { color: 'rgba(255,255,255,0.03)' }, horzLines: { color: 'rgba(255,255,255,0.03)' } },
          rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
          timeScale: { borderColor: 'rgba(255,255,255,0.1)', timeVisible: false },
          crosshair: { mode: 0 },
        });
      } catch { return null; } })();
      if (!chart || cancelled) return;
      chartInstanceRef.current = chart;

      // 0 기준점 추가 → 단일 데이터도 선으로 보임
      const firstDate = chartData[0].time as string;
      const [y, m, d] = firstDate.split('-').map(Number);
      const prevDate = new Date(y, m - 1, d - 1);
      const pad = (n: number) => String(n).padStart(2, '0');
      const zeroPoint = {
        time: `${prevDate.getFullYear()}-${pad(prevDate.getMonth()+1)}-${pad(prevDate.getDate())}` as any,
        value: 0,
      };
      const data = [zeroPoint, ...chartData];

      let series: any;
      try {
        series = (chart as any).addSeries((lc as any).BaselineSeries, {
          baseValue: { type: 'price' as const, price: 0 },
          topLineColor:     '#22c55e',
          topFillColor1:    'rgba(34,197,94,0.2)',
          topFillColor2:    'rgba(34,197,94,0.0)',
          bottomLineColor:  '#ef4444',
          bottomFillColor1: 'rgba(239,68,68,0.0)',
          bottomFillColor2: 'rgba(239,68,68,0.2)',
          lineWidth: 2 as const,
        });
      } catch {
        series = (chart as any).addBaselineSeries({
          baseValue: { type: 'price' as const, price: 0 },
          topLineColor: '#22c55e', bottomLineColor: '#ef4444', lineWidth: 2 as const,
        });
      }

      series.setData(data);
      (chart as any).timeScale().fitContent();

      // 리사이즈 대응
      const ro = new ResizeObserver(() => {
        if (chartInstanceRef.current && chartContainerRef.current) {
          chartInstanceRef.current.applyOptions({
            width:  chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
          });
        }
      });
      ro.observe(chartContainerRef.current);

      const origCleanup = () => {
        ro.disconnect();
        if (chartInstanceRef.current) { chartInstanceRef.current.remove(); chartInstanceRef.current = null; }
      };
      (chartContainerRef as any)._cleanup = origCleanup;
    });

    return () => {
      cancelled = true;
      if ((chartContainerRef as any)._cleanup) { (chartContainerRef as any)._cleanup(); }
      else if (chartInstanceRef.current) { chartInstanceRef.current.remove(); chartInstanceRef.current = null; }
    };
  }, [chartData]);

  /* ── sort handler ──────────────────────────────────────────── */

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('desc'); }
    setPage(1);
  };

  /* ── filter change resets page ─────────────────────────────── */

  const setStatus = (v: 'ALL' | 'CLOSED' | 'OPEN') => { setStatusFilter(v); setPage(1); };
  const setGrade  = (v: string) => { setGradeFilter(v);  setPage(1); };
  const setMonth  = (v: string) => { setMonthFilter(v);  setPage(1); };

  /* ── render ────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 rounded-lg bg-white/5 animate-pulse" />
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-20 rounded-xl bg-white/5 animate-pulse" />
          ))}
        </div>
        <div className="h-[300px] rounded-2xl bg-white/5 animate-pulse" />
        <div className="h-[400px] rounded-2xl bg-white/5 animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-4">

      {/* ── Header ───────────────────────────────────────────── */}
      <div>
        <h1 className="text-3xl font-bold text-white">VCP 누적 성과</h1>
        <p className="text-gray-400 text-sm mt-1">Volatility Contraction Pattern · 전략 백테스트 결과</p>
      </div>

      {/* ── Stats cards ──────────────────────────────────────── */}
      {stats ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            {[
              { label: 'Total',       value: String(stats.total),                       color: 'text-white' },
              { label: 'Closed',      value: String(stats.closed),                      color: 'text-white' },
              { label: 'Open',        value: String(stats.open),                        color: 'text-amber-400' },
              {
                label: 'Win Rate',
                value: `${stats.win_rate.toFixed(1)}%`,
                color: stats.win_rate >= 70 ? 'text-green-400' : stats.win_rate >= 50 ? 'text-yellow-400' : 'text-red-400',
              },
              {
                label: 'Avg Return',
                value: `${stats.avg_return >= 0 ? '+' : ''}${stats.avg_return.toFixed(2)}%`,
                color: stats.avg_return >= 0 ? 'text-rose-400' : 'text-blue-400',
              },
              {
                label: 'Total Return',
                value: `${(stats.total_return ?? 0) >= 0 ? '+' : ''}${(stats.total_return ?? 0).toFixed(2)}%`,
                color: (stats.total_return ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400',
              },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-[#1a1f2e] border border-white/10 rounded-xl p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">{label}</p>
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Grade sub-stats */}
          {stats.grade_stats && Object.keys(stats.grade_stats).length > 0 && (
            <div className="flex gap-4 flex-wrap text-xs text-gray-500 px-1">
              {Object.entries(stats.grade_stats).map(([g, gs]) => (
                <span key={g}>
                  <span className={GRADE[g]?.text ?? 'text-gray-400'}>{g}등급</span>
                  {' '}{gs.count}건 · 승률 {gs.win_rate.toFixed(0)}%
                </span>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="rounded-xl bg-[#1a1f2e] border border-white/10 p-6 text-center text-gray-500 text-sm">
          통계 데이터가 없습니다. enrich_vcp.py 실행 후 확인하세요.
        </div>
      )}

      {/* ── Cumulative return chart ───────────────────────────── */}
      <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-4">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">누적 수익률 곡선</p>
        <div className="h-[300px] relative">
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
        {/* Status */}
        <div className="flex rounded-lg overflow-hidden border border-white/10">
          {(['ALL', 'CLOSED', 'OPEN'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setStatus(v)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                statusFilter === v ? 'bg-white/10 text-white' : 'bg-white/5 text-gray-400 hover:text-white'
              }`}
            >
              {v}
            </button>
          ))}
        </div>

        {/* Grade */}
        <select
          value={gradeFilter}
          onChange={(e) => setGrade(e.target.value)}
          className="bg-[#1a1f2e] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-gray-400 focus:outline-none focus:border-white/30"
        >
          <option value="ALL">등급 전체</option>
          {['A', 'B', 'C', 'D'].map((g) => (
            <option key={g} value={g}>등급 {g}</option>
          ))}
        </select>

        {/* Month */}
        <select
          value={monthFilter}
          onChange={(e) => setMonth(e.target.value)}
          className="bg-[#1a1f2e] border border-white/10 rounded-lg px-3 py-1.5 text-xs text-gray-400 focus:outline-none focus:border-white/30"
        >
          <option value="ALL">월 전체</option>
          {months.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>

        <span className="text-xs text-gray-600 ml-auto">
          {filteredSorted.length}건
        </span>
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
                    <SortTh label="종목"   colKey="ticker"      current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="등급"   colKey="grade"       current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="Score"  colKey="score"       current={sortKey} dir={sortDir} onSort={handleSort} />
                    <th className="text-left px-4 py-3 text-[11px] text-gray-500 font-semibold uppercase tracking-wider">진입가</th>
                    <th className="text-left px-4 py-3 text-[11px] text-gray-500 font-semibold uppercase tracking-wider">종료가</th>
                    <SortTh label="수익률" colKey="return_pct"  current={sortKey} dir={sortDir} onSort={handleSort} />
                    <SortTh label="보유일" colKey="hold_days"   current={sortKey} dir={sortDir} onSort={handleSort} />
                    <th className="text-left px-4 py-3 text-[11px] text-gray-500 font-semibold uppercase tracking-wider">상태</th>
                  </tr>
                </thead>
                <tbody>
                  {paged.map((s, i) => {
                    const ticker = getTicker(s);
                    const name   = getName(s);
                    const score  = getScore(s);
                    const gs     = GRADE[s.grade] ?? { text: 'text-gray-400', bg: 'bg-white/5', border: 'border-white/10' };
                    return (
                      <tr key={ticker + s.signal_date + i} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                        <td className="px-4 py-3 text-gray-400 whitespace-nowrap">{s.signal_date}</td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-white">{name}</p>
                          <p className="text-xs text-gray-600">{ticker}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded text-xs font-bold border ${gs.bg} ${gs.text} ${gs.border}`}>
                            {s.grade || '-'}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-semibold text-white">{score}</td>
                        <td className="px-4 py-3 text-gray-300">{s.entry_price?.toLocaleString() ?? '-'}</td>
                        <td className="px-4 py-3 text-gray-300">
                          {s.status === 'CLOSED' ? (s.exit_price?.toLocaleString() ?? '-') : '-'}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`font-semibold ${s.return_pct >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                            {s.return_pct >= 0 ? '+' : ''}{s.return_pct.toFixed(2)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-400">{s.hold_days ?? '-'}일</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium ${s.status === 'CLOSED' ? 'text-emerald-400' : 'text-amber-400 animate-pulse'}`}>
                            {s.status}
                          </span>
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
