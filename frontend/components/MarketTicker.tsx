"use client";

import { useEffect, useState } from "react";

interface Overview {
  market_date: string;
  sp500_proxy_change: number | null;
  vix_level: number | null;
  total_companies: number;
  advancing: number;
  declining: number;
  top_gainers: { ticker: string; name: string; pct_change: number }[];
  top_losers: { ticker: string; name: string; pct_change: number }[];
}

export default function MarketTicker() {
  const [data, setData] = useState<Overview | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/api/market/overview")
      .then((r) => r.json())
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) {
    return (
      <div className="h-8 bg-terminal-surface/50 border-b border-terminal-border flex items-center px-4">
        <div className="shimmer h-3 w-64" />
      </div>
    );
  }

  const spChange = data.sp500_proxy_change || 0;
  const advDecl = data.total_companies > 0
    ? ((data.advancing / data.total_companies) * 100).toFixed(0)
    : "0";

  return (
    <div className="h-9 bg-terminal-surface/40 border-b border-terminal-border flex items-center px-4 gap-6 overflow-x-auto text-[11px] font-mono">
      {/* Market date */}
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-terminal-muted">MKT</span>
        <span className="text-terminal-dim">{data.market_date}</span>
      </div>

      {/* Divider */}
      <div className="w-px h-4 bg-terminal-border shrink-0" />

      {/* S&P 500 proxy */}
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-terminal-muted">S&P 500</span>
        <span className={`font-semibold ${spChange >= 0 ? "text-terminal-green" : "text-terminal-red"}`}>
          {spChange >= 0 ? "▲" : "▼"} {spChange >= 0 ? "+" : ""}{spChange.toFixed(2)}%
        </span>
      </div>

      <div className="w-px h-4 bg-terminal-border shrink-0" />

      {/* VIX */}
      {data.vix_level && (
        <>
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-terminal-muted">VIX</span>
            <span className={`font-semibold ${data.vix_level > 20 ? "text-terminal-amber" : "text-terminal-dim"}`}>
              {data.vix_level.toFixed(1)}
            </span>
          </div>
          <div className="w-px h-4 bg-terminal-border shrink-0" />
        </>
      )}

      {/* Advance / Decline */}
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-terminal-muted">A/D</span>
        <span className="text-terminal-green">{data.advancing}</span>
        <span className="text-terminal-muted">/</span>
        <span className="text-terminal-red">{data.declining}</span>
        <span className="text-terminal-muted">({advDecl}%)</span>
      </div>

      <div className="w-px h-4 bg-terminal-border shrink-0" />

      {/* Top movers ticker tape */}
      <div className="flex items-center gap-4 shrink-0">
        {data.top_gainers.slice(0, 3).map((g) => (
          <span key={g.ticker} className="flex items-center gap-1">
            <span className="text-terminal-text font-semibold">{g.ticker}</span>
            <span className="text-terminal-green">+{g.pct_change.toFixed(1)}%</span>
          </span>
        ))}
        {data.top_losers.slice(0, 3).map((l) => (
          <span key={l.ticker} className="flex items-center gap-1">
            <span className="text-terminal-text font-semibold">{l.ticker}</span>
            <span className="text-terminal-red">{l.pct_change.toFixed(1)}%</span>
          </span>
        ))}
      </div>
    </div>
  );
}
