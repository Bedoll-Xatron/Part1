'use client';

import { useEffect, useState } from 'react';

interface FreshnessIndicatorProps {
  lastUpdated: Date | null;
}

export default function FreshnessIndicator({ lastUpdated }: FreshnessIndicatorProps) {
  const [, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 3_000);
    return () => clearInterval(id);
  }, []);

  if (!lastUpdated) {
    return <span className="text-xs text-gray-500">업데이트 대기 중</span>;
  }

  const seconds = Math.floor((Date.now() - lastUpdated.getTime()) / 1000);
  const label = seconds < 60 ? `${seconds}초 전` : `${Math.floor(seconds / 60)}분 전`;

  return <span className="text-xs text-gray-500">{label}</span>;
}
