'use client';

import { useEffect, useRef, useState, memo } from 'react';

interface PricePoint {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

interface StockChartProps {
    ticker: string;
    marketType?: 'KR' | 'US';
    height?: number;
    onReady?: () => void;
}

const StockChart = memo(function StockChart({
    ticker,
    marketType = 'KR',
    height = 400,
    onReady,
}: StockChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<any>(null);
    const [status, setStatus] = useState<'loading' | 'ready' | 'empty'>('loading');

    useEffect(() => {
        if (!containerRef.current) return;
        let cancelled = false;

        const init = async () => {
            // 모달 레이아웃이 완료된 후 실행
            await new Promise<void>((r) => requestAnimationFrame(() => r()));
            if (cancelled || !containerRef.current) return;

            const w = containerRef.current.clientWidth || 640;
            const h = containerRef.current.clientHeight || height;

            let priceHistory: PricePoint[] = [];
            try {
                const endpoint = marketType === 'US'
                    ? `/api/us/chart-analysis/stock-summary/${ticker}`
                    : `/api/kr/stock-summary/${ticker}`;

                const res = await fetch(endpoint);
                if (!res.ok) throw new Error(`${res.status}`);
                const json = await res.json();
                priceHistory = json.price_history ?? [];
            } catch { /* no-op */ }

            if (cancelled || !containerRef.current) return;

            const lc = await import('lightweight-charts');
            if (cancelled || !containerRef.current) return;

            const chart = (() => {
                try {
                    return (lc as any).createChart(containerRef.current!, {
                        width: w,
                        height: h,
                        layout: { background: { color: '#1c1c1e' } as any, textColor: '#9ca3af' },
                        grid: {
                            vertLines: { color: 'rgba(255,255,255,0.03)' },
                            horzLines: { color: 'rgba(255,255,255,0.03)' },
                        },
                        rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)' },
                        timeScale: { borderColor: 'rgba(255,255,255,0.1)', timeVisible: false },
                        localization: {
                            priceFormatter: (price: number) =>
                                price.toLocaleString(marketType === 'KR' ? 'ko-KR' : 'en-US', {
                                    minimumFractionDigits: marketType === 'KR' ? 0 : 2,
                                    maximumFractionDigits: marketType === 'KR' ? 0 : 2
                                }),
                        },
                    });
                } catch { return null; }
            })();
            if (!chart || cancelled) return;
            chartRef.current = chart;

            const hasOHLC = priceHistory.length > 0 && priceHistory[0].open != null;

            if (priceHistory.length > 0) {
                if (hasOHLC) {
                    const candleOpts = {
                        upColor: '#f43f5e', downColor: '#3b82f6',
                        borderUpColor: '#f43f5e', borderDownColor: '#3b82f6',
                        wickUpColor: '#f43f5e', wickDownColor: '#3b82f6',
                        priceFormat: {
                            type: 'price' as const,
                            precision: marketType === 'KR' ? 0 : 2,
                            minMove: marketType === 'KR' ? 1 : 0.01
                        },
                    };
                    let candle: any;
                    try { candle = (chart as any).addSeries((lc as any).CandlestickSeries, candleOpts); }
                    catch { candle = (chart as any).addCandlestickSeries(candleOpts); }
                    candle.setData(priceHistory.map((p: any) => ({
                        time: p.date, open: p.open, high: p.high, low: p.low, close: p.close,
                    })));

                    // --- Moving Averages (20, 60, 120) ---
                    const calcSMA = (period: number) => {
                        const data = [];
                        for (let i = period - 1; i < priceHistory.length; i++) {
                            let sum = 0;
                            for (let j = 0; j < period; j++) sum += priceHistory[i - j].close;
                            data.push({ time: priceHistory[i].date, value: sum / period });
                        }
                        return data;
                    };

                    const lineOptTemplate = { lineWidth: 1.2, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false };

                    let line20: any;
                    try { line20 = (chart as any).addSeries((lc as any).LineSeries, { ...lineOptTemplate, color: '#22d3ee' }); }
                    catch { line20 = (chart as any).addLineSeries({ ...lineOptTemplate, color: '#22d3ee' }); }
                    line20.setData(calcSMA(20));

                    let line60: any;
                    try { line60 = (chart as any).addSeries((lc as any).LineSeries, { ...lineOptTemplate, color: '#fb923c' }); }
                    catch { line60 = (chart as any).addLineSeries({ ...lineOptTemplate, color: '#fb923c' }); }
                    line60.setData(calcSMA(60));

                    let line120: any;
                    try { line120 = (chart as any).addSeries((lc as any).LineSeries, { ...lineOptTemplate, color: '#f87171' }); }
                    catch { line120 = (chart as any).addLineSeries({ ...lineOptTemplate, color: '#f87171' }); }
                    line120.setData(calcSMA(120));

                    // 거래량
                    if (priceHistory[0].volume != null) {
                        const volOpts = { priceFormat: { type: 'volume' as const }, priceScaleId: 'vol' };
                        let vol: any;
                        try { vol = (chart as any).addSeries((lc as any).HistogramSeries, volOpts); }
                        catch { vol = (chart as any).addHistogramSeries(volOpts); }
                        (chart as any).priceScale('vol').applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });
                        vol.setData(priceHistory.map((p: any) => ({
                            time: p.date,
                            value: p.volume,
                            color: p.close >= p.open ? 'rgba(244,63,94,0.4)' : 'rgba(59,130,246,0.4)',
                        })));
                    }
                } else {
                    const seriesOpts = {
                        color: '#f43f5e', lineWidth: 2 as const,
                        priceFormat: { type: 'price' as const, precision: 0, minMove: 1 },
                    };
                    let line: any;
                    try { line = (chart as any).addSeries((lc as any).LineSeries, seriesOpts); }
                    catch { line = (chart as any).addLineSeries(seriesOpts); }
                    line.setData(priceHistory.map((p: any) => ({ time: p.date, value: Number(p.close) })));
                }

                requestAnimationFrame(() => {
                    if (cancelled) return;
                    (chart as any).timeScale().fitContent();
                    const lr = (chart as any).timeScale().getVisibleLogicalRange();
                    const defaultRange = marketType === 'KR' ? 252 : 120;
                    if (lr && (lr.to - lr.from) > defaultRange) {
                        (chart as any).timeScale().setVisibleLogicalRange({ from: lr.to - defaultRange, to: lr.to });
                    }
                    setStatus('ready');
                    onReady?.();
                });
            } else {
                setStatus('empty');
            }
        };

        init();
        return () => {
            cancelled = true;
            if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }
        };
    }, [ticker, marketType, height, onReady]);

    return (
        <div className="relative w-full h-full min-h-[300px]">
            <div ref={containerRef} className="w-full h-full rounded-lg overflow-hidden" />
            {status === 'loading' && (
                <div className="absolute inset-0 flex items-center justify-center bg-[#1a1f2e] rounded-lg">
                    <div className="text-gray-500 text-sm flex items-center gap-2">
                        <i className="fa-solid fa-circle-notch animate-spin" />
                        차트 로딩 중...
                    </div>
                </div>
            )}
            {status === 'empty' && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#1a1f2e] rounded-lg">
                    <i className="fa-solid fa-chart-area text-gray-600 text-4xl mb-3" />
                    <p className="text-gray-400 text-sm font-medium">차트 데이터 없음</p>
                </div>
            )}
        </div>
    );
});

export default StockChart;
