"use client";

import { useEffect, useRef, useState } from "react";

interface PriceData {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
  pct_change: number | null;
}

interface Props {
  ticker: string;
  range: string; // "1M", "6M", "1Y", "5Y", "MAX"
}

export default function StockChart({ ticker, range }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<PriceData[]>([]);
  const [companyName, setCompanyName] = useState("");
  const [loading, setLoading] = useState(true);
  const [latestPrice, setLatestPrice] = useState<PriceData | null>(null);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);

    const now = new Date();
    let startDate = "";
    const limitMap: Record<string, number> = {
      "1M": 25, "6M": 130, "1Y": 253, "5Y": 1265, MAX: 9999,
    };

    if (range === "1M") {
      const d = new Date(now);
      d.setMonth(d.getMonth() - 1);
      startDate = d.toISOString().split("T")[0];
    } else if (range === "6M") {
      const d = new Date(now);
      d.setMonth(d.getMonth() - 6);
      startDate = d.toISOString().split("T")[0];
    } else if (range === "1Y") {
      const d = new Date(now);
      d.setFullYear(d.getFullYear() - 1);
      startDate = d.toISOString().split("T")[0];
    } else if (range === "5Y") {
      const d = new Date(now);
      d.setFullYear(d.getFullYear() - 5);
      startDate = d.toISOString().split("T")[0];
    }

    const params = new URLSearchParams({ limit: String(limitMap[range] || 9999) });
    if (startDate) params.set("start_date", startDate);

    fetch(`/api/stocks/${ticker}?${params}`)
      .then((r) => r.json())
      .then((res) => {
        setCompanyName(res.company_name || ticker);
        const sorted = (res.data || []).sort(
          (a: PriceData, b: PriceData) => a.date.localeCompare(b.date)
        );
        setData(sorted);
        if (sorted.length > 0) setLatestPrice(sorted[sorted.length - 1]);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [ticker, range]);

  useEffect(() => {
    if (!chartRef.current || data.length === 0) return;

    // Dynamic import for lightweight-charts (client only)
    import("lightweight-charts").then(({ createChart }) => {
      chartRef.current!.innerHTML = "";

      const chart = createChart(chartRef.current!, {
        width: chartRef.current!.clientWidth,
        height: 360,
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
        timeScale: { borderColor: "#2e2720", timeVisible: false },
      });

      const candleSeries = chart.addCandlestickSeries({
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderDownColor: "#ef4444",
        borderUpColor: "#22c55e",
        wickDownColor: "#ef4444",
        wickUpColor: "#22c55e",
      });

      const chartData = data
        .filter((d) => d.open !== null && d.high !== null && d.low !== null)
        .map((d) => ({
          time: d.date as any,
          open: d.open!,
          high: d.high!,
          low: d.low!,
          close: d.close,
        }));

      candleSeries.setData(chartData);

      // Volume
      const volumeSeries = chart.addHistogramSeries({
        color: "rgba(212, 168, 67, 0.2)",
        priceFormat: { type: "volume" },
        priceScaleId: "",
      });

      const volData = data
        .filter((d) => d.volume !== null)
        .map((d) => ({
          time: d.date as any,
          value: d.volume!,
          color: (d.pct_change || 0) >= 0
            ? "rgba(34, 197, 94, 0.3)"
            : "rgba(239, 68, 68, 0.3)",
        }));

      volumeSeries.setData(volData);
      chart.timeScale().fitContent();

      const handleResize = () => {
        if (chartRef.current) {
          chart.applyOptions({ width: chartRef.current.clientWidth });
        }
      };
      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
        chart.remove();
      };
    });
  }, [data]);

  const changeColor =
    latestPrice && (latestPrice.pct_change || 0) >= 0 ? "gain" : "loss";

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="flex items-center gap-3">
          <span className="font-mono text-base font-bold text-terminal-text">
            {ticker}
          </span>
          <span className="text-xs text-terminal-muted">{companyName}</span>
        </div>
        {latestPrice && (
          <div className="flex items-center gap-4">
            <span className="font-mono text-lg font-bold text-terminal-text">
              ${latestPrice.close.toFixed(2)}
            </span>
            <span className={`font-mono text-sm font-semibold ${changeColor}`}>
              {(latestPrice.pct_change || 0) >= 0 ? "+" : ""}
              {(latestPrice.pct_change || 0).toFixed(2)}%
            </span>
          </div>
        )}
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
  );
}
