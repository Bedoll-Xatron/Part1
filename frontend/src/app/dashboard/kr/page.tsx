'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import FreshnessIndicator from '@/components/ui/FreshnessIndicator';
import { krAPI, KRMarketGate, KRSignalsResponse, BacktestSummary } from '@/lib/api';
import { usePriceStream } from '@/hooks/usePriceStream';

/* ── helpers ─────────────────────────────────────────────────── */

function getSectorBg(pct: number): string {
  const intensity = Math.min(Math.abs(pct) / 3, 1);
  if (pct > 0.05) return `rgba(244, 63, 94, ${0.08 + intensity * 0.25})`;
  if (pct < -0.05) return `rgba(59, 130, 246, ${0.08 + intensity * 0.25})`;
  return 'rgba(255,255,255,0.04)';
}

// 실제 Flask API는 regime 문자열을 반환 — score/label로 변환
function regimeToGate(regime?: string) {
  if (regime === 'RISK_ON') return { score: 80, label: 'RISK ON', colorClass: 'text-green-400', bgClass: 'bg-green-400/10 text-green-400' };
  if (regime === 'RISK_OFF') return { score: 20, label: 'RISK OFF', colorClass: 'text-red-400', bgClass: 'bg-red-400/10 text-red-400' };
  return { score: 50, label: 'NEUTRAL', colorClass: 'text-yellow-400', bgClass: 'bg-yellow-400/10 text-yellow-400' };
}

function ChangeBadge({ pct }: { pct?: number | null }) {
  if (pct == null) return <span className="text-xs text-gray-500">--</span>;
  const pos = pct >= 0;
  return (
    <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${pos ? 'text-rose-400 bg-rose-500/10' : 'text-blue-400 bg-blue-500/10'}`}>
      {pos ? '+' : ''}{pct.toFixed(2)}%
    </span>
  );
}

function getGradeColor(grade: string): string {
  if (grade === 'S') return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
  if (grade === 'A') return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
  if (grade === 'B') return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
  return 'bg-gray-500/15 text-gray-400 border-gray-500/30';
}

function getSignalScore(s: any): number {
  if (s?.score && typeof s.score === 'object') return s.score.total ?? 0;
  if (typeof s?.score === 'number') return s.score;
  if (typeof s?.total_score === 'number') return s.total_score;
  return 0;
}

/* ── skeleton pieces ─────────────────────────────────────────── */

function StripSkeleton() {
  return <div className="h-20 rounded-2xl bg-white/5 animate-pulse" />;
}

function HeatmapSkeleton() {
  return (
    <div className="grid grid-cols-4 md:grid-cols-7 gap-1">
      {Array.from({ length: 7 }).map((_, i) => (
        <div key={i} className="h-16 rounded-lg bg-white/5 animate-pulse" />
      ))}
    </div>
  );
}

function CardsSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="h-44 rounded-2xl bg-white/5 animate-pulse" />
      <div className="h-44 rounded-2xl bg-white/5 animate-pulse" />
    </div>
  );
}

/* ── page ────────────────────────────────────────────────────── */

export default function KROverviewPage() {
  const [gateData, setGateData] = useState<KRMarketGate | null>(null);
  const [signalsData, setSignalsData] = useState<KRSignalsResponse | null>(null);
  const [closingBetData, setClosingBetData] = useState<any>(null);
  const [backtestData, setBacktestData] = useState<BacktestSummary | null>(null);
  const [intradayGemsData, setIntradayGemsData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [activeTab, setActiveTab] = useState<'vcp' | 'closing' | 'gems'>('gems');

  const loadData = useCallback(async () => {
    setLoading(true);
    const [gate, signals, backtest, closing, gems] = await Promise.all([
      krAPI.getMarketGate().catch(() => null),
      krAPI.getSignals().catch(() => null),
      krAPI.getBacktestSummary().catch(() => null),
      krAPI.getClosingBet().catch(() => null),
      krAPI.getIntradayGems().catch(() => null),
    ]);
    setGateData(gate);
    setSignalsData(signals);
    setBacktestData(backtest);
    setClosingBetData(closing);
    setIntradayGemsData(gems);
    setLastUpdated(new Date());
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const vcpTickers = (signalsData?.signals ?? []).map(
    (s: any) => s.stock_code ?? s.ticker ?? ''
  ).filter(Boolean);
  const closingTickers = (closingBetData?.signals ?? []).map(
    (s: any) => s.stock_code ?? ''
  ).filter(Boolean);
  const allTickers = [...new Set([...vcpTickers, ...closingTickers])];
  const { prices: streamPrices, connected } = usePriceStream(allTickers);

  // Flask API는 regime 반환 — KRMarketGate 타입과 불일치하므로 any로 접근
  const raw = gateData as any;
  const { score: gateScore, label: gateLabel, colorClass: scoreColor, bgClass: scoreBg } =
    regimeToGate(raw?.regime);
  const sectors: { name: string; change_pct: number }[] = raw?.sectors ?? gateData?.sectors ?? [];

  return (
    <div className="space-y-4">

      {/* ── Header ───────────────────────────────────────────── */}
      <div className="flex justify-between items-start">
        <div>
          <span className="inline-flex items-center px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse mr-2" />
            KR Market Alpha
          </span>
          <h1 className="text-4xl font-bold text-white mt-2">
            Smart Money{' '}
            <span className="bg-gradient-to-r from-rose-400 to-amber-400 bg-clip-text text-transparent">
              Footprints
            </span>
          </h1>
          <p className="text-gray-400 mt-1 text-sm">VCP 패턴 &amp; 종가베팅 종합 대시보드</p>
        </div>

        <div className="flex flex-col items-end gap-2 mt-1">
          <button
            onClick={loadData}
            className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
          >
            <i className={`fa-solid fa-sync-alt text-sm ${loading ? 'animate-spin' : ''}`} />
          </button>
          <FreshnessIndicator lastUpdated={lastUpdated} />
        </div>
      </div>


      {/* ── Market Strip ─────────────────────────────────────── */}
      {loading ? <StripSkeleton /> : (
        <div className="flex items-center gap-6 bg-[#1a1f2e] border border-white/10 rounded-2xl px-6 py-4">
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">KOSPI</p>
            <p className="text-lg font-bold text-white">{raw?.kospi?.close?.toLocaleString() ?? '--'}</p>
            <ChangeBadge pct={raw?.kospi?.change_pct} />
          </div>

          <div className="w-px h-10 bg-white/10" />

          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">KOSDAQ</p>
            <p className="text-lg font-bold text-white">{raw?.kosdaq?.close?.toLocaleString() ?? '--'}</p>
            <ChangeBadge pct={raw?.kosdaq?.change_pct} />
          </div>

          <div className="w-px h-10 bg-white/10" />

          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">MARKET GATE</p>
            <p className={`text-lg font-bold ${gateData ? scoreColor : 'text-gray-500'}`}>
              {gateData ? gateScore : '--'}
            </p>
            {gateData && (
              <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${scoreBg}`}>{gateLabel}</span>
            )}
          </div>
        </div>
      )}

      {/* ── 오늘의 시그널 탭 ─────────────────────────────────── */}
      <div className="mt-6 rounded-2xl bg-[#1a1f2e] border border-white/10">

        {/* 탭 헤더 */}
        <div className="px-5 pt-4 flex justify-between items-center">
          <p className="text-lg font-bold text-white">오늘의 시그널</p>
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-[10px] text-gray-500">{connected ? '실시간' : '폴백'}</span>
          </div>
        </div>

        {/* 탭 바 */}
        <div className="flex border-b border-white/10 mt-3">
          {(['gems', 'vcp', 'closing'] as const).map((tab) => {
            const isGems   = tab === 'gems';
            const isVcp    = tab === 'vcp';
            let count = 0;
            if (isGems) count = intradayGemsData?.count ?? intradayGemsData?.gems?.length ?? 0;
            else if (isVcp) count = signalsData?.signals?.length ?? 0;
            else count = closingBetData?.filtered_count ?? closingBetData?.signals?.length ?? 0;
            
            const active   = activeTab === tab;
            const accentBg = isGems ? 'bg-emerald-500' : isVcp ? 'bg-rose-500' : 'bg-violet-500';
            const tabName  = isGems ? '🚀 장중 원석' : isVcp ? 'VCP' : '종가베팅';
            
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-3 text-sm font-medium relative transition-colors ${
                  active ? 'text-white' : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {tabName}
                <span className={`ml-1.5 text-[10px] px-1.5 py-0.5 rounded-full ${
                  active
                    ? isGems ? 'bg-emerald-500/20 text-emerald-400' : isVcp ? 'bg-rose-500/20 text-rose-400' : 'bg-violet-500/20 text-violet-400'
                    : 'bg-white/5 text-gray-500'
                }`}>
                  {count}
                </span>
                {active && (
                  <span className={`absolute bottom-0 left-0 right-0 h-0.5 ${accentBg}`} />
                )}
              </button>
            );
          })}
        </div>

        {/* 탭 내용 */}
        <div className="p-2">

          {loading ? (
            <div className="space-y-2 p-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-16 rounded-lg bg-white/5 animate-pulse" />
              ))}
            </div>
          ) : activeTab === 'gems' ? (
            /* ── 장중 원석 탭 ── */
            (() => {
              const list = intradayGemsData?.gems ?? [];
              if (list.length === 0) return (
                <div className="py-12 text-center">
                  <p className="text-gray-500 text-sm">현재 발굴된 장중 급상승 원석이 없습니다</p>
                  {intradayGemsData?.last_updated && (
                    <p className="text-[10px] text-gray-600 mt-2">마지막 스캔: {intradayGemsData.last_updated}</p>
                  )}
                </div>
              );
              return (
                <div>
                  <div className="px-4 py-2 flex justify-between text-[10px] text-gray-500 bg-black/20 rounded-lg mb-2">
                    <span>마지막 스캔: {intradayGemsData.last_updated}</span>
                  </div>
                  {list.map((s: any, i: number) => {
                    const ticker     = s.ticker ?? '';
                    const name       = s.name ?? '';
                    const livePrice  = streamPrices[ticker.toUpperCase()]?.price ?? s.price ?? 0;
                    return (
                      <div
                        key={ticker}
                        className={`flex items-center gap-4 px-4 py-3.5 hover:bg-white/[0.02] rounded-xl transition-colors cursor-default ${
                          i < list.length - 1 ? 'border-b border-white/5' : ''
                        }`}
                      >
                        <span className="text-sm font-bold text-gray-500 w-6 text-center">{i + 1}</span>
                        <div className="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-white bg-gradient-to-br from-emerald-500 to-teal-500">
                          GEM
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-white truncate">
                            {name}
                            <span className="ml-1.5 inline text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-medium border border-emerald-500/20">
                              거래량 {s.volume_ratio}배 폭발
                            </span>
                          </p>
                          <p className="text-[11px] text-gray-500 mt-0.5">
                            {ticker} · 당일 +{s.change_pct}% 상승 중
                          </p>
                        </div>
                        <div className="text-right min-w-[80px]">
                          <p className={`text-sm font-bold text-rose-400`}>
                            ₩{livePrice > 0 ? livePrice.toLocaleString() : '--'}
                          </p>
                          <p className="text-[10px] text-gray-500">
                            {s.scan_time.split(' ')[1]} 포착
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })()
          ) : activeTab === 'vcp' ? (
            /* ── VCP 탭 ── */
            (() => {
              const list = [...(signalsData?.signals ?? [])]
                .sort((a: any, b: any) => getSignalScore(b) - getSignalScore(a));
              if (list.length === 0) return (
                <p className="py-12 text-center text-gray-500 text-sm">오늘 발생한 VCP 시그널이 없습니다</p>
              );
              return (
                <div>
                  {list.map((s: any, i: number) => {
                    const ticker = s.stock_code ?? s.ticker ?? '';
                    const name = s.stock_name ?? s.name ?? '';
                    const score = getSignalScore(s);
                    const isKospi = (s.market ?? '').toUpperCase().includes('KOSPI');
                    const livePrice = streamPrices[ticker.toUpperCase()]?.price ?? s.current_price ?? 0;
                    const liveReturn = s.entry_price > 0
                      ? (livePrice - s.entry_price) / s.entry_price * 100
                      : 0;
                    return (
                      <div
                        key={ticker + s.signal_date}
                        className={`flex items-center gap-4 px-4 py-3.5 hover:bg-white/[0.02] rounded-xl transition-colors cursor-default ${i < list.length - 1 ? 'border-b border-white/5' : ''
                          }`}
                      >
                        <span className="text-sm font-bold text-gray-500 w-6 text-center">{i + 1}</span>

                        <div className={`w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-white ${isKospi
                            ? 'bg-gradient-to-br from-rose-500 to-orange-500'
                            : 'bg-gradient-to-br from-blue-500 to-cyan-500'
                          }`}>
                          {isKospi ? 'KP' : 'KQ'}
                        </div>

                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-white truncate">
                            {name}
                            {s.grade && (
                              <span className={`ml-2 inline text-[10px] px-1.5 py-0.5 rounded border font-bold ${getGradeColor(s.grade)}`}>
                                {s.grade}
                              </span>
                            )}
                            <span className="ml-1.5 inline text-[10px] px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-400 font-medium">
                              {score}점
                            </span>
                          </p>
                          <p className="text-[11px] text-gray-500 mt-0.5">
                            {ticker} · 진입 ₩{s.entry_price?.toLocaleString() ?? '--'}
                            {s.signal_date && ` · ${s.signal_date}`}
                          </p>
                        </div>

                        <div className="text-right min-w-[80px]">
                          <p className={`text-sm font-bold ${liveReturn >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                            {liveReturn >= 0 ? '+' : ''}{liveReturn.toFixed(2)}%
                          </p>
                          <p className="text-[10px] text-gray-500">
                            ₩{livePrice > 0 ? livePrice.toLocaleString() : '--'}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })()
          ) : (
            /* ── 종가베팅 탭 ── */
            (() => {
              const list = [...(closingBetData?.signals ?? [])]
                .sort((a: any, b: any) => getSignalScore(b) - getSignalScore(a));
              if (list.length === 0) return (
                <p className="py-12 text-center text-gray-500 text-sm">오늘 발생한 종가베팅 시그널이 없습니다</p>
              );
              return (
                <div>
                  {list.map((s: any, i: number) => {
                    const ticker = s.stock_code ?? s.ticker ?? '';
                    const name = s.stock_name ?? s.name ?? '';
                    const score = getSignalScore(s);
                    const isKospi = (s.market ?? '').toUpperCase().includes('KOSPI');
                    const livePrice = streamPrices[ticker.toUpperCase()]?.price ?? s.current_price ?? 0;
                    const liveReturn = s.entry_price > 0
                      ? (livePrice - s.entry_price) / s.entry_price * 100
                      : 0;
                    const themes: string[] = s.themes ?? [];
                    return (
                      <div
                        key={ticker + s.signal_date}
                        className={`flex items-center gap-4 px-4 py-3.5 hover:bg-white/[0.02] rounded-xl transition-colors cursor-default ${i < list.length - 1 ? 'border-b border-white/5' : ''
                          }`}
                      >
                        <span className="text-sm font-bold text-gray-500 w-6 text-center">{i + 1}</span>

                        <div className={`w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-white ${isKospi
                            ? 'bg-gradient-to-br from-rose-500 to-orange-500'
                            : 'bg-gradient-to-br from-blue-500 to-cyan-500'
                          }`}>
                          {isKospi ? 'KP' : 'KQ'}
                        </div>

                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-white truncate">
                            {name}
                            {s.grade && (
                              <span className={`ml-2 inline text-[10px] px-1.5 py-0.5 rounded border font-bold ${getGradeColor(s.grade)}`}>
                                {s.grade}
                              </span>
                            )}
                            <span className="ml-1.5 inline text-[10px] px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-400 font-medium">
                              {score}점
                            </span>
                          </p>
                          <p className="text-[11px] text-gray-500 mt-0.5">
                            {ticker} · 진입 ₩{s.entry_price?.toLocaleString() ?? '--'}
                            {s.target_price && ` · 목표 ₩${s.target_price.toLocaleString()}`}
                            {s.stop_price && ` · 손절 ₩${s.stop_price.toLocaleString()}`}
                          </p>
                          {themes.length > 0 && (
                            <div className="flex gap-1 mt-1 flex-wrap">
                              {themes.slice(0, 3).map((t: string) => (
                                <span key={t} className="px-1.5 py-0.5 bg-white/5 text-[10px] text-gray-400 rounded border border-white/5">
                                  {t}
                                </span>
                              ))}
                              {themes.length > 3 && (
                                <span className="px-1.5 py-0.5 bg-white/5 text-[10px] text-gray-400 rounded border border-white/5">
                                  +{themes.length - 3}
                                </span>
                              )}
                            </div>
                          )}
                        </div>

                        <div className="text-right min-w-[80px]">
                          <p className={`text-sm font-bold ${liveReturn >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                            {liveReturn >= 0 ? '+' : ''}{liveReturn.toFixed(2)}%
                          </p>
                          <p className="text-[10px] text-gray-500">
                            ₩{livePrice > 0 ? livePrice.toLocaleString() : '--'}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })()
          )}

        </div>
      </div>

      {/* ── Sector Heatmap ───────────────────────────────────── */}
      <div>
        <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Sector</p>
        {loading ? <HeatmapSkeleton /> : (
          sectors.length === 0 ? (
            <p className="text-sm text-gray-600">섹터 데이터 없음</p>
          ) : (
            <div className="grid grid-cols-4 md:grid-cols-7 gap-1">
              {sectors.map((s) => (
                <div
                  key={s.name}
                  className="rounded-lg p-2 text-center cursor-default transition-all duration-150 hover:brightness-125"
                  style={{ background: getSectorBg(s.change_pct) }}
                >
                  <p className="text-[11px] text-gray-400 truncate">{s.name}</p>
                  <p className={`text-sm font-black ${s.change_pct > 0.05 ? 'text-rose-400' :
                      s.change_pct < -0.05 ? 'text-blue-400' : 'text-gray-400'
                    }`}>
                    {s.change_pct > 0.05 ? '+' : ''}{s.change_pct.toFixed(2)}%
                  </p>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* ── Strategy Cards ───────────────────────────────────── */}
      {loading ? <CardsSkeleton /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {/* VCP */}
          <Link href="/dashboard/kr/vcp" className="group block bg-[#1a1f2e] border border-white/10 rounded-2xl p-5 relative overflow-hidden hover:border-amber-500/30 cursor-pointer transition-all duration-300">
            <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/10 rounded-full blur-[30px] -translate-y-1/2 translate-x-1/2 pointer-events-none" />
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
                <i className="fa-solid fa-chart-line text-amber-400 text-sm" />
              </div>
              <span className="text-white font-semibold">VCP Strategy</span>
              <span className="text-[10px] bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded-full">Backtest</span>
            </div>

            <div className="mt-4 flex items-baseline gap-3 flex-wrap">
              <div className="flex flex-col">
                <span className="text-3xl font-black text-white hover:text-amber-400 transition-colors">
                  {backtestData?.vcp?.win_rate != null ? `${backtestData.vcp.win_rate}%` : '--'}
                </span>
                <span className="text-[10px] text-gray-500">Win Rate</span>
              </div>
              <div className="w-px h-10 bg-white/10" />
              <div className="flex flex-col">
                <span className={`text-lg font-bold ${backtestData?.vcp?.avg_return != null
                    ? backtestData.vcp.avg_return >= 0 ? 'text-rose-400' : 'text-blue-400'
                    : 'text-gray-400'
                  }`}>
                  {backtestData?.vcp?.avg_return != null
                    ? `${backtestData.vcp.avg_return >= 0 ? '+' : ''}${backtestData.vcp.avg_return}%`
                    : '--'}
                </span>
                <span className="text-[10px] text-gray-500">Avg Return</span>
              </div>
              <div className="w-px h-10 bg-white/10" />
              <div className="flex flex-col">
                <span className="text-lg font-black text-white">{backtestData?.vcp?.count ?? '--'}</span>
                <span className="text-[10px] text-gray-500">Trades</span>
              </div>
              {backtestData?.vcp?.profit_factor != null && (
                <>
                  <div className="w-px h-10 bg-white/10" />
                  <div className="flex flex-col">
                    <span className="text-lg font-bold text-white">{backtestData.vcp.profit_factor}</span>
                    <span className="text-[10px] text-gray-500">Profit Factor</span>
                  </div>
                </>
              )}
            </div>

          </Link>

          {/* 종가베팅 */}
          <Link href="/dashboard/kr/closing-bet" className="group block bg-[#1a1f2e] border border-white/10 rounded-2xl p-5 relative overflow-hidden hover:border-violet-500/30 cursor-pointer transition-all duration-300">
            <div className="absolute top-0 right-0 w-24 h-24 bg-violet-500/10 rounded-full blur-[30px] -translate-y-1/2 translate-x-1/2 pointer-events-none" />
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-violet-500/15 flex items-center justify-center">
                <i className="fa-solid fa-clock text-violet-400 text-sm" />
              </div>
              <span className="text-white font-semibold">종가베팅</span>
              <span className="text-[10px] bg-violet-500/10 text-violet-400 px-2 py-0.5 rounded-full">Backtest</span>
            </div>

            {backtestData?.closing_bet?.status === 'Accumulating' ? (
              <div className="mt-4 flex items-center gap-3 text-gray-400 text-sm">
                <i className="fa-solid fa-database" />
                <span className="animate-pulse">Accumulating</span>
              </div>
            ) : (
              <div className="mt-4 flex items-baseline gap-3 flex-wrap">
                <div className="flex flex-col">
                  <span className="text-3xl font-black text-white hover:text-violet-400 transition-colors">
                    {backtestData?.closing_bet?.win_rate != null ? `${backtestData.closing_bet.win_rate}%` : '--'}
                  </span>
                  <span className="text-[10px] text-gray-500">Win Rate</span>
                </div>
                <div className="w-px h-10 bg-white/10" />
                <div className="flex flex-col">
                  <span className={`text-lg font-bold ${backtestData?.closing_bet?.avg_return != null
                      ? backtestData.closing_bet.avg_return >= 0 ? 'text-rose-400' : 'text-blue-400'
                      : 'text-gray-400'
                    }`}>
                    {backtestData?.closing_bet?.avg_return != null
                      ? `${backtestData.closing_bet.avg_return >= 0 ? '+' : ''}${backtestData.closing_bet.avg_return}%`
                      : '--'}
                  </span>
                  <span className="text-[10px] text-gray-500">Avg Return</span>
                </div>
                <div className="w-px h-10 bg-white/10" />
                <div className="flex flex-col">
                  <span className="text-lg font-black text-white">{backtestData?.closing_bet?.count ?? '--'}</span>
                  <span className="text-[10px] text-gray-500">Trades</span>
                </div>
              </div>
            )}

          </Link>

        </div>
      )}

    </div>
  );
}
