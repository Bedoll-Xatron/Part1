import Sidebar from '@/components/layout/Sidebar';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
      />
      <div
        className="flex h-screen w-full overflow-hidden"
        style={{ background: '#0d1117' }}
      >
        <Sidebar />

        {/* ── Main ─────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col h-full overflow-hidden">

          {/* Top bar */}
          <header
            className="flex-shrink-0 flex items-center justify-between px-6 h-14"
            style={{
              background: '#131722',
              borderBottom: '1px solid rgba(42,52,71,0.7)',
            }}
          >
            <div className="flex items-center gap-2" style={{ color: '#787b86' }}>
              <i className="fa-solid fa-chart-line text-xs" />
              <span className="text-xs font-medium">KR Market Alpha</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <span
                  className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"
                />
                <span className="text-[11px]" style={{ color: '#787b86' }}>실시간</span>
              </div>
              <span className="text-[11px]" style={{ color: '#4a5568' }}>
                KOSPI · KOSDAQ
              </span>
            </div>
          </header>

          {/* Content */}
          <main
            className="flex-1 overflow-y-auto p-6"
            style={{ background: '#0d1117' }}
          >
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
