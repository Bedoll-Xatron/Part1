'use client';

import { useEffect, useState } from 'react';

/* ── types ───────────────────────────────────────────────────── */

interface MaBreadth {
  count: number;
  pct: number;
  below: number;
}

interface AdData {
  advances: number;
  declines: number;
  unchanged?: number;
  ratio: number | null;
  upper_limit?: number;
  lower_limit?: number;
}

interface BreadthData {
  universe: { total: number; source: string };
  ma_breadth: Record<string, MaBreadth>;
  advance_decline: {
    tracked: AdData & { unchanged: number };
    naver:   Record<string, AdData>;
  };
  new_highs_lows: { new_high_52w: number; new_low_52w: number; ratio: number | null };
  updated_at: string;
}

/* ── GaugeBar ────────────────────────────────────────────────── */

function GaugeBar({ pct, label, sublabel }: { pct: number; label: string; sublabel: string }) {
  const color = pct >= 70 ? 'bg-green-400' : pct >= 50 ? 'bg-yellow-400' : pct >= 30 ? 'bg-orange-400' : 'bg-red-400';
  const text  = pct >= 70 ? 'text-green-400' : pct >= 50 ? 'text-yellow-400' : pct >= 30 ? 'text-orange-400' : 'text-red-400';
  return (
    <div className="bg-[#1a1f2e] border border-white/10 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-white font-medium">{label}</span>
        <span className={`text-xl font-bold tabular-nums ${text}`}>{pct}%</span>
      </div>
      <div className="h-2 bg-white/10 rounded-full mb-2">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-[11px] text-gray-500">{sublabel}</p>
    </div>
  );
}

/* ── AdBar ───────────────────────────────────────────────────── */

function AdBar({ advances, declines, unchanged = 0, label }: { advances: number; declines: number; unchanged?: number; label: string }) {
  const total = advances + declines + unchanged || 1;
  const advPct = Math.round(advances / total * 100);
  const decPct = Math.round(declines / total * 100);
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-gray-400">{label}</span>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-green-400 font-semibold">▲ {advances.toLocaleString()}</span>
          {unchanged > 0 && <span className="text-gray-500">— {unchanged.toLocaleString()}</span>}
          <span className="text-red-400 font-semibold">▼ {declines.toLocaleString()}</span>
        </div>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden bg-white/5">
        <div className="bg-green-400" style={{ width: `${advPct}%` }} />
        {unchanged > 0 && <div className="bg-gray-600" style={{ width: `${Math.round(unchanged / total * 100)}%` }} />}
        <div className="bg-red-400" style={{ width: `${decPct}%` }} />
      </div>
    </div>
  );
}

/* ── page ────────────────────────────────────────────────────── */

export default function BreadthPage() {
  const [data,    setData]    = useState<BreadthData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/kr/breadth')
      .then(r => r.json()).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const mb    = data?.ma_breadth ?? {};
  const naver = data?.advance_decline.naver ?? {};
  const hl    = data?.new_highs_lows;
  const hlRatioGood = hl && hl.ratio !== null && hl.ratio > 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">시장 폭 분석</h1>
          <p className="text-gray-400 text-sm mt-1">Market Breadth — MA 위치 · 등락 · 52주 고저</p>
        </div>
        {data && (
          <div className="text-right">
            <p className="text-xs text-gray-600">업데이트 {data.updated_at}</p>
            <p className="text-xs text-gray-700 mt-0.5">{data.universe.source}</p>
          </div>
        )}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20 text-gray-500 gap-2">
          <i className="fa-solid fa-spinner fa-spin" /><span>분석 중...</span>
        </div>
      )}

      {data && (
        <>
          {/* MA 브레드스 */}
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">이동평균 상위 비율 (추적 유니버스 {data.universe.total}종목)</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[['20', 'MA20 상위'], ['60', 'MA60 상위'], ['120', 'MA120 상위'], ['200', 'MA200 상위']].map(([w, label]) => {
                const d = mb[w];
                return d ? (
                  <GaugeBar key={w} pct={d.pct} label={label}
                    sublabel={`${d.count}/${data.universe.total}종목 (하회 ${d.below})`} />
                ) : null;
              })}
            </div>
          </div>

          {/* 등락 종목 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5 space-y-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider">등락 종목 수</p>

            {/* 추적 유니버스 */}
            {data.advance_decline.tracked && (() => {
              const t = data.advance_decline.tracked;
              return (
                <AdBar advances={t.advances} declines={t.declines} unchanged={t.unchanged}
                  label={`추적 유니버스 (${data.universe.total}종목) — A/D ${t.ratio ?? '--'}`} />
              );
            })()}

            {/* Naver 실시간 */}
            {Object.entries(naver).map(([market, ad]) => (
              <AdBar key={market} advances={ad.advances} declines={ad.declines}
                label={`${market} 전체 — A/D ${ad.ratio ?? '--'}${ad.upper_limit ? ` | 상한 ${ad.upper_limit} / 하한 ${ad.lower_limit}` : ''}`} />
            ))}

            {Object.keys(naver).length === 0 && (
              <p className="text-xs text-gray-600">Naver 실시간 A/D 데이터 로드 실패 (추적 유니버스만 표시)</p>
            )}
          </div>

          {/* 52주 신고/신저 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">52주 신고가 / 신저가</p>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <p className="text-3xl font-bold text-green-400">{hl?.new_high_52w ?? '--'}</p>
                <p className="text-xs text-gray-500 mt-1">신고가 종목</p>
              </div>
              <div className="text-center">
                <p className={`text-3xl font-bold ${hlRatioGood ? 'text-green-400' : 'text-red-400'}`}>
                  {hl?.ratio !== null && hl?.ratio !== undefined ? hl.ratio.toFixed(2) : '--'}
                </p>
                <p className="text-xs text-gray-500 mt-1">고/저 비율</p>
                <p className="text-[10px] text-gray-600 mt-0.5">{hlRatioGood ? '▲ 강세' : hl?.ratio !== null ? '▼ 약세' : ''}</p>
              </div>
              <div className="text-center">
                <p className="text-3xl font-bold text-red-400">{hl?.new_low_52w ?? '--'}</p>
                <p className="text-xs text-gray-500 mt-1">신저가 종목</p>
              </div>
            </div>
          </div>

          {/* 해석 가이드 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">해석 가이드</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                { range: 'MA20 > 70%', label: '강한 단기 상승장', color: 'text-green-400' },
                { range: 'MA60 > 60%', label: '건강한 중기 추세', color: 'text-green-400' },
                { range: 'MA200 < 40%', label: '장기 하락세 경고', color: 'text-red-400' },
                { range: 'A/D < 0.8',   label: '하락 종목 우세 — 분산 매도', color: 'text-orange-400' },
                { range: '고/저 > 2.0', label: '확장 국면 — 적극 매수 가능', color: 'text-green-400' },
                { range: '고/저 < 0.5', label: '위축 국면 — 현금 비중 확대', color: 'text-red-400' },
              ].map(({ range, label, color }) => (
                <div key={range} className="flex items-center gap-2">
                  <span className={`text-xs font-mono ${color} w-28 flex-shrink-0`}>{range}</span>
                  <span className="text-xs text-gray-400">{label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white/3 border border-white/5 rounded-xl p-4">
            <p className="text-xs text-gray-600 leading-relaxed">
              <i className="fa-solid fa-circle-info text-gray-700 mr-1.5" />
              MA 분석은 daily_prices.csv에 등록된 추적 유니버스 {data.universe.total}종목 기준입니다.
              전체 시장 A/D는 Naver 증권에서 실시간으로 수집합니다. 데이터 부족 시 파악된 종목 기준으로만 표시됩니다.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
