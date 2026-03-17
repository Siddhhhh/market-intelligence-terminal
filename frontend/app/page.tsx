"use client";

import { useState } from "react";
import CompanySelector from "@/components/CompanySelector";
import StockChart from "@/components/StockChart";
import StockDetail from "@/components/StockDetail";
import TimelineNav from "@/components/TimelineNav";
import SectorHeatmap from "@/components/SectorHeatmap";
import TopMovers from "@/components/TopMovers";
import StockSuggestions from "@/components/StockSuggestions";
import MarketTicker from "@/components/MarketTicker";
import AIChatPanel from "@/components/AIChatPanel";

export default function DashboardPage() {
  const [selectedTicker, setSelectedTicker] = useState("AAPL");
  const [timeRange, setTimeRange] = useState("1Y");

  return (
    <div className="flex flex-col h-[calc(100vh-48px)]">
      {/* Market Ticker Bar */}
      <MarketTicker />

      {/* Three-panel layout */}
      <div className="flex-1 grid grid-cols-[250px_1fr_330px] gap-px bg-terminal-border overflow-hidden">
        {/* ── LEFT PANEL ── */}
        <aside className="bg-terminal-panel overflow-hidden flex flex-col">
          <CompanySelector
            onSelect={setSelectedTicker}
            selectedTicker={selectedTicker}
          />
        </aside>

        {/* ── CENTER PANEL ── */}
        <main className="bg-terminal-bg overflow-y-auto">
          <div className="p-3 space-y-3">
            {/* Chart header */}
            <div className="flex items-center justify-between">
              <TimelineNav selected={timeRange} onChange={setTimeRange} />
            </div>

            {/* Stock Chart */}
            <StockChart ticker={selectedTicker} range={timeRange} />

            {/* Stock Metrics */}
            <StockDetail ticker={selectedTicker} />

            {/* Grid: Heatmap + Movers + Suggestions */}
            <div className="grid grid-cols-3 gap-3">
              <SectorHeatmap />
              <TopMovers />
              <StockSuggestions onSelect={setSelectedTicker} />
            </div>
          </div>
        </main>

        {/* ── RIGHT PANEL ── */}
        <aside className="bg-terminal-panel overflow-hidden flex flex-col">
          <AIChatPanel />
        </aside>
      </div>
    </div>
  );
}
