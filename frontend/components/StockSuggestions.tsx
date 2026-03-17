"use client";

import { useEffect, useState } from "react";

interface Suggestion {
  ticker: string;
  name: string;
  sector: string | null;
  close: number;
  weekly_return: number | null;
  monthly_return: number | null;
  signal: string;
  reason: string;
}

interface Props {
  onSelect: (ticker: string) => void;
}

export default function StockSuggestions({ onSelect }: Props) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8000/api/market/suggestions?limit=6")
      .then((r) => r.json())
      .then((data) => {
        setSuggestions(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const signalBadge = (signal: string) => {
    switch (signal) {
      case "strong_momentum":
        return { bg: "bg-terminal-green/15 border-terminal-green/30", text: "text-terminal-green", label: "Strong" };
      case "momentum":
        return { bg: "bg-terminal-accent/15 border-terminal-accent/30", text: "text-terminal-accent", label: "Momentum" };
      default:
        return { bg: "bg-terminal-amber/15 border-terminal-amber/30", text: "text-terminal-amber", label: "Trending" };
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Stocks to Watch</span>
        <span className="text-[10px] text-terminal-muted">Based on momentum</span>
      </div>

      <div className="divide-y divide-terminal-border/50">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="px-4 py-3">
                <div className="shimmer h-4 w-32 mb-2" />
                <div className="shimmer h-3 w-48" />
              </div>
            ))
          : suggestions.map((s) => {
              const badge = signalBadge(s.signal);
              return (
                <button
                  key={s.ticker}
                  onClick={() => onSelect(s.ticker)}
                  className="w-full text-left px-4 py-3 hover:bg-terminal-surface/50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-terminal-text">
                        {s.ticker}
                      </span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded border ${badge.bg} ${badge.text}`}>
                        {badge.label}
                      </span>
                    </div>
                    <div className="text-right">
                      <span className="font-mono text-xs text-terminal-dim">
                        ${s.close.toFixed(2)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-[10px] text-terminal-muted truncate flex-1">
                      {s.name}
                    </span>
                    {s.weekly_return !== null && (
                      <span className={`text-[10px] font-mono ${s.weekly_return >= 0 ? "text-terminal-green" : "text-terminal-red"}`}>
                        W: {s.weekly_return >= 0 ? "+" : ""}{s.weekly_return.toFixed(1)}%
                      </span>
                    )}
                    {s.monthly_return !== null && (
                      <span className={`text-[10px] font-mono ${s.monthly_return >= 0 ? "text-terminal-green" : "text-terminal-red"}`}>
                        M: {s.monthly_return >= 0 ? "+" : ""}{s.monthly_return.toFixed(1)}%
                      </span>
                    )}
                  </div>
                  <div className="text-[9px] text-terminal-muted mt-1">{s.reason}</div>
                </button>
              );
            })}
      </div>
    </div>
  );
}
