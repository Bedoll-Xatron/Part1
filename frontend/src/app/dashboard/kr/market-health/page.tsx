'use client';

import { useEffect, useState } from 'react';

/* ── types ───────────────────────────────────────────────────── */

interface Component {
  label: string;
  score: number;
  weight: number;
  detail: string;
  count?: number;
  below_pct?: number;
  spread?: number;
  def_avg?: number;
  off_avg?: number;
  contrarian_count?: number;
}

interface MarketTopData {
  score: number;
  risk_level: 'green' | 'yellow' | 'orange' | 'red' | 'critical';
  risk_label: string;
  components: Record<string, Component>;
  updated_at: string;
}

/* ── constants ───────────────────────────────────────────────── */

const RISK_META = {
  green:    { label: '정상',        color: 'text-green-400',  bg: 'bg-green-400',  border: 'border-green-500/30',  ring: 'ring-green-500/40'  },
  yellow:   { label: '조기 경고',   color: 'text-yellow-400', bg: 'bg-yellow-400', border: 'border-yellow-500/30', ring: 'ring-yellow-500/40' },
  orange:   { label: '위험 상승',   color: 'text-orange-400', bg: 'bg-orange-400', border: 'border-orange-500/30', ring: 'ring-orange-500/40' },
  red:      { label: '고점 위험',   color: 'text-red-400',    bg: 'bg-red-400',    border: 'border-red-500/30',    ring: 'ring-red-500/40'    },
  critical: { label: '고점 형성',   color: 'text-rose-400',   bg: 'bg-rose-400',   border: 'border-rose-500/30',   ring: 'ring-rose-500/40'   },
};

const COMP_ORDER = [
  'distribution_days', 'leading_deterioration', 'defensive_rotation',
  'market_breadth', 'index_technical', 'sentiment',
];

const COMP_ICONS: Record<string, string> = {
  distribution_days:     'fa-cloud-rain',
  leading_deterioration: 'fa-chart-line',
  defensive_rotation:    'fa-shield',
  market_breadth:        'fa-wave-square',
  index_technical:       'fa-chart-bar',
  sentiment:             'fa-brain',
};

/* ── ScoreGauge ──────────────────────────────────────────────── */

function ScoreGauge({ score, level }: { score: number; level: keyof typeof RISK_META }) {
  const meta  = RISK_META[level];
  const pct   = score;                          // 0~100
  const angle = (pct / 100) * 180 - 90;        // -90 ~ +90 deg

  return (
    <div className="flex flex-col items-center gap-3">
      {/* 반원 게이지 */}
      <div className="relative w-48 h-24 overflow-hidden">
        <svg viewBox="0 0 200 100" className="absolute inset-0 w-full h-full">
          {/* 배경 호 */}
          <path d="M10,100 A90,90 0 0,1 190,100" fill="none" stroke="#2a2a2e" strokeWidth="16" strokeLinecap="round" />
          {/* 점수 호 */}
          <path d="M10,100 A90,90 0 0,1 190,100" fill="none" strokeWidth="16" strokeLinecap="round"
            stroke="url(#gaugeFill)"
            strokeDasharray={`${pct * 2.827} ${282.7 - pct * 2.827}`} />
          <defs>
            <linearGradient id="gaugeFill" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%"   stopColor="#22c55e" />
              <stop offset="40%"  stopColor="#eab308" />
              <stop offset="70%"  stopColor="#f97316" />
              <stop offset="100%" stopColor="#ef4444" />
            </linearGradient>
          </defs>
          {/* 바늘 */}
          <line
            x1="100" y1="100"
            x2={100 + 70 * Math.cos((angle - 90) * Math.PI / 180)}
            y2={100 + 70 * Math.sin((angle - 90) * Math.PI / 180)}
            stroke="white" strokeWidth="2.5" strokeLinecap="round"
          />
          <circle cx="100" cy="100" r="5" fill="white" />
          {/* 눈금 라벨 */}
          {[0, 25, 50, 75, 100].map((v, i) => {
            const a  = (v / 100 * 180 - 90) * Math.PI / 180;
            const lx = 100 + 78 * Math.cos(a - Math.PI / 2);
            const ly = 100 + 78 * Math.sin(a - Math.PI / 2);
            return <text key={v} x={lx} y={ly} textAnchor="middle" dominantBaseline="middle"
              fontSize="8" fill="#4b5563">{v}</text>;
          })}
        </svg>
      </div>
      <div className="text-center">
        <p className={`text-5xl font-black ${meta.color}`}>{score}</p>
        <p className="text-gray-500 text-xs mt-0.5">/ 100</p>
        <p className={`text-sm font-semibold mt-2 ${meta.color}`}>{RISK_META[level].label}</p>
      </div>
    </div>
  );
}

/* ── ComponentCard ───────────────────────────────────────────── */

function ComponentCard({ compKey, data }: { compKey: string; data: Component }) {
  const pct      = Math.round((data.score / data.weight) * 100);
  const barColor = pct >= 80 ? 'bg-red-400' : pct >= 50 ? 'bg-orange-400' : pct >= 25 ? 'bg-yellow-400' : 'bg-green-400';
  return (
    <div className="bg-[#1a1f2e] border border-white/10 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <i className={`fa-solid ${COMP_ICONS[compKey] ?? 'fa-circle'} text-gray-400 text-sm`} />
          <span className="text-sm text-white font-medium">{data.label}</span>
        </div>
        <span className="text-sm font-bold text-white">{data.score}<span className="text-gray-600 text-xs">/{data.weight}</span></span>
      </div>
      <div className="h-1.5 bg-white/10 rounded-full mb-2.5">
        <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-[11px] text-gray-500">{data.detail}</p>
    </div>
  );
}

/* ── page ────────────────────────────────────────────────────── */

export default function MarketHealthPage() {
  const [data,    setData]    = useState<MarketTopData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  useEffect(() => {
    fetch('/api/kr/market-top')
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const level    = (data?.risk_level ?? 'green') as keyof typeof RISK_META;
  const meta     = RISK_META[level];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">시장 고점 탐지</h1>
          <p className="text-gray-400 mt-1 text-sm">KR 시장 복합 위험도 지표 (0~100)</p>
        </div>
        {data && (
          <span className="text-xs text-gray-600">업데이트 {data.updated_at}</span>
        )}
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20 text-gray-500 gap-2">
          <i className="fa-solid fa-spinner fa-spin" /><span>분석 중...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm">
          <i className="fa-solid fa-triangle-exclamation mr-2" />{error}
        </div>
      )}

      {data && (
        <>
          {/* 종합 스코어 카드 */}
          <div className={`bg-[#1a1f2e] border ${meta.border} rounded-2xl p-6`}>
            <div className="flex flex-col md:flex-row items-center gap-8">
              <ScoreGauge score={data.score} level={level} />
              <div className="flex-1 space-y-4">
                <div>
                  <p className={`text-2xl font-bold ${meta.color}`}>{data.risk_label}</p>
                  <p className="text-gray-400 text-sm mt-1">6개 지표 복합 분석 결과</p>
                </div>
                {/* 리스크 구간 */}
                <div className="space-y-1.5">
                  {([
                    ['green',    '0~20',   '정상 (매수 우호)'],
                    ['yellow',   '21~40',  '조기 경고'],
                    ['orange',   '41~60',  '위험 상승'],
                    ['red',      '61~80',  '고점 가능성 높음'],
                    ['critical', '81~100', '고점 형성 중'],
                  ] as const).map(([lvl, range, desc]) => (
                    <div key={lvl} className={`flex items-center gap-2 text-xs ${level === lvl ? 'opacity-100' : 'opacity-30'}`}>
                      <div className={`w-2 h-2 rounded-full ${RISK_META[lvl].bg}`} />
                      <span className="text-gray-500 w-14">{range}</span>
                      <span className={RISK_META[lvl].color}>{desc}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* 6개 컴포넌트 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {COMP_ORDER.map(key =>
              data.components[key] ? (
                <ComponentCard key={key} compKey={key} data={data.components[key]} />
              ) : null
            )}
          </div>

          {/* 투자 유의 */}
          <div className="bg-white/3 border border-white/5 rounded-xl p-4">
            <p className="text-xs text-gray-600 leading-relaxed">
              <i className="fa-solid fa-circle-info text-gray-700 mr-1.5" />
              이 지표는 2~8주 단기 전술적 타이밍 신호이며, 10~20% 조정에 선행할 가능성을 나타냅니다.
              Distribution Days 기준은 KOSPI 기준 거래량 증가 + 0.2% 이상 하락일입니다.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
