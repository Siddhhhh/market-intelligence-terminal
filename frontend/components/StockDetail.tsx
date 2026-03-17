"use client";

import { useEffect, useState } from "react";

interface StockMetrics {
  ticker: string;
  name: string;
  close: number;
  pct_change: number;
  high_52w: number;
  low_52w: number;
  avg_volume: number;
  ytd_return: number | null;
}

interface Props {
  ticker: string;
}

export default function StockDetail({ ticker }: Props) {
  const [metrics, setMetrics] = useState<StockMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);

    // Fetch last year of data to calculate metrics
    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    const startDate = oneYearAgo.toISOString().split("T")[0];

    fetch(`http://localhost:8000/api/stocks/${ticker}?start_date=${startDate}&limit=300`)
      .then((r) => r.json())
      .then((res) => {
        if (!res.data || res.data.length === 0) {
          setLoading(false);
          return;
        }

        const prices = res.data;
        const latest = prices[0]; // sorted DESC
        const oldest = prices[prices.length - 1];

        const highs = prices.map((p: any) => p.high).filter(Boolean);
        const lows = prices.map((p: any) => p.low).filter(Boolean);
        const volumes = prices.map((p: any) => p.volume).filter(Boolean);

        const ytdStart = prices.find((p: any) => p.date.startsWith(`${new Date().getFullYear()}-01`));
        const ytdReturn = ytdStart
          ? ((latest.close - ytdStart.close) / ytdStart.close) * 100
          : ((latest.close - oldest.close) / oldest.close) * 100;

        setMetrics({
          ticker: res.ticker,
          name: res.company_name,
          close: latest.close,
          pct_change: latest.pct_change || 0,
          high_52w: Math.max(...highs),
          low_52w: Math.min(...lows),
          avg_volume: Math.round(volumes.reduce((a: number, b: number) => a + b, 0) / volumes.length),
          ytd_return: Math.round(ytdReturn * 100) / 100,
        });
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [ticker]);

  if (loading) {
    return (
      <div className="grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="shimmer h-16 rounded-lg" />
        ))}
      </div>
    );
  }

  if (!metrics) return null;

  const items = [
    {
      label: "52W High",
      value: `$${metrics.high_52w.toFixed(2)}`,
      sub: metrics.close >= metrics.high_52w * 0.95 ? "Near high" : null,
      subColor: "text-terminal-green",
    },
    {
      label: "52W Low",
      value: `$${metrics.low_52w.toFixed(2)}`,
      sub: metrics.close <= metrics.low_52w * 1.05 ? "Near low" : null,
      subColor: "text-terminal-red",
    },
    {
      label: "Avg Volume",
      value: metrics.avg_volume > 1000000
        ? `${(metrics.avg_volume / 1000000).toFixed(1)}M`
        : `${(metrics.avg_volume / 1000).toFixed(0)}K`,
      sub: null,
      subColor: "",
    },
    {
      label: "YTD Return",
      value: `${metrics.ytd_return !== null ? (metrics.ytd_return >= 0 ? "+" : "") + metrics.ytd_return.toFixed(1) + "%" : "N/A"}`,
      sub: null,
      subColor: "",
      valueColor: metrics.ytd_return !== null
        ? metrics.ytd_return >= 0 ? "text-terminal-green" : "text-terminal-red"
        : "text-terminal-dim",
    },
  ];

  return (
    <div className="grid grid-cols-4 gap-2">
      {items.map((item) => (
        <div
          key={item.label}
          className="bg-terminal-surface/60 border border-terminal-border/50 rounded-lg px-3 py-2"
        >
          <div className="text-[10px] text-terminal-muted uppercase tracking-wider">
            {item.label}
          </div>
          <div className={`font-mono text-sm font-bold mt-0.5 ${(item as any).valueColor || "text-terminal-text"}`}>
            {item.value}
          </div>
          {item.sub && (
            <div className={`text-[9px] ${item.subColor} mt-0.5`}>{item.sub}</div>
          )}
        </div>
      ))}
    </div>
  );
}
