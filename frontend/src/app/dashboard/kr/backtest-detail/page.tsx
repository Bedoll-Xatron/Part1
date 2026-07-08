'use client';

import { useEffect, useState } from 'react';

/* ── types ───────────────────────────────────────────────────── */

interface Stats {
  count: number;
  win_rate: number;
  avg: number;
  pf: number | null;
  max_cons_loss: number;
}

interface MonthlyEntry {
  avg: number;
  count: number;
  win_rate: number;
}

interface StrategyResult {
  total: number;
  stats_5d: Stats;
  stats_20d: Stats;
  max_drawdown: number;
  rolling_wr_30: number | null;
  equity_curve: number[];
  monthly: Record<string, MonthlyEntry>;
  recent: any[];
}

interface BtData {
  strategies: Record<string, StrategyResult>;
  updated_at: string;
}

/* ── constants ───────────────────────────────────────────────── */

const STRAT_META: Record<string, { label: string; icon: string; color: string; textCls: string }> = {
  vcp: { label: 'VCP', icon: 'fa-crosshairs', color: 'blue', textCls: 'text-blue-400' },
  closing_bet: { label: '종가베팅', icon: 'fa-clock', color: 'purple', textCls: 'text-purple-400' },
  flow_momentum: { label: '수급모멘텀', icon: 'fa-water', color: 'cyan', textCls: 'text-cyan-400' },
  narrative: { label: '테마모멘텀', icon: 'fa-fire', color: 'orange', textCls: 'text-orange-400' },
  sector_rotation: { label: '섹터로테이션', icon: 'fa-sync', color: 'emerald', textCls: 'text-emerald-400' },
  contrarian: { label: '역발상', icon: 'fa-undo', color: 'rose', textCls: 'text-rose-400' },
  held_positions: { label: '보유종목추적', icon: 'fa-briefcase', color: 'yellow', textCls: 'text-yellow-400' },
};

const ORDER = ['vcp', 'closing_bet', 'flow_momentum', 'narrative', 'sector_rotation', 'contrarian', 'held_positions'];

/* ── helpers ─────────────────────────────────────────────────── */

function pct(v: number | null | undefined, suffix = '%') {
  if (v == null) return '--';
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}${suffix}`;
}

function wr(v: number, count: number) {
  if (count === 0) return <span className="text-gray-600">--</span>;
  const c = v >= 55 ? 'text-green-400' : v >= 45 ? 'text-gray-300' : 'text-red-400';
  return <span className={`font-bold ${c}`}>{v}%</span>;
}

/* ── EquitySparkline ─────────────────────────────────────────── */

function EquitySparkline({ data, color }: { data: number[]; color: string }) {
  const safeData = data || [];
  const plotData = safeData.length === 1 ? [safeData[0], safeData[0]] : safeData;
  if (!plotData || plotData.length < 2) return <div className="h-10 bg-white/5 rounded flex justify-center items-center text-xs text-gray-500">대기 중</div>;
  const min = Math.min(...plotData);
  const max = Math.max(...plotData);
  const range = max - min || 0.001;
  const W = 200, H = 40;
  const pts = plotData.map((v, i) => {
    const x = (i / (plotData.length - 1)) * W;
    const y = H - ((v - min) / range) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const colorMap: Record<string, string> = {
    blue: '#60a5fa', purple: '#c084fc', cyan: '#22d3ee',
    orange: '#fb923c', emerald: '#34d399', rose: '#fb7185',
    yellow: '#facc15',
  };
  const stroke = colorMap[color] ?? '#9ca3af';
  const last = plotData[plotData.length - 1];
  const isUp = last >= plotData[0];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-10">
      <polyline points={pts} fill="none" stroke={isUp ? stroke : '#f87171'} strokeWidth="1.5" />
    </svg>
  );
}

/* ── MonthlyHeatmap ──────────────────────────────────────────── */

function MonthlyHeatmap({ monthly }: { monthly: Record<string, MonthlyEntry> }) {
  const entries = Object.entries(monthly).slice(-12);
  if (!entries.length) return <p className="text-xs text-gray-600">데이터 없음</p>;
  return (
    <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
      {entries.map(([month, d]) => {
        const bg = d.avg >= 5 ? 'bg-green-400/30' : d.avg >= 0 ? 'bg-green-400/10'
          : d.avg >= -5 ? 'bg-red-400/10' : 'bg-red-400/30';
        const tc = d.avg >= 0 ? 'text-green-400' : 'text-red-400';
        return (
          <div key={month} className={`${bg} rounded p-2 text-center`}>
            <p className="text-[10px] text-gray-500">{month.slice(5)}</p>
            <p className={`text-sm font-bold ${tc}`}>{d.avg > 0 ? '+' : ''}{d.avg.toFixed(1)}%</p>
            <p className="text-[10px] text-gray-600">{d.count}건</p>
          </div>
        );
      })}
    </div>
  );
}

/* ── page ────────────────────────────────────────────────────── */

export default function BacktestDetailPage() {
  const [data, setData] = useState<BtData | null>(null);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState('vcp');

  useEffect(() => {
    fetch('/api/kr/backtest/detail')
      .then(r => r.json()).then(setData).catch(() => { }).finally(() => setLoading(false));
  }, []);

  const st = data?.strategies[active];
  const meta = STRAT_META[active];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Backtest Expert</h1>
          <p className="text-gray-400 text-sm mt-1">전략별 상세 백테스트 — 수익곡선 · MDD · Profit Factor · 월별</p>
        </div>
        {data && <span className="text-xs text-gray-600">업데이트 {data.updated_at}</span>}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20 text-gray-500 gap-2">
          <i className="fa-solid fa-spinner fa-spin" /><span>분석 중...</span>
        </div>
      )}

      {data && (
        <>
          {/* 전략 탭 */}
          <div className="flex flex-wrap gap-2">
            {ORDER.map(key => {
              const m = STRAT_META[key];
              const st = data.strategies[key];
              if (!st && key !== active) return null; // 데이터 없으면 탭 숨김 (단, 현재 선택된 탭은 예외)
              const isActive = active === key;
              return (
                <button key={key} onClick={() => setActive(key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm transition-all ${isActive ? `border-${m.color}-500/50 bg-${m.color}-400/10 ${m.textCls}` : 'border-white/10 text-gray-400 hover:border-white/20'
                    }`}>
                  <i className={`fa-solid ${m.icon} text-xs`} />
                  {m.label}
                  {st && <span className="text-[10px] text-gray-600 ml-1">{st.total}건</span>}
                </button>
              );
            })}
          </div>

          {st && meta && (
            <>
              {/* 핵심 지표 */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: '5일 승률', value: wr(st.stats_5d.win_rate, st.stats_5d.count), sub: `${st.stats_5d.count}건 평가` },
                  { label: '20일 승률', value: wr(st.stats_20d.win_rate, st.stats_20d.count), sub: `${st.stats_20d.count}건 평가` },
                  { label: '20일 평균수익', value: <span className={st.stats_20d.avg >= 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>{pct(st.stats_20d.avg)}</span>, sub: 'per trade' },
                  { label: 'Profit Factor', value: <span className={!st.stats_20d.pf ? 'text-gray-600' : st.stats_20d.pf >= 1.5 ? 'text-green-400 font-bold' : 'text-yellow-400 font-bold'}>{st.stats_20d.pf?.toFixed(2) ?? '--'}</span>, sub: '≥1.5 양호' },
                ].map(({ label, value, sub }) => (
                  <div key={label} className="bg-[#1a1f2e] border border-white/10 rounded-xl p-4">
                    <p className="text-xs text-gray-500 mb-1">{label}</p>
                    <p className="text-xl">{value}</p>
                    <p className="text-[11px] text-gray-600 mt-0.5">{sub}</p>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* MDD */}
                <div className="bg-[#1a1f2e] border border-white/10 rounded-xl p-4">
                  <p className="text-xs text-gray-500 mb-1">최대 낙폭 (MDD)</p>
                  <p className={`text-2xl font-bold ${st.max_drawdown > 20 ? 'text-red-400' : st.max_drawdown > 10 ? 'text-yellow-400' : 'text-green-400'}`}>
                    -{st.max_drawdown}%
                  </p>
                  <p className="text-[11px] text-gray-600 mt-0.5">1% 리스크 기준 복리 곡선</p>
                </div>
                {/* 최대 연속 손실 */}
                <div className="bg-[#1a1f2e] border border-white/10 rounded-xl p-4">
                  <p className="text-xs text-gray-500 mb-1">최대 연속 손실</p>
                  <p className={`text-2xl font-bold ${st.stats_20d.max_cons_loss >= 5 ? 'text-red-400' : st.stats_20d.max_cons_loss >= 3 ? 'text-yellow-400' : 'text-green-400'}`}>
                    {st.stats_20d.max_cons_loss > 0 ? `${st.stats_20d.max_cons_loss}연속` : '--'}
                  </p>
                  <p className="text-[11px] text-gray-600 mt-0.5">20일 수익률 기준</p>
                </div>
                {/* 롤링 승률 */}
                <div className="bg-[#1a1f2e] border border-white/10 rounded-xl p-4">
                  <p className="text-xs text-gray-500 mb-1">최근 30건 승률</p>
                  <p className={`text-2xl font-bold ${!st.rolling_wr_30 ? 'text-gray-600' :
                    st.rolling_wr_30 >= 55 ? 'text-green-400' : st.rolling_wr_30 >= 45 ? 'text-yellow-400' : 'text-red-400'
                    }`}>{st.rolling_wr_30 != null ? `${st.rolling_wr_30}%` : '--'}</p>
                  <p className="text-[11px] text-gray-600 mt-0.5">누적 대비 최근 성과</p>
                </div>
              </div>

              {/* 수익 곡선 */}
              <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm text-white font-medium">누적 수익 곡선 (최근 60거래)</p>
                  <span className={`text-sm font-bold ${st.equity_curve.length > 1 && st.equity_curve[st.equity_curve.length - 1] >= st.equity_curve[0]
                    ? 'text-green-400' : 'text-red-400'
                    }`}>
                    {st.equity_curve.length > 1
                      ? `${((st.equity_curve[st.equity_curve.length - 1] / st.equity_curve[0] - 1) * 100).toFixed(1)}%`
                      : '--'}
                  </span>
                </div>
                {st.equity_curve.length > 1
                  ? <EquitySparkline data={st.equity_curve} color={meta.color} />
                  : <p className="text-xs text-gray-600 py-4 text-center">데이터 누적 중...</p>
                }
              </div>

              {/* 월별 성과 */}
              <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
                <p className="text-sm text-white font-medium mb-3">월별 평균 20일 수익률</p>
                <MonthlyHeatmap monthly={st.monthly} />
              </div>

              {/* 전략 비교 요약 테이블 */}
              <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl overflow-hidden">
                <div className="px-5 py-3 border-b border-white/10">
                  <p className="text-sm font-medium text-white">전략 비교 (20일 기준)</p>
                </div>
                <div className="grid grid-cols-[1fr_4rem_5rem_5rem_5rem_4rem] gap-2 px-5 py-2.5 text-[10px] text-gray-500 uppercase tracking-wide border-b border-white/5">
                  <span>전략</span>
                  <span className="text-right">건수</span>
                  <span className="text-right">승률</span>
                  <span className="text-right">평균수익</span>
                  <span className="text-right">PF</span>
                  <span className="text-right">MDD</span>
                </div>
                {ORDER.map(key => {
                  const s = data.strategies[key];
                  const m = STRAT_META[key];
                  if (!s) return null;
                  const isActive = key === active;
                  return (
                    <div key={key} onClick={() => setActive(key)}
                      className={`grid grid-cols-[1fr_4rem_5rem_5rem_5rem_4rem] gap-2 px-5 py-3 border-b border-white/5 last:border-0 cursor-pointer transition-colors ${isActive ? 'bg-white/[0.04]' : 'hover:bg-white/[0.02]'}`}>
                      <div className="flex items-center gap-2">
                        <i className={`fa-solid ${m.icon} ${m.textCls} text-xs`} />
                        <span className="text-sm text-white">{m.label}</span>
                      </div>
                      <span className="text-sm text-gray-400 text-right self-center">{s.stats_20d.count}</span>
                      <span className="text-right self-center">
                        {s.stats_20d.count > 0
                          ? <span className={s.stats_20d.win_rate >= 55 ? 'text-green-400 font-semibold text-sm' : s.stats_20d.win_rate >= 45 ? 'text-gray-300 text-sm' : 'text-red-400 font-semibold text-sm'}>
                            {s.stats_20d.win_rate}%
                          </span>
                          : <span className="text-gray-600 text-sm">--</span>}
                      </span>
                      <span className={`text-sm font-semibold text-right self-center tabular-nums ${s.stats_20d.avg >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {s.stats_20d.count > 0 ? pct(s.stats_20d.avg) : '--'}
                      </span>
                      <span className={`text-sm text-right self-center ${!s.stats_20d.pf ? 'text-gray-600' : s.stats_20d.pf >= 1.5 ? 'text-green-400' : 'text-yellow-400'}`}>
                        {s.stats_20d.pf?.toFixed(1) ?? '--'}
                      </span>
                      <span className={`text-sm text-right self-center ${s.max_drawdown > 20 ? 'text-red-400' : s.max_drawdown > 10 ? 'text-yellow-400' : 'text-green-400'}`}>
                        -{s.max_drawdown}%
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className="bg-white/3 border border-white/5 rounded-xl p-4">
                <p className="text-xs text-gray-600 leading-relaxed">
                  <i className="fa-solid fa-circle-info text-gray-700 mr-1.5" />
                  수익 곡선은 거래당 1% 리스크 가정 복리 계산 기준입니다.
                  Profit Factor ≥ 1.5 양호, ≥ 2.0 우수. 통계적 유의성은 20건 이상부터 적용하세요.
                </p>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
