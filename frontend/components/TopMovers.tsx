"use client";

import { useEffect, useState } from "react";

interface Mover {
  ticker: string;
  name: string;
  date: string;
  close: number;
  pct_change: number;
  volume: number | null;
}

export default function TopMovers() {
  const [gainers, setGainers] = useState<Mover[]>([]);
  const [losers, setLosers] = useState<Mover[]>([]);
  const [tab, setTab] = useState<"gainers" | "losers">("gainers");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/api/movers/gainers?limit=10").then((r) => r.json()),
      fetch("/api/movers/losers?limit=10").then((r) => r.json()),
    ])
      .then(([g, l]) => {
        setGainers(g);
        setLosers(l);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const active = tab === "gainers" ? gainers : losers;

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Top Movers</span>
        <div className="flex gap-1">
          <button
            onClick={() => setTab("gainers")}
            className={`px-2 py-1 text-xs font-semibold rounded transition-colors ${
              tab === "gainers"
                ? "bg-terminal-green/20 text-terminal-green"
                : "text-terminal-muted hover:text-terminal-text"
            }`}
          >
            Gainers
          </button>
          <button
            onClick={() => setTab("losers")}
            className={`px-2 py-1 text-xs font-semibold rounded transition-colors ${
              tab === "losers"
                ? "bg-terminal-red/20 text-terminal-red"
                : "text-terminal-muted hover:text-terminal-text"
            }`}
          >
            Losers
          </button>
        </div>
      </div>

      <div className="divide-y divide-terminal-border/50">
        {loading
          ? Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-4 py-3 flex justify-between">
                <div className="shimmer h-4 w-20" />
                <div className="shimmer h-4 w-16" />
              </div>
            ))
          : active.map((m, i) => (
              <div
                key={m.ticker}
                className="px-4 py-2.5 flex items-center justify-between hover:bg-terminal-surface/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="text-xs text-terminal-muted w-4 font-mono">
                    {i + 1}
                  </span>
                  <div>
                    <span className="font-mono text-xs font-bold text-terminal-text">
                      {m.ticker}
                    </span>
                    <span className="text-[10px] text-terminal-muted ml-2">
                      {m.name.length > 16 ? m.name.slice(0, 16) + "…" : m.name}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-xs text-terminal-dim">
                    ${m.close.toFixed(2)}
                  </div>
                  <div
                    className={`font-mono text-xs font-bold ${
                      m.pct_change >= 0 ? "gain" : "loss"
                    }`}
                  >
                    {m.pct_change >= 0 ? "+" : ""}
                    {m.pct_change.toFixed(2)}%
                  </div>
                </div>
              </div>
            ))}
      </div>
    </div>
  );
}
