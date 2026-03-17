"use client";

import { useEffect, useState, useRef } from "react";

interface CryptoAsset {
  id: number;
  symbol: string;
  name: string;
}

interface PriceData {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  pct_change: number | null;
}

interface AssetSummary {
  symbol: string;
  name: string;
  close: number;
  pct_change: number;
  high: number;
  low: number;
  total_days: number;
}

export default function CryptoPage() {
  const [assets, setAssets] = useState<CryptoAsset[]>([]);
  const [selected, setSelected] = useState("BTC");
  const [data, setData] = useState<PriceData[]>([]);
  const [summaries, setSummaries] = useState<AssetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState("1Y");
  const chartRef = useRef<HTMLDivElement>(null);

  // Fetch all crypto assets
  useEffect(() => {
    fetch("http://localhost:8000/api/crypto")
      .then((r) => r.json())
      .then((a) => {
        setAssets(a);
        // Load summaries for all assets
        Promise.all(
          a.map((asset: CryptoAsset) =>
            fetch(`http://localhost:8000/api/crypto/${asset.symbol}?limit=365`)
              .then((r) => r.json())
              .then((res) => {
                const prices = (res.data || []).sort((a: PriceData, b: PriceData) =>
                  a.date.localeCompare(b.date)
                );
                if (prices.length === 0) return null;
                const latest = prices[prices.length - 1];
                const first = prices[0];
                const highs = prices.map((p: PriceData) => p.high || p.close);
                const lows = prices.map((p: PriceData) => p.low || p.close);
                return {
                  symbol: res.symbol,
                  name: res.name,
                  close: latest.close,
                  pct_change: first.close > 0
                    ? ((latest.close - first.close) / first.close) * 100
                    : 0,
                  high: Math.max(...highs),
                  low: Math.min(...lows),
                  total_days: prices.length,
                };
              })
          )
        ).then((s) => setSummaries(s.filter(Boolean) as AssetSummary[]));
      })
      .catch(() => {});
  }, []);

  // Fetch selected crypto data
  useEffect(() => {
    setLoading(true);
    const limitMap: Record<string, number> = {
      "1M": 30, "6M": 180, "1Y": 365, "5Y": 1825, MAX: 9999,
    };
    fetch(`http://localhost:8000/api/crypto/${selected}?limit=${limitMap[range] || 365}`)
      .then((r) => r.json())
      .then((res) => {
        const sorted = (res.data || []).sort((a: PriceData, b: PriceData) =>
          a.date.localeCompare(b.date)
        );
        setData(sorted);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selected, range]);

  // Render chart
  useEffect(() => {
    if (!chartRef.current || data.length === 0) return;

    import("lightweight-charts").then(({ createChart }) => {
      chartRef.current!.innerHTML = "";

      const chart = createChart(chartRef.current!, {
        width: chartRef.current!.clientWidth,
        height: 380,
        layout: {
          background: { color: "#161210" },
          textColor: "#a69070",
          fontSize: 11,
          fontFamily: "JetBrains Mono, monospace",
        },
        grid: {
          vertLines: { color: "rgba(46, 39, 32, 0.5)" },
          horzLines: { color: "rgba(46, 39, 32, 0.5)" },
        },
        crosshair: {
          vertLine: { color: "rgba(212, 168, 67, 0.4)", width: 1, labelBackgroundColor: "#d4a843" },
          horzLine: { color: "rgba(212, 168, 67, 0.4)", width: 1, labelBackgroundColor: "#d4a843" },
        },
        rightPriceScale: { borderColor: "#2e2720" },
        timeScale: { borderColor: "#2e2720" },
      });

      const candleSeries = chart.addCandlestickSeries({
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderDownColor: "#ef4444",
        borderUpColor: "#22c55e",
        wickDownColor: "#ef4444",
        wickUpColor: "#22c55e",
      });

      candleSeries.setData(
        data
          .filter((d) => d.open && d.high && d.low)
          .map((d) => ({
            time: d.date as any,
            open: d.open!,
            high: d.high!,
            low: d.low!,
            close: d.close,
          }))
      );

      chart.timeScale().fitContent();

      const handleResize = () => {
        if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
      };
      window.addEventListener("resize", handleResize);
      return () => {
        window.removeEventListener("resize", handleResize);
        chart.remove();
      };
    });
  }, [data]);

  const latest = data.length > 0 ? data[data.length - 1] : null;
  const RANGES = ["1M", "6M", "1Y", "5Y", "MAX"];

  return (
    <div className="p-4 space-y-4 max-w-7xl mx-auto">
      {/* Asset comparison cards */}
      <div className="grid grid-cols-3 gap-3">
        {summaries.map((s) => (
          <button
            key={s.symbol}
            onClick={() => setSelected(s.symbol)}
            className={`panel p-4 text-left transition-all ${
              selected === s.symbol
                ? "border-terminal-amber/60 bg-terminal-surface/80"
                : "hover:bg-terminal-surface/40"
            }`}
          >
            <div className="flex items-center justify-between">
              <div>
                <span className="font-mono text-base font-bold text-terminal-text">
                  {s.symbol}
                </span>
                <span className="text-xs text-terminal-muted ml-2">{s.name}</span>
              </div>
              <div className={`text-[10px] px-2 py-0.5 rounded font-semibold ${
                s.pct_change >= 0
                  ? "bg-terminal-green/15 text-terminal-green"
                  : "bg-terminal-red/15 text-terminal-red"
              }`}>
                {s.pct_change >= 0 ? "+" : ""}{s.pct_change.toFixed(1)}% 1Y
              </div>
            </div>
            <div className="font-mono text-xl font-bold text-terminal-text mt-2">
              ${s.close.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="flex items-center gap-4 mt-2 text-[10px] text-terminal-muted">
              <span>H: ${s.high.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
              <span>L: ${s.low.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
              <span>{s.total_days}d data</span>
            </div>
          </button>
        ))}
      </div>

      {/* Chart with controls */}
      <div className="panel">
        <div className="panel-header">
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm font-bold text-terminal-text">{selected}</span>
            {latest && (
              <>
                <span className="font-mono text-sm text-terminal-dim">
                  ${latest.close.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
                {latest.pct_change !== null && (
                  <span className={`font-mono text-xs font-semibold ${latest.pct_change >= 0 ? "gain" : "loss"}`}>
                    {latest.pct_change >= 0 ? "+" : ""}{latest.pct_change.toFixed(2)}%
                  </span>
                )}
              </>
            )}
          </div>
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-2.5 py-1 text-[10px] font-mono font-semibold rounded transition-colors ${
                  range === r
                    ? "bg-terminal-amber text-black"
                    : "text-terminal-muted hover:text-terminal-text hover:bg-terminal-surface"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        <div className="relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-terminal-panel/80 z-10">
              <span className="text-sm text-terminal-muted cursor-blink">Loading</span>
            </div>
          )}
          <div ref={chartRef} className="w-full" />
        </div>
      </div>

      {/* Recent activity */}
      <div className="grid grid-cols-2 gap-3">
        {/* Price table */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Recent Prices</span>
          </div>
          <div className="divide-y divide-terminal-border/50">
            <div className="px-4 py-2 flex items-center text-[10px] text-terminal-muted font-mono uppercase">
              <span className="flex-1">Date</span>
              <span className="w-24 text-right">Close</span>
              <span className="w-20 text-right">Change</span>
            </div>
            {data
              .slice(-15)
              .reverse()
              .map((d) => (
                <div key={d.date} className="px-4 py-1.5 flex items-center text-xs font-mono">
                  <span className="flex-1 text-terminal-muted">{d.date}</span>
                  <span className="w-24 text-right text-terminal-dim">
                    ${d.close.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                  <span className={`w-20 text-right font-semibold ${(d.pct_change || 0) >= 0 ? "gain" : "loss"}`}>
                    {(d.pct_change || 0) >= 0 ? "+" : ""}{(d.pct_change || 0).toFixed(2)}%
                  </span>
                </div>
              ))}
          </div>
        </div>

        {/* Market events for this crypto */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">{selected} Events</span>
          </div>
          <CryptoEvents symbol={selected} />
        </div>
      </div>
    </div>
  );
}

function CryptoEvents({ symbol }: { symbol: string }) {
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => {
    fetch(`http://localhost:8000/api/events?ticker=${symbol}&limit=15`)
      .then((r) => r.json())
      .then(setEvents)
      .catch(() => setEvents([]));
  }, [symbol]);

  if (events.length === 0) {
    return (
      <div className="p-4 text-xs text-terminal-muted">
        No detected events for {symbol}
      </div>
    );
  }

  return (
    <div className="divide-y divide-terminal-border/50">
      {events.map((e) => (
        <div key={e.id} className="px-4 py-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-terminal-muted">{e.date}</span>
            <span className={`text-[9px] px-1.5 py-0.5 rounded font-semibold ${
              e.severity === "critical"
                ? "bg-terminal-red/20 text-terminal-red"
                : e.severity === "high"
                ? "bg-terminal-amber/20 text-terminal-amber"
                : "bg-terminal-surface text-terminal-muted"
            }`}>
              {e.severity}
            </span>
          </div>
          <div className="text-[11px] text-terminal-dim mt-0.5">
            {e.event_type.replace("_", " ")}
            {e.magnitude && (
              <span className={`ml-1 font-mono font-semibold ${e.magnitude >= 0 ? "gain" : "loss"}`}>
                {e.magnitude >= 0 ? "+" : ""}{e.magnitude.toFixed(1)}%
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
