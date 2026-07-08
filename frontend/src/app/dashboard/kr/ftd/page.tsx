'use client';

import { useEffect, useState } from 'react';

/* ── types ───────────────────────────────────────────────────── */

interface FtdSignal {
  date: string;
  change: number;
  close: number;
  volume_ratio: number;
  day_count: number;
}

interface RallyAttempt {
  date: string;
  change: number;
  close: number;
  days_ago: number;
}

interface HistoryRow {
  date: string;
  close: number;
  change: number;
  is_rally: boolean;
  is_ftd: boolean;
}

interface FtdData {
  market_state: 'UPTREND' | 'CORRECTION' | 'NEUTRAL';
  ftd_status: 'CONFIRMED' | 'FAILED' | 'WATCHING' | 'NO_SIGNAL';
  current_close: number;
  decline_from_peak: number;
  high_60d: number;
  low_20d: number;
  ma20: number | null;
  ma50: number | null;
  rally_attempt: RallyAttempt | null;
  ftd_signals: FtdSignal[];
  ftd_failed: boolean;
  history: HistoryRow[];
  updated_at: string;
}

/* ── constants ───────────────────────────────────────────────── */

const MARKET_META = {
  UPTREND:    { label: '상승 추세',    color: 'text-green-400',  bg: 'bg-green-400/10',  border: 'border-green-500/30'  },
  CORRECTION: { label: '조정 구간',   color: 'text-red-400',    bg: 'bg-red-400/10',    border: 'border-red-500/30'    },
  NEUTRAL:    { label: '중립',         color: 'text-yellow-400', bg: 'bg-yellow-400/10', border: 'border-yellow-500/30' },
};

const FTD_META = {
  CONFIRMED: { label: 'FTD 확인',     color: 'text-green-400',  bg: 'bg-green-400/15',  icon: 'fa-check-circle'         },
  WATCHING:  { label: '관찰 중',      color: 'text-yellow-400', bg: 'bg-yellow-400/15', icon: 'fa-eye'                  },
  FAILED:    { label: 'FTD 무효',     color: 'text-red-400',    bg: 'bg-red-400/15',    icon: 'fa-circle-xmark'         },
  NO_SIGNAL: { label: '신호 없음',    color: 'text-gray-400',   bg: 'bg-white/5',        icon: 'fa-minus-circle'         },
};

/* ── MiniChart ───────────────────────────────────────────────── */

function MiniChart({ history, rallyDate, ftdDates }: {
  history: HistoryRow[];
  rallyDate: string | null;
  ftdDates: string[];
}) {
  if (!history.length) return null;
  const closes = history.map(r => r.close);
  const min    = Math.min(...closes);
  const max    = Math.max(...closes);
  const range  = max - min || 1;
  const W = 640, H = 120;
  const xStep = W / (history.length - 1 || 1);

  const toX = (i: number)   => i * xStep;
  const toY = (v: number)   => H - ((v - min) / range) * H;

  const pathD = history
    .map((r, i) => `${i === 0 ? 'M' : 'L'} ${toX(i).toFixed(1)} ${toY(r.close).toFixed(1)}`)
    .join(' ');

  return (
    <div className="w-full overflow-hidden">
      <svg viewBox={`0 0 ${W} ${H + 20}`} className="w-full h-28">
        {/* 가격선 */}
        <path d={pathD} fill="none" stroke="#4b5563" strokeWidth="1.5" />
        {/* MA20 참고선 */}
        {/* 마커 */}
        {history.map((r, i) => {
          if (r.is_rally) return (
            <g key={`r${i}`}>
              <circle cx={toX(i)} cy={toY(r.close)} r="5" fill="#fbbf24" />
              <text x={toX(i)} y={toY(r.close) - 10} textAnchor="middle" fontSize="8" fill="#fbbf24">R</text>
            </g>
          );
          if (r.is_ftd) return (
            <g key={`f${i}`}>
              <circle cx={toX(i)} cy={toY(r.close)} r="6" fill="#22c55e" />
              <text x={toX(i)} y={toY(r.close) - 10} textAnchor="middle" fontSize="8" fill="#22c55e">FTD</text>
            </g>
          );
          return null;
        })}
        {/* x축 날짜 레이블 (첫/중간/마지막) */}
        {[0, Math.floor(history.length / 2), history.length - 1].map(i => (
          <text key={i} x={toX(i)} y={H + 14} textAnchor="middle" fontSize="8" fill="#4b5563">
            {history[i]?.date.slice(5)}
          </text>
        ))}
      </svg>
    </div>
  );
}

/* ── page ────────────────────────────────────────────────────── */

export default function FtdPage() {
  const [data,    setData]    = useState<FtdData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  useEffect(() => {
    fetch('/api/kr/ftd')
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const mm  = data ? MARKET_META[data.market_state] : null;
  const fm  = data ? FTD_META[data.ftd_status] : null;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white">FTD 탐지</h1>
        <p className="text-gray-400 text-sm mt-1">Follow-Through Day — O'Neil 시장 저점 확인 신호</p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20 text-gray-500 gap-2">
          <i className="fa-solid fa-spinner fa-spin" /><span>KOSPI 분석 중...</span>
        </div>
      )}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">
          <i className="fa-solid fa-triangle-exclamation mr-2" />{error}
        </div>
      )}

      {data && mm && fm && (
        <>
          {/* 상태 배너 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 시장 상태 */}
            <div className={`border ${mm.border} ${mm.bg} rounded-2xl p-5`}>
              <p className="text-xs text-gray-500 mb-2">시장 상태 (KOSPI)</p>
              <p className={`text-2xl font-bold ${mm.color}`}>{mm.label}</p>
              <div className="mt-3 space-y-1.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">현재</span>
                  <span className="text-white font-semibold">{data.current_close.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">60일 고점 대비</span>
                  <span className={data.decline_from_peak < -5 ? 'text-red-400 font-semibold' : 'text-gray-300'}>
                    {data.decline_from_peak > 0 ? '+' : ''}{data.decline_from_peak}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">MA20</span>
                  <span className={data.ma20 && data.current_close > data.ma20 ? 'text-green-400' : 'text-red-400'}>
                    {data.ma20?.toLocaleString() ?? '--'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">MA50</span>
                  <span className={data.ma50 && data.current_close > data.ma50 ? 'text-green-400' : 'text-red-400'}>
                    {data.ma50?.toLocaleString() ?? '--'}
                  </span>
                </div>
              </div>
            </div>

            {/* FTD 상태 */}
            <div className={`border border-white/10 ${fm.bg} rounded-2xl p-5`}>
              <p className="text-xs text-gray-500 mb-2">FTD 상태</p>
              <div className="flex items-center gap-3">
                <i className={`fa-solid ${fm.icon} ${fm.color} text-3xl`} />
                <p className={`text-2xl font-bold ${fm.color}`}>{fm.label}</p>
              </div>

              {data.rally_attempt && (
                <div className="mt-3 p-3 bg-amber-400/10 border border-amber-500/20 rounded-lg">
                  <p className="text-[10px] text-amber-500 mb-1.5">Rally Attempt</p>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">날짜</span>
                    <span className="text-amber-400 font-medium">
                      {data.rally_attempt.date} ({data.rally_attempt.days_ago}일 전)
                    </span>
                  </div>
                  <div className="flex justify-between text-sm mt-1">
                    <span className="text-gray-400">상승률</span>
                    <span className="text-amber-400">+{data.rally_attempt.change}%</span>
                  </div>
                </div>
              )}

              {!data.rally_attempt && (
                <p className="text-sm text-gray-500 mt-3">Rally Attempt 없음 — 조정 대기 중</p>
              )}
            </div>
          </div>

          {/* FTD 시그널 상세 */}
          {data.ftd_signals.length > 0 && (
            <div className="bg-[#1a1f2e] border border-green-500/20 rounded-2xl overflow-hidden">
              <div className="px-5 py-3 border-b border-white/10 flex items-center gap-2">
                <i className="fa-solid fa-check-circle text-green-400" />
                <span className="text-white font-medium">Follow-Through Day 확인</span>
              </div>
              <div className="grid grid-cols-[1fr_4rem_4rem_5rem_4rem] gap-3 px-5 py-2.5 text-[10px] text-gray-500 uppercase tracking-wide border-b border-white/5">
                <span>날짜</span>
                <span className="text-right">상승률</span>
                <span className="text-right">거래량 배수</span>
                <span className="text-right">지수</span>
                <span className="text-right">Rally 후 일수</span>
              </div>
              {data.ftd_signals.map((f, i) => (
                <div key={i} className="grid grid-cols-[1fr_4rem_4rem_5rem_4rem] gap-3 px-5 py-3 border-b border-white/5 last:border-0">
                  <span className="text-sm text-green-400 font-medium">{f.date}</span>
                  <span className="text-sm text-green-400 font-bold text-right">+{f.change}%</span>
                  <span className="text-sm text-gray-300 text-right">×{f.volume_ratio}</span>
                  <span className="text-sm text-white text-right">{f.close.toLocaleString()}</span>
                  <span className="text-sm text-gray-400 text-right">+{f.day_count}일</span>
                </div>
              ))}
            </div>
          )}

          {/* KOSPI 미니 차트 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm text-white font-medium">KOSPI 최근 40일</p>
              <div className="flex items-center gap-4 text-[11px]">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />Rally Attempt</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-green-400 inline-block" />FTD</span>
              </div>
            </div>
            <MiniChart
              history={data.history}
              rallyDate={data.rally_attempt?.date ?? null}
              ftdDates={data.ftd_signals.map(f => f.date)}
            />
          </div>

          {/* FTD 개요 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">FTD 해석 가이드</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-gray-400">
              <div className="space-y-1.5">
                <p><span className="text-amber-400 font-medium">Rally Attempt</span> — 조정 저점 이후 최초 상승일</p>
                <p><span className="text-green-400 font-medium">FTD 조건</span> — Rally 4일 후 이상, +1.5%↑, 거래량 증가</p>
                <p><span className="text-red-400 font-medium">FTD 무효</span> — Rally 후 기존 저점 하향 돌파</p>
              </div>
              <div className="space-y-1.5">
                <p>FTD 확인 시: 역발상 시그널 + 수급 모멘텀 전략 적극 활용</p>
                <p>CONFIRMED 상태에서 모든 전략 진입 비중 상향 권장</p>
                <p className="text-gray-600">KOSPI (^KS11) 기준, 업데이트 {data.updated_at}</p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
