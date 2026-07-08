'use client';

import { useState } from 'react';

/* ── types ───────────────────────────────────────────────────── */

interface SizeResult {
  method: string;
  shares: number;
  entry_price: number;
  stop_price: number;
  target_price: number;
  position_value: number;
  actual_risk: number;
  potential_profit: number;
  portfolio_risk_pct: number;
  position_pct: number;
  risk_reward_ratio: number;
  stop_distance_pct: number;
  risk_warning: boolean;
  kelly?: { b: number; full_kelly_pct: number; half_kelly_pct: number };
}

type Method = 'fixed' | 'atr' | 'kelly';

const METHOD_META: Record<Method, { label: string; icon: string; color: string; desc: string }> = {
  fixed: { label: 'Fixed Fractional', icon: 'fa-percent',    color: 'blue',   desc: '자본 대비 고정 % 리스크' },
  atr:   { label: 'ATR 기반',         icon: 'fa-chart-area', color: 'emerald', desc: '변동성(ATR) 기반 손절' },
  kelly: { label: 'Kelly Criterion',  icon: 'fa-calculator', color: 'amber',  desc: '승률/손익비 기반 최적 비율' },
};

function fmt(n: number) { return Math.round(n).toLocaleString(); }

/* ── page ───────────────────────────────────────────────────── */

export default function PositionSizerPage() {
  const [method, setMethod] = useState<Method>('fixed');
  const [result, setResult] = useState<SizeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState('');

  const [capital,      setCapital]      = useState('100000000');
  const [entryPrice,   setEntryPrice]   = useState('');
  const [stopPrice,    setStopPrice]    = useState('');
  const [targetPrice,  setTargetPrice]  = useState('');
  const [riskPct,      setRiskPct]      = useState('1');
  const [atr,          setAtr]          = useState('');
  const [atrMult,      setAtrMult]      = useState('2');
  const [winRate,      setWinRate]      = useState('55');
  const [avgWin,       setAvgWin]       = useState('9');
  const [avgLoss,      setAvgLoss]      = useState('5');

  const calculate = async () => {
    setError('');
    setLoading(true);
    try {
      const body: Record<string, any> = {
        method,
        capital:     parseFloat(capital) || 0,
        entry_price: parseFloat(entryPrice) || 0,
        stop_price:  parseFloat(stopPrice) || 0,
        risk_pct:    parseFloat(riskPct) || 1,
      };
      if (method === 'fixed' && targetPrice) body.target_price = parseFloat(targetPrice);
      if (method === 'atr')   { body.atr = parseFloat(atr) || 0; body.atr_multiplier = parseFloat(atrMult) || 2; }
      if (method === 'kelly') { body.win_rate = parseFloat(winRate) || 55; body.avg_win_pct = parseFloat(avgWin) || 9; body.avg_loss_pct = parseFloat(avgLoss) || 5; }

      const res = await fetch('/api/kr/position-size', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const json = await res.json();
      if (!res.ok) { setError(json.error || '계산 실패'); return; }
      setResult(json);
    } catch { setError('서버 연결 실패'); }
    finally { setLoading(false); }
  };

  const meta = METHOD_META[method];
  const colorMap: Record<string, string> = {
    blue:    'border-blue-500/50 text-blue-400 bg-blue-500/10',
    emerald: 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10',
    amber:   'border-amber-500/50 text-amber-400 bg-amber-500/10',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white">포지션 사이징</h1>
        <p className="text-gray-400 mt-1 text-sm">Fixed Fractional · ATR · Kelly Criterion</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── 입력 패널 ── */}
        <div className="space-y-4">
          {/* 방법 선택 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">계산 방식</p>
            <div className="grid grid-cols-3 gap-2">
              {(Object.keys(METHOD_META) as Method[]).map((m) => {
                const mt = METHOD_META[m];
                const active = method === m;
                return (
                  <button
                    key={m}
                    onClick={() => { setMethod(m); setResult(null); }}
                    className={`rounded-xl border p-3 text-left transition-all ${
                      active ? colorMap[mt.color] : 'border-white/10 text-gray-400 hover:border-white/20'
                    }`}
                  >
                    <i className={`fa-solid ${mt.icon} text-sm mb-1.5 block`} />
                    <p className="text-xs font-semibold">{mt.label}</p>
                    <p className="text-[10px] text-gray-500 mt-0.5">{mt.desc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 공통 입력 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5 space-y-3">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">기본 설정</p>
            <label className="block">
              <span className="text-xs text-gray-500 mb-1 block">총 자본금 (₩)</span>
              <input type="number" value={capital} onChange={e => setCapital(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30" />
            </label>
            <label className="block">
              <span className="text-xs text-gray-500 mb-1 block">진입가 (₩)</span>
              <input type="number" value={entryPrice} onChange={e => setEntryPrice(e.target.value)} placeholder="예: 50000"
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30" />
            </label>
            {method !== 'kelly' && (
              <label className="block">
                <span className="text-xs text-gray-500 mb-1 block">리스크 비율 (%)</span>
                <input type="number" value={riskPct} onChange={e => setRiskPct(e.target.value)} step="0.1"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30" />
              </label>
            )}
          </div>

          {/* 방식별 추가 입력 */}
          <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5 space-y-3">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{meta.label} 설정</p>

            {method === 'fixed' && (
              <>
                <label className="block">
                  <span className="text-xs text-gray-500 mb-1 block">손절가 (₩)</span>
                  <input type="number" value={stopPrice} onChange={e => setStopPrice(e.target.value)} placeholder="비워두면 진입가 ×0.95"
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30" />
                </label>
                <label className="block">
                  <span className="text-xs text-gray-500 mb-1 block">목표가 (₩)</span>
                  <input type="number" value={targetPrice} onChange={e => setTargetPrice(e.target.value)} placeholder="비워두면 진입가 ×1.15"
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30" />
                </label>
              </>
            )}

            {method === 'atr' && (
              <>
                <label className="block">
                  <span className="text-xs text-gray-500 mb-1 block">ATR (14일 평균 진폭)</span>
                  <input type="number" value={atr} onChange={e => setAtr(e.target.value)} placeholder="예: 2500"
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30" />
                </label>
                <label className="block">
                  <span className="text-xs text-gray-500 mb-1 block">ATR 배수 (손절 거리)</span>
                  <input type="number" value={atrMult} onChange={e => setAtrMult(e.target.value)} step="0.5"
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30" />
                </label>
              </>
            )}

            {method === 'kelly' && (
              <>
                <label className="block">
                  <span className="text-xs text-gray-500 mb-1 block">승률 (%)</span>
                  <input type="number" value={winRate} onChange={e => setWinRate(e.target.value)} step="1"
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30" />
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block">
                    <span className="text-xs text-gray-500 mb-1 block">평균 수익 (%)</span>
                    <input type="number" value={avgWin} onChange={e => setAvgWin(e.target.value)} step="0.5"
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30" />
                  </label>
                  <label className="block">
                    <span className="text-xs text-gray-500 mb-1 block">평균 손실 (%)</span>
                    <input type="number" value={avgLoss} onChange={e => setAvgLoss(e.target.value)} step="0.5"
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30" />
                  </label>
                </div>
              </>
            )}
          </div>

          <button
            onClick={calculate}
            disabled={loading}
            className="w-full py-3 rounded-xl bg-blue-500 hover:bg-blue-400 disabled:opacity-50 text-white font-semibold transition-colors"
          >
            {loading ? <><i className="fa-solid fa-spinner fa-spin mr-2" />계산 중...</> : '계산하기'}
          </button>
          {error && <p className="text-red-400 text-sm text-center">{error}</p>}
        </div>

        {/* ── 결과 패널 ── */}
        <div className="space-y-4">
          {!result ? (
            <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-14 flex flex-col items-center text-center">
              <i className="fa-solid fa-calculator text-gray-700 text-5xl mb-4" />
              <p className="text-gray-400 font-medium">좌측에서 값을 입력하고 계산하세요</p>
            </div>
          ) : (
            <>
              {/* 핵심 지표 */}
              <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-white font-semibold">계산 결과</p>
                  {result.risk_warning && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-400">
                      <i className="fa-solid fa-triangle-exclamation mr-1" />리스크 2% 초과
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: '매수 수량',    value: `${result.shares.toLocaleString()}주`,      color: 'text-blue-400' },
                    { label: '포지션 금액',  value: `₩${fmt(result.position_value)}`,           color: 'text-white' },
                    { label: '실제 리스크',  value: `₩${fmt(result.actual_risk)}`,              color: 'text-red-400' },
                    { label: '예상 수익',    value: `₩${fmt(result.potential_profit)}`,          color: 'text-green-400' },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="bg-white/5 rounded-xl p-3">
                      <p className="text-xs text-gray-500 mb-1">{label}</p>
                      <p className={`text-lg font-bold ${color}`}>{value}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* 상세 지표 */}
              <div className="bg-[#1a1f2e] border border-white/10 rounded-2xl p-5">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">상세 지표</p>
                <div className="space-y-2.5">
                  {[
                    { label: '진입가',        value: `₩${fmt(result.entry_price)}` },
                    { label: '손절가',        value: `₩${fmt(result.stop_price)} (−${result.stop_distance_pct}%)` },
                    { label: '목표가',        value: `₩${fmt(result.target_price)}` },
                    { label: '손익비',        value: `1 : ${result.risk_reward_ratio}` },
                    { label: '자본 대비 비중', value: `${result.position_pct}%` },
                    { label: '포트폴리오 리스크', value: `${result.portfolio_risk_pct}%`, warn: result.risk_warning },
                  ].map(({ label, value, warn }) => (
                    <div key={label} className="flex items-center justify-between py-1.5 border-b border-white/5 last:border-0">
                      <span className="text-sm text-gray-400">{label}</span>
                      <span className={`text-sm font-medium ${warn ? 'text-red-400' : 'text-white'}`}>{value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Kelly 상세 */}
              {result.kelly && (
                <div className="bg-[#1a1f2e] border border-amber-500/20 rounded-2xl p-5">
                  <p className="text-xs text-amber-400 uppercase tracking-wider mb-3">Kelly 계산 내역</p>
                  <div className="space-y-2">
                    {[
                      { label: '수익/손실 비율 (b)', value: result.kelly.b },
                      { label: 'Full Kelly (%)',      value: `${result.kelly.full_kelly_pct}%` },
                      { label: 'Half Kelly (%)',      value: `${result.kelly.half_kelly_pct}%` },
                    ].map(({ label, value }) => (
                      <div key={label} className="flex justify-between text-sm py-1 border-b border-white/5 last:border-0">
                        <span className="text-gray-400">{label}</span>
                        <span className="text-amber-400 font-medium">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 원칙 */}
              <div className="bg-white/3 border border-white/5 rounded-2xl p-4">
                <p className="text-xs text-gray-600 leading-relaxed">
                  <i className="fa-solid fa-lightbulb text-amber-700 mr-1.5" />
                  포지션 사이징은 수익을 최대화하는 것이 아니라 <span className="text-gray-500">연패 구간을 버티는 것</span>입니다.
                  총 오픈 리스크가 자본의 6-8%를 초과하지 않도록 관리하세요.
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
