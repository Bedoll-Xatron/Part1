'use client';

import { useEffect, useMemo, useState } from 'react';

type PriceEntry = {
  price: number;
  change_pct: number;
  volume: number;
  updated_at: string;
};

type PricesMap = Record<string, PriceEntry>;

export function usePriceStream(tickers: string[]) {
  const [prices, setPrices] = useState<PricesMap>({});
  const [connected, setConnected] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const tickerKey = tickers.join(',');

  useEffect(() => {
    if (tickers.length === 0) return;

    let closed = false;
    let fallbackInterval: ReturnType<typeof setInterval> | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

    const startFallback = () => {
      if (fallbackInterval) return;
      fallbackInterval = setInterval(async () => {
        if (closed) return;
        try {
          const res = await fetch('/api/kr/realtime-prices', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tickers }),
          });
          const data = await res.json();
          if (data.prices) {
            setPrices((prev) => ({ ...prev, ...data.prices }));
            setLastUpdated(new Date());
          }
        } catch {
          // silent
        }
      }, 30_000);
    };

    let activeEs: EventSource | null = null;

    const connect = () => {
      if (closed) return;

      const es = new EventSource(`/api/kr/price-stream?tickers=${tickerKey}`);
      activeEs = es;

      es.onopen = () => {
        if (!closed) setConnected(true);
      };

      es.onmessage = (e) => {
        if (closed) return;
        try {
          const data = JSON.parse(e.data);
          if (data.prices) {
            setPrices((prev) => ({ ...prev, ...data.prices }));
            setLastUpdated(new Date());
          }
        } catch {
          // silent
        }
      };

      es.onerror = () => {
        es.close();
        activeEs = null;
        if (closed) return;
        setConnected(false);
        startFallback();
        reconnectTimeout = setTimeout(connect, 5_000);
      };
    };

    connect();

    return () => {
      closed = true;
      setConnected(false);
      if (activeEs) { activeEs.close(); activeEs = null; }
      if (fallbackInterval) clearInterval(fallbackInterval);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [tickerKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredPrices = useMemo(() => {
    const result: PricesMap = {};
    for (const ticker of tickers) {
      const key = ticker.toUpperCase();
      if (prices[key]) result[key] = prices[key];
    }
    return result;
  }, [prices, tickerKey]); // eslint-disable-line react-hooks/exhaustive-deps

  return { prices: filteredPrices, connected, lastUpdated };
}
