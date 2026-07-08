'use client';

import { useCallback, useEffect, useRef, useState, memo } from 'react';
import { chartAnalysisAPI, ChartAnalysisResult, ChartAnalysisStatus } from '@/lib/api';

import StockChart from '@/components/ui/StockChart';

/* ── constants ───────────────────────────────────────────────── */

const POLL_MS = 5_000;

const SIGNAL_STYLE: Record<string, { bg: string; text: string; dot: string }> = {
  BUY: { bg: 'bg-emerald-500/15', text: 'text-emerald-300', dot: 'bg-emerald-400' },
  SELL: { bg: 'bg-red-500/15', text: 'text-red-300', dot: 'bg-red-400' },
  HOLD: { bg: 'bg-yellow-500/15', text: 'text-yellow-300', dot: 'bg-yellow-400' },
  ERROR: { bg: 'bg-gray-500/15', text: 'text-gray-400', dot: 'bg-gray-500' },
};

const SORT_COLS = ['confidence', '종목명', '시장', 'signal', 'ma_status', 'rsi_zone', 'volume_trend'] as const;
type SortCol = typeof SORT_COLS[number];

/* ── helpers ─────────────────────────────────────────────────── */

function signalStyle(signal: string) {
  return SIGNAL_STYLE[signal] ?? SIGNAL_STYLE.ERROR;
}

function SignalBadge({ signal }: { signal: string }) {
  const s = signalStyle(signal);
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {signal}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const color = pct >= 70 ? '#10b981' : pct >= 40 ? '#f59e0b' : '#ef4444';
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs text-gray-300 w-8 text-right">{pct.toFixed(0)}%</span>
    </div>
  );
}

/* ── ChartModal ──────────────────────────────────────────────── */

const ChartModal = memo(function ChartModal({
  result,
  onClose,
}: {
  result: ChartAnalysisResult;
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-6 w-full max-w-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <SignalBadge signal={result.signal} />
              <p className="font-semibold text-white">{result.종목명}</p>
            </div>
            <p className="text-xs text-gray-500">{result.종목코드} · {result.시장}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
          >
            <i className="fa-solid fa-times" />
          </button>
        </div>

        {/* Gemini meta strip */}
        <div className="grid grid-cols-4 gap-2 mb-4 p-3 rounded-xl bg-white/5 border border-white/[0.08]">
          {[
            { label: '신뢰도', value: `${result.confidence.toFixed(0)}%` },
            { label: 'MA 배열', value: result.ma_status || '—' },
            { label: 'RSI', value: result.rsi_zone || '—' },
            { label: '거래량', value: result.volume_trend || '—' },
          ].map(({ label, value }) => (
            <div key={label} className="flex flex-col gap-0.5">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</span>
              <span className="text-sm font-semibold text-gray-200">{value}</span>
            </div>
          ))}
        </div>

        {/* Chart */}
        <div className="h-[400px] mb-4">
          <StockChart ticker={result.종목코드} marketType="KR" />
        </div>

        {result.reasons && (
          <div className="px-3 py-2.5 rounded-lg bg-white/5 border border-white/[0.08]">
            <p className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">분석 근거</p>
            <p className="text-xs text-gray-300 leading-relaxed">{result.reasons}</p>
          </div>
        )}
      </div>
    </div>
  );
});

/* ── main page ───────────────────────────────────────────────── */

export default function ChartScanPage() {
  const [status, setStatus] = useState<ChartAnalysisStatus | null>(null);
  const [results, setResults] = useState<ChartAnalysisResult[]>([]);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState<ChartAnalysisResult | null>(null);
  const [sortCol, setSortCol] = useState<SortCol>('confidence');
  const [sortAsc, setSortAsc] = useState(false);
  const [filterSignal, setFilterSignal] = useState<string>('ALL');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await chartAnalysisAPI.getStatus();
      setStatus(s);
      if (!s.running) {
        stopPolling();
        if (s.status === 'done') {
          const r = await chartAnalysisAPI.getResults();
          setResults(r.results);
          setSummary(r.summary);
        }
      }
    } catch { /* no-op */ }
  }, [stopPolling]);

  const startPolling = useCallback(() => {
    stopPolling();
    pollRef.current = setInterval(fetchStatus, POLL_MS);
  }, [fetchStatus, stopPolling]);

  // Load initial status and results on mount
  useEffect(() => {
    fetchStatus();
    chartAnalysisAPI.getResults().then((r) => {
      if (r.results.length) {
        setResults(r.results);
        setSummary(r.summary);
      }
    }).catch(() => { });
  }, [fetchStatus]);

  // Restart polling if status indicates running
  useEffect(() => {
    if (status?.running) startPolling();
    return stopPolling;
  }, [status?.running, startPolling, stopPolling]);

  const handleRun = async () => {
    setLoading(true);
    try {
      await chartAnalysisAPI.run();
      await fetchStatus();
      startPolling();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (col: SortCol) => {
    if (sortCol === col) setSortAsc((p) => !p);
    else { setSortCol(col); setSortAsc(col !== 'confidence'); }
  };

  const displayed = [...results]
    .filter((r) => filterSignal === 'ALL' || r.signal === filterSignal)
    .sort((a, b) => {
      let va: string | number = a[sortCol as keyof ChartAnalysisResult] as string | number;
      let vb: string | number = b[sortCol as keyof ChartAnalysisResult] as string | number;
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });

  const isRunning = status?.running ?? false;

  return (
    <div className="flex flex-col gap-5 p-6 min-h-0">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-white flex items-center gap-2">
            <i className="fa-solid fa-robot text-blue-400" />
            Gemini 차트 스캔
          </h1>
          <p className="text-xs text-gray-500 mt-0.5">
            한국 주식 100종목 · Gemini Vision 기술적 분석 · 매일 17:05 자동 실행
          </p>
        </div>

        <button
          onClick={handleRun}
          disabled={isRunning || loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all"
          style={{
            background: isRunning || loading ? 'rgba(41,98,255,0.2)' : 'rgba(41,98,255,0.9)',
            color: isRunning || loading ? '#6b7280' : '#fff',
            cursor: isRunning || loading ? 'not-allowed' : 'pointer',
          }}
        >
          {isRunning ? (
            <><i className="fa-solid fa-circle-notch fa-spin" /> 분석 중…</>
          ) : loading ? (
            <><i className="fa-solid fa-circle-notch fa-spin" /> 시작 중…</>
          ) : (
            <><i className="fa-solid fa-play" /> 분석 시작</>
          )}
        </button>
      </div>

      {/* ── Progress ───────────────────────────────────────────── */}
      {status && status.status !== 'idle' && (
        <div className="rounded-xl p-4" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(42,52,71,0.7)' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-300">
              {isRunning
                ? `진행 중 · ${status.current} / ${status.total}`
                : status.status === 'done'
                  ? `완료 · ${status.total}개 종목 분석`
                  : `오류: ${status.error ?? '알 수 없는 오류'}`}
            </span>
            <span className="text-xs font-bold" style={{ color: isRunning ? '#2962ff' : status.status === 'done' ? '#10b981' : '#ef4444' }}>
              {status.pct}%
            </span>
          </div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${status.pct}%`,
                background: isRunning ? '#2962ff' : status.status === 'done' ? '#10b981' : '#ef4444',
              }}
            />
          </div>
          {status.started_at && (
            <p className="text-[10px] text-gray-600 mt-1.5">
              시작: {new Date(status.started_at).toLocaleTimeString('ko-KR')}
              {status.finished_at && (
                <> · 완료: {new Date(status.finished_at).toLocaleTimeString('ko-KR')}</>
              )}
            </p>
          )}
        </div>
      )}

      {/* ── Summary cards ──────────────────────────────────────── */}
      {results.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {(['BUY', 'HOLD', 'SELL'] as const).map((sig) => {
            const count = summary[sig] ?? 0;
            const s = SIGNAL_STYLE[sig];
            return (
              <button
                key={sig}
                onClick={() => setFilterSignal(filterSignal === sig ? 'ALL' : sig)}
                className={`rounded-xl p-4 text-left transition-all ${filterSignal === sig ? 'ring-1' : ''}`}
                style={{
                  background: filterSignal === sig ? `rgba(${sig === 'BUY' ? '16,185,129' : sig === 'SELL' ? '239,68,68' : '245,158,11'},0.12)` : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${filterSignal === sig ? (sig === 'BUY' ? 'rgba(16,185,129,0.5)' : sig === 'SELL' ? 'rgba(239,68,68,0.5)' : 'rgba(245,158,11,0.5)') : 'rgba(42,52,71,0.7)'}`,
                }}
              >
                <p className={`text-xs font-semibold mb-1 ${s.text}`}>{sig}</p>
                <p className="text-2xl font-bold text-white">{count}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">
                  {results.length > 0 ? `${((count / results.length) * 100).toFixed(0)}%` : '—'}
                </p>
              </button>
            );
          })}
        </div>
      )}

      {/* ── Results table ──────────────────────────────────────── */}
      {results.length > 0 && (
        <div className="rounded-xl overflow-hidden flex-1" style={{ border: '1px solid rgba(42,52,71,0.7)' }}>
          {/* Table header controls */}
          <div className="flex items-center justify-between px-4 py-2.5" style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(42,52,71,0.7)' }}>
            <span className="text-xs text-gray-500">
              {filterSignal === 'ALL' ? `전체 ${results.length}개` : `${filterSignal} ${displayed.length}개`}
            </span>
            {filterSignal !== 'ALL' && (
              <button onClick={() => setFilterSignal('ALL')} className="text-[10px] text-blue-400 hover:text-blue-300">
                필터 해제
              </button>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.025)', borderBottom: '1px solid rgba(42,52,71,0.5)' }}>
                  {(
                    [
                      { col: '종목명', label: '종목' },
                      { col: '시장', label: '시장' },
                      { col: 'signal', label: '시그널' },
                      { col: 'confidence', label: '신뢰도' },
                      { col: 'ma_status', label: 'MA 배열' },
                      { col: 'rsi_zone', label: 'RSI' },
                      { col: 'volume_trend', label: '거래량' },
                    ] as { col: SortCol; label: string }[]
                  ).map(({ col, label }) => (
                    <th
                      key={col}
                      onClick={() => handleSort(col)}
                      className="px-3 py-2.5 text-left font-medium text-gray-500 cursor-pointer hover:text-gray-300 select-none whitespace-nowrap"
                    >
                      {label}
                      {sortCol === col && (
                        <i className={`fa-solid fa-caret-${sortAsc ? 'up' : 'down'} ml-1 text-blue-400`} />
                      )}
                    </th>
                  ))}
                  <th className="px-3 py-2.5 text-left font-medium text-gray-500">분석 근거</th>
                </tr>
              </thead>
              <tbody>
                {displayed.map((row) => (
                  <tr
                    key={row.종목코드}
                    onClick={() => setModal(row)}
                    className="cursor-pointer transition-colors hover:bg-white/5"
                    style={{ borderBottom: '1px solid rgba(42,52,71,0.35)' }}
                  >
                    <td className="px-3 py-2.5">
                      <p className="font-semibold text-gray-200">{row.종목명}</p>
                      <p className="text-[10px] text-gray-500">{row.종목코드}</p>
                    </td>
                    <td className="px-3 py-2.5 text-gray-400">{row.시장}</td>
                    <td className="px-3 py-2.5">
                      <SignalBadge signal={row.signal} />
                    </td>
                    <td className="px-3 py-2.5">
                      <ConfidenceBar value={row.confidence} />
                    </td>
                    <td className="px-3 py-2.5 text-gray-300">{row.ma_status || '—'}</td>
                    <td className="px-3 py-2.5 text-gray-300">{row.rsi_zone || '—'}</td>
                    <td className="px-3 py-2.5 text-gray-300">{row.volume_trend || '—'}</td>
                    <td className="px-3 py-2.5 max-w-xs">
                      <p className="text-gray-400 truncate">{row.reasons || '—'}</p>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Empty state ────────────────────────────────────────── */}
      {results.length === 0 && !isRunning && (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
            style={{ background: 'rgba(41,98,255,0.1)', border: '1px solid rgba(41,98,255,0.2)' }}>
            <i className="fa-solid fa-robot text-blue-400 text-2xl" />
          </div>
          <p className="text-gray-300 font-medium mb-1">분석 결과가 없습니다</p>
          <p className="text-gray-600 text-sm">위의 "분석 시작" 버튼을 눌러 Gemini 차트 분석을 실행하세요.</p>
        </div>
      )}

      {/* ── Chart modal ────────────────────────────────────────── */}
      {modal && <ChartModal result={modal} onClose={() => setModal(null)} />}
    </div>
  );
}
