'use client';

import { useEffect, useRef, useState } from 'react';

interface DateFilterProps {
  dates: string[];                    // YYYYMMDD 형식
  selected: string | null;            // null = 최신
  onChange: (date: string | null) => void;
  loading?: boolean;
  counts?: Record<string, number>;    // date → 시그널 수
}

function fmtDate(d: string): string {
  return `${parseInt(d.slice(4, 6))}/${parseInt(d.slice(6, 8))}`;
}

export default function DateFilter({ dates, selected, onChange, loading, counts }: DateFilterProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  if (dates.length === 0) return null;

  const hasData = (d: string) => !counts || (counts[d] ?? 0) > 0;
  const selectedLabel = selected ? fmtDate(selected) : '최신';

  return (
    <div className="relative" ref={ref}>
      {/* 드롭다운 버튼 */}
      <button
        onClick={() => !loading && setOpen((v) => !v)}
        disabled={loading}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white hover:bg-white/10 transition-colors disabled:opacity-50"
      >
        <i className="fa-regular fa-calendar text-gray-400 text-xs" />
        <span className={selected ? 'text-rose-400' : 'text-white'}>{selectedLabel}</span>
        <i className={`fa-solid fa-chevron-down text-gray-500 text-[10px] transition-transform duration-150 ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* 드롭다운 패널 */}
      {open && (
        <div className="absolute top-full mt-1.5 left-0 z-50 bg-[#1e2635] border border-white/10 rounded-xl shadow-2xl overflow-hidden min-w-[110px] py-1">
          {/* 최신 */}
          <button
            onClick={() => { onChange(null); setOpen(false); }}
            className={`w-full text-left px-4 py-2 text-sm transition-colors flex items-center justify-between ${
              selected === null
                ? 'bg-rose-500/20 text-rose-400'
                : 'text-white hover:bg-white/10'
            }`}
          >
            <span>최신</span>
            {selected === null && <i className="fa-solid fa-check text-[10px]" />}
          </button>

          <div className="mx-3 my-1 border-t border-white/10" />

          {/* 날짜 목록 */}
          {dates.map((d) => {
            const active  = selected === d;
            const hasItem = hasData(d);
            const cnt     = counts?.[d] ?? null;
            return (
              <button
                key={d}
                onClick={() => { onChange(d); setOpen(false); }}
                className={`w-full text-left px-4 py-2 text-sm transition-colors flex items-center justify-between gap-3 ${
                  active
                    ? 'bg-rose-500/20 text-rose-400'
                    : hasItem
                    ? 'text-white hover:bg-white/10'
                    : 'text-gray-600 hover:bg-white/5'
                }`}
              >
                <span>{fmtDate(d)}</span>
                {cnt !== null && (
                  <span className={`text-[10px] tabular-nums ${
                    active ? 'text-rose-400/70' : hasItem ? 'text-gray-500' : 'text-gray-700'
                  }`}>
                    {cnt}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
