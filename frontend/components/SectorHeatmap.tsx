"use client";

import { useEffect, useState } from "react";

interface HeatmapEntry {
  sector: string;
  display_name: string;
  avg_pct_change: number;
  company_count: number;
  top_gainer: string | null;
  top_gainer_pct: number | null;
  top_loser: string | null;
  top_loser_pct: number | null;
}

export default function SectorHeatmap() {
  const [data, setData] = useState<HeatmapEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/heatmap")
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const getColor = (pct: number) => {
    if (pct > 2) return "bg-green-500/40 border-green-500/60";
    if (pct > 1) return "bg-green-500/25 border-green-500/40";
    if (pct > 0) return "bg-green-500/10 border-green-500/20";
    if (pct > -1) return "bg-red-500/10 border-red-500/20";
    if (pct > -2) return "bg-red-500/25 border-red-500/40";
    return "bg-red-500/40 border-red-500/60";
  };

  if (loading) {
    return (
      <div className="panel">
        <div className="panel-header"><span className="panel-title">Sector Heatmap</span></div>
        <div className="p-4 grid grid-cols-3 gap-2">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="shimmer h-20 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Sector Heatmap</span>
        <span className="text-xs text-terminal-muted">Latest trading day</span>
      </div>
      <div className="p-3 grid grid-cols-3 gap-2">
        {data.map((s) => (
          <div
            key={s.sector}
            className={`p-3 rounded-lg border ${getColor(s.avg_pct_change)} transition-all hover:scale-[1.02] cursor-default`}
          >
            <div className="text-xs font-semibold text-terminal-text truncate">
              {s.display_name}
            </div>
            <div
              className={`text-lg font-mono font-bold mt-1 ${
                s.avg_pct_change >= 0 ? "gain" : "loss"
              }`}
            >
              {s.avg_pct_change >= 0 ? "+" : ""}
              {s.avg_pct_change.toFixed(2)}%
            </div>
            <div className="text-[10px] text-terminal-muted mt-1">
              {s.company_count} companies
            </div>
            {s.top_gainer && (
              <div className="text-[10px] text-terminal-green mt-0.5">
                ▲ {s.top_gainer} +{s.top_gainer_pct?.toFixed(1)}%
              </div>
            )}
            {s.top_loser && (
              <div className="text-[10px] text-terminal-red">
                ▼ {s.top_loser} {s.top_loser_pct?.toFixed(1)}%
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
