'use client';

import Link from 'next/link';
import { useState } from 'react';
import { usePathname } from 'next/navigation';

/* ── nav structure ───────────────────────────────────────────── */

interface NavItem {
  name: string;
  href: string;
  icon: string;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

const sections: NavSection[] = [
  {
    label: '시장 분석',
    items: [
      { name: 'Overview', href: '/dashboard/kr', icon: 'fa-table-cells-large' },
      { name: '시장 고점 탐지', href: '/dashboard/kr/market-health', icon: 'fa-gauge-high' },
      { name: 'FTD 탐지', href: '/dashboard/kr/ftd', icon: 'fa-flag-checkered' },
      { name: '시장 폭 분석', href: '/dashboard/kr/breadth', icon: 'fa-wave-square' },
    ],
  },
  {
    label: '종목 발굴',
    items: [
      { name: 'Best of Best', href: '/dashboard/kr/best', icon: 'fa-trophy' },
      { name: '장중 원석', href: '/dashboard/kr/intraday-gems', icon: 'fa-gem' },
      { name: 'VCP Signals', href: '/dashboard/kr/vcp', icon: 'fa-crosshairs' },
      { name: 'VCP 누적 성과', href: '/dashboard/kr/vcp/history', icon: 'fa-chart-area' },
      { name: '종가베팅', href: '/dashboard/kr/closing-bet', icon: 'fa-clock' },
      { name: '종가베팅 누적', href: '/dashboard/kr/closing-bet/history', icon: 'fa-chart-column' },
      { name: '수급 모멘텀', href: '/dashboard/kr/flow-momentum', icon: 'fa-water' },
      { name: '테마 모멘텀', href: '/dashboard/kr/narrative-momentum', icon: 'fa-fire' },
      { name: '섹터 로테이션', href: '/dashboard/kr/sector-rotation', icon: 'fa-arrows-rotate' },
      { name: '역발상', href: '/dashboard/kr/contrarian', icon: 'fa-rotate-left' },
      { name: '갭 드리프트', href: '/dashboard/kr/pead', icon: 'fa-bolt-lightning' },
    ],
  },
  {
    label: '성과 추적',
    items: [
      { name: '시그널 사후분석', href: '/dashboard/kr/postmortem', icon: 'fa-microscope' },
      { name: 'Backtest Expert', href: '/dashboard/kr/backtest-detail', icon: 'fa-flask' },
    ],
  },
  {
    label: 'AI 차트 분석',
    items: [
      { name: '미국(US) 차트 스캔', href: '/dashboard/us/chart-scan', icon: 'fa-earth-americas' },
      { name: '한국(KR) 차트 스캔', href: '/dashboard/kr/chart-scan', icon: 'fa-robot' },
    ],
  },
  {
    label: '매매 실행',
    items: [
      { name: '포지션 사이징', href: '/dashboard/kr/position-sizer', icon: 'fa-calculator' },
      { name: '종목 검색', href: '/dashboard/kr/search', icon: 'fa-magnifying-glass' },
    ],
  },
];

/* ── component ───────────────────────────────────────────────── */

export default function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) => pathname === href;

  return (
    <aside
      style={{ background: '#131722', borderRight: '1px solid rgba(42,52,71,0.7)' }}
      className="w-56 h-screen flex-shrink-0 flex flex-col overflow-hidden"
    >
      {/* ── Logo ─────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-2.5 px-5 h-14 flex-shrink-0"
        style={{ borderBottom: '1px solid rgba(42,52,71,0.7)' }}
      >
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: 'linear-gradient(135deg,#2962ff 0%,#00bcd4 100%)' }}
        >
          <i className="fa-solid fa-chart-line text-white text-xs" />
        </div>
        <div>
          <span className="text-sm font-bold text-white tracking-tight">MarketFlow</span>
          <span
            className="block text-[9px] font-medium tracking-widest uppercase"
            style={{ color: '#2962ff' }}
          >
            KR Alpha
          </span>
        </div>
      </div>

      {/* ── Nav ──────────────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto py-3 space-y-5 px-2">
        {sections.map((section) => (
          <div key={section.label}>
            {/* Section header */}
            <p
              className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest select-none"
              style={{ color: '#4a5568' }}
            >
              {section.label}
            </p>

            {/* Items */}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    style={
                      active
                        ? {
                          borderLeft: '2px solid #2962ff',
                          background: 'rgba(41,98,255,0.1)',
                          color: '#ffffff',
                        }
                        : {
                          borderLeft: '2px solid transparent',
                          color: '#787b86',
                        }
                    }
                    className={`flex items-center gap-2.5 pl-3 pr-3 py-1.5 rounded-r-md text-xs font-medium
                      transition-all duration-100
                      ${active ? '' : 'hover:bg-white/5 hover:text-[#d1d4dc]'}`}
                  >
                    <i
                      className={`fa-solid ${item.icon} w-3.5 text-center text-[11px] flex-shrink-0`}
                      style={{ color: active ? '#2962ff' : 'currentColor' }}
                    />
                    <span className="truncate">{item.name}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* ── Footer ───────────────────────────────────────────── */}
      <div
        className="px-5 py-3 flex-shrink-0"
        style={{ borderTop: '1px solid rgba(42,52,71,0.7)', color: '#4a5568' }}
      >
        <p className="text-[10px]">KR Market · Real-time</p>
      </div>
    </aside>
  );
}
