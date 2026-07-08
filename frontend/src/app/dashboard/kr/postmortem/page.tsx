'use client';

import { useEffect, useState } from 'react';

/* ── types ───────────────────────────────────────────────────── */

interface StrategyStats {
  total: number;
  evaluated_5d: number;
  evaluated_20d: number;
  win_rate_5d: number;
  win_rate_20d: number;
  avg_return_5d: number;
  avg_return_20d: number;
  recent: RecentSignal[];
}

interface RecentSignal {
  ticker: string;
  name: string;
  signal_date: string;
  score: number;
  return_5d: number | null;
  return_20d: number | null;
}

interface PostmortemData {
  strategies: Record<string, StrategyStats>;
  updated_at: string;
}

/* ── constants ───────────────────────────────────────────────── */

const STRATEGY_META: Record<string, { label: string; icon: string; color: string; textCls: string; bgCls: string }> = {
  vcp:             { label: 'VCP',       icon: 'fa-crosshairs', color: 'blue',    textCls: 'text-blue-400',    bgCls: 'bg-blue-400/10'    },
  closing_bet:     { label: '종가베팅',  icon: 'fa-clock',      color: 'purple',  textCls: 'text-purple-400',  bgCls: 'bg-purple-400/10'  },
  flow_momentum:   { label: '수급모멘텀', icon: 'fa-water',     color: 'cyan',    textCls: 'text-cyan-400',    bgCls: 'bg-cyan-400/10'    },
  narrative:       { label: '테마모멘텀', icon: 'fa-fire',      color: 'orange',  textCls: 'text-orange-400',  bgCls: 'bg-orange-400/10'  },
  sector_rotation: { label: '섹터로테이션', icon: 'fa-sync',    color: 'emerald', textCls: 'text-emerald-400', bgCls: 'bg-emerald-400/10' },
  contrarian:      { label: '역발상',    icon: 'fa-undo',       color: 'rose',    textCls: 'text-rose-400',    bgCls: 'bg-rose-400/10'    },
};

const ORDER = ['vcp', 'closing_bet', 'flow_momentum', 'narrative', 'sector_rotation', 'contrarian'];

/* ── WinRateBar ──────────────────────────────────────────────── */

function WinRateBar({ rate, color }: { rate: number; color: string }) {
  const bg = {
    blue: 'bg-blue-400', purple: 'bg-purple-400', cyan: 'bg-cyan-400',
    orange: 'bg-orange-400', emerald: 'bg-emerald-400', rose: 'bg-rose-400',
  }[color] ?? 'bg-gray-400';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-white/10 rounded-full">
        <div className={`h-full rounded-full ${bg}`} style={{ width: `${Math.min(rate, 100)}%` }} />
      </div>
      <span className={`text-xs font-bold w-10 text-right ${rate >= 55 ? 'text-green-400' : rate >= 45 ? 'text-gray-300' : 'text-red-400'}`}>
        {rate > 0 ? `${rate}%` : '--'}
      </span>
    </div>
  );
}

/* ── ReturnBadge ─────────────────────────────────────────────── */

function ReturnBadge({ v }: { v: number | null }) {
  if (v === null) return <span className="text-gray-600 text-xs">-</span>;
  const pos = v >= 0;
  return (
    <span className={`text-xs font-semibold tabular-nums ${pos ? 'text-green-400' : 'text-red-400'}`}>
      {pos ? '+' : ''}{v.toFixed(1)}%
    </span>
  );
}

/* ── page ────────────────────────────────────────────────────── */

export default function PostmortemPage() {
  const [data,    setData]    = useState<PostmortemData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expand,  setExpand]  = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/kr/postmortem')
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">시그널 사후 분석</h1>
          <p className="text-gray-400 mt-1 text-sm">전략별 5일 / 20일 수익률 추적</p>
        </div>
        {data && <span className="text-xs text-gray-600">업데이트 {data.updated_at}</span>}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20 text-gray-500 gap-2">
          <i className="fa-solid fa-spinner fa-spin" /><span>분석 중...</span>
        </div>
      )}

      {/* 전략 요약 카드 */}
      {data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {ORDER.map(key => {
              const st   = data.strategies[key];
              const meta = STRATEGY_META[key];
              if (!st || !meta) return null;
              const hasData = st.evaluated_5d > 0;
              return (
                <button
                  key={key}
                  onClick={() => setExpand(expand === key ? null : key)}
                  className={`bg-[#1a1f2e] border rounded-xl p-4 text-left transition-all ${
                    expand === key ? `border-${meta.color}-500/40` : 'border-white/10 hover:border-white/20'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <i className={`fa-solid ${meta.icon} ${meta.textCls} text-sm`} />
                    <span className="text-white text-sm font-medium">{meta.label}</span>
                    <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded-full ${meta.bgCls} ${meta.textCls}`}>
                      {st.total}건
                    </span>
                  </div>

                  {!hasData ? (
                    <p className="text-xs text-gray-600">평가 데이터 부족</p>
                  ) : (
                    <div className="space-y-2">
                      <div>
                        <p className="text-[10px] text-gray-600 mb-1">5일 승률</p>
                        <WinRateBar rate={st.win_rate_5d} color={meta.color} />
                      </div>
                      <div>
                        <p className="text-[10px] text-gray-600 mb-1">20일 승률</p>
                        <WinRateBar rate={st.win_rate_20d} color={meta.color} />
                      </div>
                      <div className="flex justify-between text-[11px] pt-1 border-t border-white/5">
                        <span className="text-gray-500">5일 평균</span>
                        <ReturnBadge v={st.avg_return_5d} />
                        <span className="text-gray-500 ml-3">20일 평균</span>
                        <ReturnBadge v={st.avg_return_20d} />
                      </div>
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* 최근 시그널 상세 (확장 시) */}
          {expand && data.strategies[expand] && (
            <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl overflow-hidden">
              <div className="px-5 py-3 border-b border-white/10 flex items-center gap-2">
                <i className={`fa-solid ${STRATEGY_META[expand].icon} ${STRATEGY_META[expand].textCls} text-sm`} />
                <span className="text-white font-medium">{STRATEGY_META[expand].label} — 최근 시그널</span>
              </div>
              <div className="grid grid-cols-[1fr_6rem_3.5rem_3.5rem_3.5rem] gap-3 px-5 py-2.5 text-[10px] text-gray-500 uppercase tracking-wide border-b border-white/5">
                <span>종목</span>
                <span>시그널일</span>
                <span className="text-right">점수</span>
                <span className="text-right">5일</span>
                <span className="text-right">20일</span>
              </div>
              {data.strategies[expand].recent.length === 0 ? (
                <div className="py-10 text-center text-gray-600 text-sm">데이터 없음</div>
              ) : (
                data.strategies[expand].recent.map((sig, i) => (
                  <div key={i}
                    className="grid grid-cols-[1fr_6rem_3.5rem_3.5rem_3.5rem] gap-3 px-5 py-3 border-b border-white/5 last:border-0">
                    <div className="min-w-0">
                      <p className="text-sm text-white font-medium truncate">{sig.name || sig.ticker}</p>
                      <p className="text-[11px] text-gray-600">{sig.ticker}</p>
                    </div>
                    <span className="text-xs text-gray-400 self-center">{sig.signal_date}</span>
                    <span className="text-xs text-gray-300 self-center text-right">{sig.score}</span>
                    <span className="self-center text-right"><ReturnBadge v={sig.return_5d} /></span>
                    <span className="self-center text-right"><ReturnBadge v={sig.return_20d} /></span>
                  </div>
                ))
              )}
            </div>
          )}

          {/* 전략 비교 테이블 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl overflow-hidden">
            <div className="px-5 py-3 border-b border-white/10">
              <span className="text-white font-medium text-sm">전략별 성과 비교</span>
            </div>
            <div className="grid grid-cols-[1fr_4rem_4rem_5rem_5rem_5rem_5rem] gap-2 px-5 py-2.5 text-[10px] text-gray-500 uppercase tracking-wide border-b border-white/5">
              <span>전략</span>
              <span className="text-right">시그널</span>
              <span className="text-right">평가수</span>
              <span className="text-right">5일 승률</span>
              <span className="text-right">20일 승률</span>
              <span className="text-right">5일 평균</span>
              <span className="text-right">20일 평균</span>
            </div>
            {ORDER.map(key => {
              const st   = data.strategies[key];
              const meta = STRATEGY_META[key];
              if (!st || !meta) return null;
              return (
                <div key={key}
                  className="grid grid-cols-[1fr_4rem_4rem_5rem_5rem_5rem_5rem] gap-2 px-5 py-3 border-b border-white/5 last:border-0 hover:bg-white/[0.02]">
                  <div className="flex items-center gap-2">
                    <i className={`fa-solid ${meta.icon} ${meta.textCls} text-xs`} />
                    <span className="text-sm text-white">{meta.label}</span>
                  </div>
                  <span className="text-sm text-gray-400 text-right self-center">{st.total}</span>
                  <span className="text-sm text-gray-400 text-right self-center">{st.evaluated_5d}</span>
                  <span className={`text-sm font-semibold text-right self-center ${
                    st.win_rate_5d >= 55 ? 'text-green-400' : st.win_rate_5d >= 45 ? 'text-gray-300' : 'text-red-400'
                  }`}>{st.evaluated_5d > 0 ? `${st.win_rate_5d}%` : '--'}</span>
                  <span className={`text-sm font-semibold text-right self-center ${
                    st.win_rate_20d >= 55 ? 'text-green-400' : st.win_rate_20d >= 45 ? 'text-gray-300' : 'text-red-400'
                  }`}>{st.evaluated_20d > 0 ? `${st.win_rate_20d}%` : '--'}</span>
                  <span className="text-right self-center"><ReturnBadge v={st.evaluated_5d > 0 ? st.avg_return_5d : null} /></span>
                  <span className="text-right self-center"><ReturnBadge v={st.evaluated_20d > 0 ? st.avg_return_20d : null} /></span>
                </div>
              );
            })}
          </div>

          <div className="bg-white/3 border border-white/5 rounded-xl p-4">
            <p className="text-xs text-gray-600 leading-relaxed">
              <i className="fa-solid fa-circle-info text-gray-700 mr-1.5" />
              수익률은 시그널 발생일 다음 거래일 종가 기준으로 계산됩니다. 통계적 유의성은 20건 이상 축적 후 판단하세요.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
