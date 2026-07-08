'use client';

import { useEffect, useRef, useState } from 'react';
import StockChart from '@/components/ui/StockChart';

/* ── types ───────────────────────────────────────────────────── */

interface PeadSignal {
  ticker: string;
  name: string;
  market: string;
  gap_date: string;
  gap_pct: number;
  vol_ratio: number;
  post_drift: number | null;
  score: number;
  factors: { gap: number; volume: number; ma: number; trend: number; drift: number };
}

interface PeadData {
  signals: PeadSignal[];
  total: number;
  universe_size: number;
  params: { min_gap_pct: number; min_vol_ratio: number; lookback_days: number };
}

function SignalMeta({ label, value, className = '' }: { label: string; value: string | number; className?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</span>
      <span className={`text-sm font-semibold ${className || 'text-gray-200'}`}>{value}</span>
    </div>
  );
}

function ChartModal({ ticker, name, signal, onClose }: { ticker: string; name: string; signal: PeadSignal; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="p-5 border-b border-white/5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-2xl flex items-center justify-center text-xs font-bold text-white shadow-lg ${!(signal.market?.toUpperCase().includes('KOSDAQ'))
                ? 'bg-gradient-to-br from-rose-500 to-orange-500 shadow-rose-500/20'
                : 'bg-gradient-to-br from-blue-500 to-cyan-500 shadow-blue-500/20'
                }`}>
                {!(signal.market?.toUpperCase().includes('KOSDAQ')) ? 'KOSPI' : 'KOSDAQ'}
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

          <div className="flex items-center gap-8 py-3 px-4 bg-white/[0.02] rounded-xl border border-white/5">
            <SignalMeta label="Score" value={`${signal.score}/10`} className="text-amber-400" />
            <div className="w-px h-8 bg-white/10" />
            <SignalMeta label="Gap %" value={`+${signal.gap_pct}%`} className="text-white" />
            <div className="w-px h-8 bg-white/10" />
            <SignalMeta label="Vol Ratio" value={`×${signal.vol_ratio}`} className="text-white" />
            <div className="w-px h-8 bg-white/10" />
            <SignalMeta label="Drift" value={signal.post_drift === null ? '당일' : `${signal.post_drift >= 0 ? '+' : ''}${signal.post_drift}%`} className={signal.post_drift === null ? 'text-gray-500' : signal.post_drift >= 0 ? 'text-green-400' : 'text-red-400'} />
            <div className="w-px h-8 bg-white/10" />
            <SignalMeta label="Gap Date" value={signal.gap_date} />
          </div>
        </div>

        {/* Chart View */}
        <div className="p-5 h-[400px]">
          <StockChart ticker={ticker} marketType="KR" />
        </div>
      </div>
    </div>
  );
}

/* ── FactorBar ───────────────────────────────────────────────── */

function FactorBar({ label, value, max = 2 }: { label: string; value: number; max?: number }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-gray-500 w-10 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1 bg-white/10 rounded-full">
        <div className="h-full rounded-full bg-amber-400" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-amber-400 w-5 text-right">{value}</span>
    </div>
  );
}

/* ── page ────────────────────────────────────────────────────── */

export default function PeadPage() {
  const [data, setData] = useState<PeadData | null>(null);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<{ ticker: string; name: string; signal: PeadSignal } | null>(null);
  const [minGap, setMinGap] = useState('3');
  const [minVol, setMinVol] = useState('1.5');
  const [lookback, setLookback] = useState('60');

  const load = (gap = minGap, vol = minVol, lb = lookback) => {
    setLoading(true);
    fetch(`/api/kr/pead?min_gap=${gap}&min_vol=${vol}&lookback=${lb}`)
      .then(r => r.json()).then(setData).catch(() => { }).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <>
      {modal && <ChartModal ticker={modal.ticker} name={modal.name} signal={modal.signal} onClose={() => setModal(null)} />}

      <div className="space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">갭 상승 드리프트</h1>
            <p className="text-gray-400 text-sm mt-1">PEAD Proxy — 갭 상승 후 추세 지속 종목 스크리닝</p>
          </div>
          {data && (
            <span className="text-xs text-gray-600 mt-2">
              유니버스 {data.universe_size}종목 · {data.total}개 이벤트
            </span>
          )}
        </div>

        {/* 필터 */}
        <div className="bg-[#1a1f2e] border border-white/10 rounded-xl p-4 flex flex-wrap gap-4 items-end">
          {[
            { label: '최소 갭 (%)', val: minGap, set: setMinGap },
            { label: '최소 거래량 배수', val: minVol, set: setMinVol },
            { label: '탐색 기간 (일)', val: lookback, set: setLookback },
          ].map(({ label, val, set }) => (
            <label key={label} className="flex flex-col gap-1">
              <span className="text-[10px] text-gray-500">{label}</span>
              <input type="number" value={val} onChange={e => set(e.target.value)} step="0.5"
                className="w-28 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-white/30" />
            </label>
          ))}
          <button onClick={() => load(minGap, minVol, lookback)}
            className="px-4 py-1.5 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-lg text-sm hover:bg-amber-500/30 transition-colors">
            <i className="fa-solid fa-magnifying-glass mr-1.5" />스캔
          </button>
        </div>

        {/* 설명 */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: 'fa-bolt-lightning', label: '갭 상승', desc: '전일 종가 대비 갭 크기 + 거래량 배수', color: 'text-amber-400' },
            { icon: 'fa-chart-line', label: '추세 지속', desc: '갭 이후 가격 드리프트 방향', color: 'text-green-400' },
            { icon: 'fa-layer-group', label: '5요소 점수', desc: '갭/거래량/MA/추세/드리프트 종합 0~10', color: 'text-blue-400' },
          ].map(({ icon, label, desc, color }) => (
            <div key={label} className="bg-[#1a1f2e] border border-white/10 rounded-xl p-3">
              <i className={`fa-solid ${icon} ${color} mb-2 block`} />
              <p className="text-sm font-medium text-white">{label}</p>
              <p className="text-[11px] text-gray-500 mt-0.5">{desc}</p>
            </div>
          ))}
        </div>

        {/* 테이블 */}
        <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl overflow-hidden">
          <div className="grid grid-cols-[2rem_2.5rem_1fr_4rem_4.5rem_4.5rem_6rem_4rem] gap-2 px-5 py-2.5 border-b border-white/10 text-[10px] text-gray-500 uppercase tracking-wide">
            <span>#</span><span></span><span>종목</span>
            <span className="text-center">Score</span>
            <span className="text-right">갭 %</span>
            <span className="text-right">거래량 배수</span>
            <span className="text-right">드리프트</span>
            <span className="text-center">갭 날짜</span>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-16 gap-2 text-gray-500">
              <i className="fa-solid fa-spinner fa-spin" /><span>스캔 중...</span>
            </div>
          )}

          {!loading && (!data || data.signals.length === 0) && (
            <div className="flex flex-col items-center py-16 text-gray-600 gap-3">
              <i className="fa-solid fa-bolt-lightning text-4xl" />
              <p className="text-sm">갭 이벤트 없음 — 필터 조건을 낮춰보세요</p>
            </div>
          )}

          {!loading && data?.signals.map((sig, idx) => {
            const isKospi = !(sig.market?.toUpperCase().includes('KOSDAQ'));
            const driftPos = sig.post_drift !== null && sig.post_drift >= 0;
            return (
              <div key={sig.ticker}
                className="grid grid-cols-[2rem_2.5rem_1fr_4rem_4.5rem_4.5rem_6rem_4rem] gap-2 px-5 py-3.5 border-b border-white/5 last:border-0 cursor-pointer hover:bg-white/[0.03] transition-colors"
                onClick={() => setModal({ ticker: sig.ticker, name: sig.name, signal: sig })}>
                <span className="text-sm text-gray-600 self-center">{idx + 1}</span>
                <div className={`w-8 h-8 rounded-full self-center flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0 ${isKospi ? 'bg-gradient-to-br from-rose-500 to-orange-500' : 'bg-gradient-to-br from-blue-500 to-cyan-500'
                  }`}>{isKospi ? 'KP' : 'KQ'}</div>

                <div className="self-center min-w-0">
                  <p className="text-sm font-medium text-white truncate">{sig.name}</p>
                  <p className="text-[11px] text-gray-600">{sig.ticker}</p>
                  {/* 5요소 미니바 */}
                  <div className="mt-1.5 space-y-0.5 hidden sm:block">
                    {Object.entries(sig.factors).map(([k, v]) => (
                      <FactorBar key={k} label={k} value={v} />
                    ))}
                  </div>
                </div>

                <div className="self-center text-center">
                  <span className={`text-lg font-bold ${sig.score >= 7 ? 'text-amber-400' : sig.score >= 5 ? 'text-white' : 'text-gray-400'}`}>
                    {sig.score}
                  </span>
                  <span className="text-gray-600 text-xs">/10</span>
                </div>

                <span className={`text-sm font-semibold text-right self-center tabular-nums ${sig.gap_pct >= 8 ? 'text-amber-400' : 'text-white'}`}>
                  +{sig.gap_pct}%
                </span>
                <span className="text-sm text-right self-center text-gray-300 tabular-nums">
                  ×{sig.vol_ratio}
                </span>
                <span className={`text-sm font-semibold text-right self-center tabular-nums ${sig.post_drift === null ? 'text-gray-600' : driftPos ? 'text-green-400' : 'text-red-400'
                  }`}>
                  {sig.post_drift === null ? '당일' : `${sig.post_drift >= 0 ? '+' : ''}${sig.post_drift}%`}
                </span>
                <span className="text-[11px] text-gray-500 text-center self-center">{sig.gap_date}</span>
              </div>
            );
          })}
        </div>

        <div className="bg-white/3 border border-white/5 rounded-xl p-4">
          <p className="text-xs text-gray-600 leading-relaxed">
            <i className="fa-solid fa-circle-info text-gray-700 mr-1.5" />
            PEAD(Post-Earnings Announcement Drift) Proxy: 실적 발표일 데이터 없이 대형 갭 상승 이벤트를 대리 지표로 사용합니다.
            일별 가격 데이터에 등록된 추적 유니버스 기준이며, 갭 후 드리프트 방향이 핵심 지표입니다.
          </p>
        </div>
      </div>
    </>
  );
}
