'use client';

import { useEffect, useState, useCallback } from 'react';
import { krAPI } from '@/lib/api';
import StockChart from '@/components/ui/StockChart';

/* ── 타입 ───────────────────────────────────────────────────── */

interface Gem {
  ticker: string;
  name: string;
  price: number;
  change_pct: number;
  volume_ratio: number;
  above_ma60?: boolean;
  scan_time: string;
}

interface GemsData {
  last_updated: string | null;
  count: number;
  gems: Gem[];
  message?: string;
}

/* ── 세부 정보 셀 ─────────────────────────────────────────── */

function GemMeta({
  label,
  value,
  className = '',
}: {
  label: string;
  value: string | number;
  className?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</span>
      <span className={`text-sm font-semibold ${className || 'text-gray-200'}`}>{value}</span>
    </div>
  );
}

/* ── 차트 모달 ─────────────────────────────────────────────── */

function ChartModal({
  gem,
  onClose,
}: {
  gem: Gem;
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const volColor =
    gem.volume_ratio >= 5
      ? 'text-rose-400'
      : gem.volume_ratio >= 3
      ? 'text-orange-400'
      : 'text-yellow-400';

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-6 w-full max-w-2xl shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg">
              <i className="fa-solid fa-gem text-white text-base" />
            </div>
            <div>
              <p className="font-bold text-white text-lg leading-tight">{gem.name}</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {gem.ticker} · 스캔: {gem.scan_time}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
          >
            <i className="fa-solid fa-times" />
          </button>
        </div>

        {/* 원석 지표 */}
        <div className="grid grid-cols-4 gap-3 mb-5 p-3 rounded-xl bg-white/5 border border-white/[0.08]">
          <GemMeta
            label="현재가"
            value={`₩${gem.price.toLocaleString()}`}
            className="text-white"
          />
          <GemMeta
            label="등락률"
            value={`+${gem.change_pct.toFixed(2)}%`}
            className="text-rose-400"
          />
          <GemMeta
            label="거래량 배수"
            value={`${gem.volume_ratio}x`}
            className={volColor}
          />
          <GemMeta
            label="MA60 위치"
            value={
              gem.above_ma60 === undefined ? '--' : gem.above_ma60 ? '위 ✓' : '아래'
            }
            className={gem.above_ma60 ? 'text-emerald-400' : 'text-gray-500'}
          />
        </div>

        {/* 차트 */}
        <div className="h-[400px]">
          <StockChart ticker={gem.ticker} marketType="KR" />
        </div>
      </div>
    </div>
  );
}

/* ── 거래량 뱃지 ──────────────────────────────────────────── */

function VolBadge({ ratio }: { ratio: number }) {
  const tier =
    ratio >= 5
      ? { bg: 'bg-rose-500/20', text: 'text-rose-300', ring: 'ring-1 ring-rose-500/40', label: '폭발' }
      : ratio >= 3
      ? { bg: 'bg-orange-500/20', text: 'text-orange-300', ring: 'ring-1 ring-orange-500/40', label: '급증' }
      : ratio >= 2
      ? { bg: 'bg-yellow-500/20', text: 'text-yellow-300', ring: 'ring-1 ring-yellow-500/40', label: '증가' }
      : { bg: 'bg-gray-500/20', text: 'text-gray-400', ring: 'ring-1 ring-gray-500/30', label: '보통' };

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${tier.bg} ${tier.text} ${tier.ring}`}
    >
      <i className="fa-solid fa-bolt text-[8px]" />
      {ratio}x {tier.label}
    </span>
  );
}

/* ── 스캔 시각 표시 ───────────────────────────────────────── */

function ScanStatus({
  lastUpdated,
  count,
}: {
  lastUpdated: string | null;
  count: number;
}) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);

  if (!lastUpdated) return null;
  const scanDate = new Date(lastUpdated.replace(' ', 'T'));
  const diffMin = Math.round((now - scanDate.getTime()) / 60_000);
  const isRecent = diffMin < 6;

  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          isRecent ? 'bg-green-400 animate-pulse' : 'bg-yellow-400'
        }`}
      />
      <span className={isRecent ? 'text-green-400' : 'text-yellow-400'}>
        마지막 스캔 {diffMin < 1 ? '방금' : `${diffMin}분 전`} · {count}개 원석
      </span>
    </div>
  );
}

/* ── 페이지 본문 ──────────────────────────────────────────── */

export default function IntradayGemsPage() {
  const [data, setData] = useState<GemsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedGem, setSelectedGem] = useState<Gem | null>(null);
  const [sortBy, setSortBy] = useState<'volume_ratio' | 'change_pct'>('volume_ratio');
  const [onlyMa60, setOnlyMa60] = useState(false);

  const fetchData = useCallback(() => {
    setLoading(true);
    krAPI
      .getIntradayGems()
      .then((res: any) =>
        setData(res ?? { count: 0, gems: [], last_updated: null })
      )
      .catch(() => setData({ count: 0, gems: [], last_updated: null }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 5분마다 자동 갱신
  useEffect(() => {
    const id = setInterval(fetchData, 5 * 60_000);
    return () => clearInterval(id);
  }, [fetchData]);

  const gems = (data?.gems ?? [])
    .filter((g) => !onlyMa60 || g.above_ma60)
    .sort((a, b) =>
      sortBy === 'volume_ratio'
        ? b.volume_ratio - a.volume_ratio
        : b.change_pct - a.change_pct
    );

  return (
    <div className="space-y-6">

      {/* ── 헤더 ─────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-xl">
            <i className="fa-solid fa-gem text-white text-xl" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">장중 원석</h1>
            <p className="text-gray-400 text-sm mt-0.5">
              Intraday Gem Hunter · 거래량 급등 + 정배열 종목 자동 탐색
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 mt-1">
          {data?.last_updated && (
            <ScanStatus lastUpdated={data.last_updated} count={data.count} />
          )}
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300 hover:bg-white/10 transition-colors disabled:opacity-50"
          >
            <i
              className={`fa-solid fa-rotate-right text-[10px] ${
                loading ? 'animate-spin' : ''
              }`}
            />
            새로고침
          </button>
        </div>
      </div>

      {/* ── 스캔 조건 안내 뱃지 ────────────────────────── */}
      <div className="flex flex-wrap gap-2 text-[11px]">
        {[
          { icon: 'fa-arrow-trend-up', label: '양봉 (전일 대비 상승)', color: 'text-rose-400' },
          { icon: 'fa-chart-line', label: 'MA20 위 (정배열 초입)', color: 'text-cyan-400' },
          { icon: 'fa-bolt', label: '거래량 평균 이상 폭발', color: 'text-yellow-400' },
          { icon: 'fa-percent', label: '등락률 15% 미만', color: 'text-gray-400' },
        ].map((c) => (
          <span
            key={c.label}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/5 border border-white/[0.08]"
          >
            <i className={`fa-solid ${c.icon} ${c.color} text-[9px]`} />
            <span className="text-gray-400">{c.label}</span>
          </span>
        ))}
      </div>

      {/* ── 정렬 / 필터 ─────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1 bg-white/5 border border-white/10 rounded-lg p-0.5 text-[11px]">
          <button
            onClick={() => setSortBy('volume_ratio')}
            className={`px-3 py-1.5 rounded-md transition-colors font-medium ${
              sortBy === 'volume_ratio'
                ? 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            <i className="fa-solid fa-bolt mr-1" />
            거래량순
          </button>
          <button
            onClick={() => setSortBy('change_pct')}
            className={`px-3 py-1.5 rounded-md transition-colors font-medium ${
              sortBy === 'change_pct'
                ? 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            <i className="fa-solid fa-arrow-trend-up mr-1" />
            등락률순
          </button>
        </div>

        <button
          onClick={() => setOnlyMa60(!onlyMa60)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all ${
            onlyMa60
              ? 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40'
              : 'bg-white/5 border border-white/10 text-gray-500 hover:text-gray-300'
          }`}
        >
          <i className="fa-solid fa-filter text-[9px]" />
          MA60 위만
        </button>

        {!loading && (
          <span className="ml-auto px-3 py-1 rounded-full bg-white/5 border border-white/10 text-sm font-medium text-white">
            {gems.length}개
          </span>
        )}
      </div>

      {/* ── 목록 ─────────────────────────────────────────── */}
      {loading ? (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-2 space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 rounded-lg bg-white/5 animate-pulse" />
          ))}
        </div>
      ) : gems.length === 0 ? (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-14 flex flex-col items-center text-center">
          <i className="fa-solid fa-gem text-gray-700 text-5xl mb-4" />
          {data?.message ? (
            <>
              <p className="text-gray-400 font-medium">{data.message}</p>
              <p className="text-gray-600 text-sm mt-1">
                거래일 09:05~15:25 사이 5분 간격으로 자동 스캔됩니다.
              </p>
            </>
          ) : onlyMa60 ? (
            <>
              <p className="text-gray-400 font-medium">MA60 위 종목이 없습니다.</p>
              <button
                onClick={() => setOnlyMa60(false)}
                className="mt-3 text-sm text-amber-400 hover:text-amber-300 transition-colors"
              >
                필터 해제하기
              </button>
            </>
          ) : (
            <>
              <p className="text-gray-400 font-medium">현재 탐색된 원석이 없습니다.</p>
              <p className="text-gray-600 text-sm mt-1">장중(09:05~15:25)에 자동 스캔됩니다.</p>
            </>
          )}
        </div>
      ) : (
        <div className="rounded-2xl bg-[#1a1f2e] border border-white/10 p-2">
          {gems.map((gem, i) => (
            <div
              key={gem.ticker + gem.scan_time}
              onClick={() => setSelectedGem(gem)}
              className={`flex items-center gap-4 px-4 py-3.5 hover:bg-white/[0.04] rounded-xl transition-colors cursor-pointer group ${
                i < gems.length - 1 ? 'border-b border-white/5' : ''
              }`}
            >
              {/* 순위 */}
              <span className="text-sm font-bold text-gray-600 w-6 text-center flex-shrink-0">
                {i + 1}
              </span>

              {/* 젬 아이콘 */}
              <div
                className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md ${
                  gem.volume_ratio >= 5
                    ? 'bg-gradient-to-br from-rose-500 to-pink-600'
                    : gem.volume_ratio >= 3
                    ? 'bg-gradient-to-br from-orange-500 to-amber-500'
                    : 'bg-gradient-to-br from-amber-400 to-yellow-500'
                }`}
              >
                <i className="fa-solid fa-gem text-white text-sm" />
              </div>

              {/* 종목 정보 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="text-sm font-semibold text-white truncate group-hover:text-amber-300 transition-colors">
                    {gem.name}
                  </p>
                  <span className="text-[11px] text-gray-500">{gem.ticker}</span>
                  <VolBadge ratio={gem.volume_ratio} />
                  {gem.above_ma60 && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/15 text-emerald-400">
                      MA60+
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-gray-500 mt-0.5">
                  ₩{gem.price.toLocaleString()} · 스캔{' '}
                  {gem.scan_time.split(' ')[1] ?? ''}
                </p>
              </div>

              {/* 등락률 */}
              <div className="text-right flex-shrink-0">
                <p className="text-sm font-bold text-rose-400">
                  +{gem.change_pct.toFixed(2)}%
                </p>
                <p className="text-[10px] text-gray-600">당일 상승률</p>
              </div>

              <i className="fa-solid fa-chevron-right text-gray-600 group-hover:text-amber-400 text-xs transition-colors flex-shrink-0" />
            </div>
          ))}
        </div>
      )}

      {/* ── 스캔 기준 안내 ─────────────────────────────── */}
      {!loading && data?.last_updated && (
        <div className="rounded-xl bg-white/[0.03] border border-white/[0.08] p-4 text-[11px] text-gray-500 space-y-1">
          <p className="flex items-center gap-1.5 font-medium text-gray-400">
            <i className="fa-solid fa-circle-info text-amber-500" />
            장중 원석(Gem Hunter) 스캔 기준
          </p>
          <p>• 네이버 거래량 상위 150종목 중 양봉(상승) + 등락률 15% 미만 선별</p>
          <p>• 현재가가 20일 이동평균선(MA20) 위에 있어야 함 (정배열 초입)</p>
          <p>• 거래량이 20일 평균 이상 발생 (거래량 배수로 품질 구분)</p>
          <p>
            •{' '}
            <span className="text-emerald-400 font-medium">MA60+</span> 표시: 60일선도
            돌파한 강한 상승 종목
          </p>
          <p>• 자동 스캔: 거래일 09:05~15:25, 5분 간격</p>
        </div>
      )}

      {/* ── 차트 모달 ──────────────────────────────────── */}
      {selectedGem && (
        <ChartModal gem={selectedGem} onClose={() => setSelectedGem(null)} />
      )}
    </div>
  );
}
