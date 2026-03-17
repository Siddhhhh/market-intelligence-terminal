"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";

const API = "http://localhost:8000";

interface Driver {
  factor: string;
  category: string;
  impact: string;
  strength: number;
  confidence: number;
  composite_score: number;
  explanation: string;
  short_label: string;
  icon: string;
}

export default function CompanyIntelPage() {
  const searchParams = useSearchParams();
  const initialTicker = searchParams.get("ticker") || "AAPL";

  const [ticker, setTicker] = useState(initialTicker);
  const [search, setSearch] = useState(initialTicker);
  const [intel, setIntel] = useState<any>(null);
  const [movement, setMovement] = useState<any>(null);
  const [range, setRange] = useState("7d");
  const [loading, setLoading] = useState(true);
  const [movLoading, setMovLoading] = useState(true);

  // Fetch intelligence
  useEffect(() => {
    setLoading(true);
    fetch(`${API}/api/company/${ticker}/intelligence`)
      .then((r) => r.json())
      .then(setIntel)
      .catch(() => setIntel(null))
      .finally(() => setLoading(false));
  }, [ticker]);

  // Fetch movement explanation
  useEffect(() => {
    setMovLoading(true);
    fetch(`${API}/api/company/${ticker}/movement-explanation?range=${range}`)
      .then((r) => r.json())
      .then(setMovement)
      .catch(() => setMovement(null))
      .finally(() => setMovLoading(false));
  }, [ticker, range]);

  const handleSearch = () => {
    if (search.trim()) setTicker(search.trim().toUpperCase());
  };

  const RANGES = ["1d", "7d", "14d", "30d", "90d"];

  return (
    <div className="p-4 max-w-7xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <h1 className="font-display text-lg font-bold text-terminal-accent tracking-wide">
          COMPANY INTELLIGENCE
        </h1>
        <div className="flex gap-2 ml-4">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="input-field w-32 text-xs"
            placeholder="Ticker..."
          />
          <button onClick={handleSearch} className="btn-primary text-xs">
            Analyze
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <span className="text-terminal-muted cursor-blink text-sm">Loading intelligence</span>
        </div>
      ) : !intel || intel.detail ? (
        <div className="panel p-8 text-center text-terminal-muted">
          Ticker not found. Try AAPL, NVDA, MSFT, TSLA...
        </div>
      ) : (
        <div className="grid grid-cols-[1fr_1fr] gap-4">
          {/* ── LEFT PANEL ── */}
          <div className="space-y-3">
            {/* Company Header */}
            <div className="panel p-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-mono text-xl font-bold text-terminal-text">{intel.ticker}</span>
                  <span className="text-sm text-terminal-dim ml-3">{intel.name}</span>
                </div>
                {intel.market?.close && (
                  <div className="text-right">
                    <div className="font-mono text-xl font-bold text-terminal-text">
                      ${intel.market.close.toFixed(2)}
                    </div>
                    {intel.market.pct_change !== null && (
                      <div className={`font-mono text-sm font-semibold ${intel.market.pct_change >= 0 ? "gain" : "loss"}`}>
                        {intel.market.pct_change >= 0 ? "+" : ""}{intel.market.pct_change.toFixed(2)}%
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="flex gap-3 mt-2 text-[11px] text-terminal-muted">
                <span>{intel.sector}</span>
                <span>·</span>
                <span>{intel.industry}</span>
              </div>
            </div>

            {/* Financials */}
            <div className="panel">
              <div className="panel-header"><span className="panel-title">Financials</span></div>
              <div className="grid grid-cols-2 gap-px bg-terminal-border/30">
                <MetricCell label="Market Cap" value={formatLarge(intel.financials?.market_cap)} />
                <MetricCell label="P/E Ratio" value={intel.financials?.pe_ratio?.toFixed(1)} />
                <MetricCell label="Forward P/E" value={intel.financials?.forward_pe?.toFixed(1)} />
                <MetricCell label="EPS" value={intel.financials?.eps ? `$${intel.financials.eps.toFixed(2)}` : null} />
                <MetricCell label="Revenue" value={formatLarge(intel.financials?.revenue)} />
                <MetricCell label="Net Income" value={formatLarge(intel.financials?.net_income)} />
                <MetricCell label="Profit Margin" value={intel.financials?.profit_margin ? `${(intel.financials.profit_margin * 100).toFixed(1)}%` : null} />
                <MetricCell label="Rev Growth" value={intel.financials?.revenue_growth ? `${(intel.financials.revenue_growth * 100).toFixed(1)}%` : null} />
              </div>
            </div>

            {/* Technical Indicators */}
            <div className="panel">
              <div className="panel-header"><span className="panel-title">Technical Indicators</span></div>
              {intel.indicators?.ma20 ? (
                <div className="grid grid-cols-3 gap-px bg-terminal-border/30">
                  <MetricCell label="MA 20" value={intel.indicators.ma20?.toFixed(2)} />
                  <MetricCell label="MA 50" value={intel.indicators.ma50?.toFixed(2)} />
                  <MetricCell label="MA 200" value={intel.indicators.ma200?.toFixed(2)} />
                  <MetricCell label="RSI (14)" value={intel.indicators.rsi?.toFixed(1)} color={
                    intel.indicators.rsi > 70 ? "text-terminal-red" : intel.indicators.rsi < 30 ? "text-terminal-green" : undefined
                  } />
                  <MetricCell label="MACD" value={intel.indicators.macd?.toFixed(3)} />
                  <MetricCell label="Volatility" value={intel.indicators.volatility_20d?.toFixed(2)} />
                  <MetricCell label="Vol Ratio" value={intel.indicators.volume_ratio?.toFixed(2)} />
                  <MetricCell label="Trend" value={intel.indicators.trend} color={
                    intel.indicators.trend === "bullish" ? "text-terminal-green" : intel.indicators.trend === "bearish" ? "text-terminal-red" : undefined
                  } />
                </div>
              ) : (
                <div className="p-4 text-xs text-terminal-muted">
                  Run the indicator pipeline first: python -c &quot;from backend.analysis.indicator_pipeline import compute_indicators; compute_indicators()&quot;
                </div>
              )}
            </div>

            {/* Holders */}
            {intel.holders && intel.holders.length > 0 && (
              <div className="panel">
                <div className="panel-header"><span className="panel-title">Top Holders</span></div>
                <div className="divide-y divide-terminal-border/30">
                  {intel.holders.slice(0, 5).map((h: any, i: number) => (
                    <div key={i} className="px-4 py-2 flex items-center justify-between text-xs">
                      <span className="text-terminal-dim truncate flex-1">{h.name}</span>
                      <span className="font-mono text-terminal-muted ml-2">
                        {h.pct ? `${(h.pct * 100).toFixed(1)}%` : "—"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Relationships */}
            {intel.relationships && intel.relationships.length > 0 && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Relationships</span>
                  <span className="text-[9px] text-terminal-muted">estimated</span>
                </div>
                <div className="divide-y divide-terminal-border/30">
                  {intel.relationships.map((r: any, i: number) => (
                    <div key={i} className="px-4 py-2 flex items-center gap-3 text-xs">
                      <span className="font-mono font-bold text-terminal-text w-12">{r.ticker}</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded ${
                        r.type === "supplier" ? "bg-blue-500/10 text-blue-400" :
                        r.type === "competitor" ? "bg-red-500/10 text-red-400" :
                        "bg-green-500/10 text-green-400"
                      }`}>{r.type}</span>
                      <span className="text-terminal-muted truncate flex-1">{r.description}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ── RIGHT PANEL ── */}
          <div className="space-y-3">
            {/* Range Selector */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-terminal-muted uppercase tracking-wider">Movement Analysis</span>
              <div className="ml-auto flex gap-1">
                {RANGES.map((r) => (
                  <button
                    key={r}
                    onClick={() => setRange(r)}
                    className={`px-2.5 py-1 text-[10px] font-mono font-semibold rounded transition-colors ${
                      range === r
                        ? "bg-terminal-accent text-black"
                        : "text-terminal-muted hover:text-terminal-text hover:bg-terminal-surface"
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>

            {movLoading ? (
              <div className="panel p-8 text-center">
                <span className="text-terminal-muted cursor-blink text-sm">Analyzing movement</span>
              </div>
            ) : !movement || movement.detail ? (
              <div className="panel p-8 text-center text-terminal-muted text-sm">
                No movement data available
              </div>
            ) : (
              <>
                {/* Narrative Summary */}
                <div className="panel p-5">
                  <div className="flex items-center gap-3 mb-3">
                    <span className={`font-mono text-2xl font-bold ${movement.period_return >= 0 ? "gain" : "loss"}`}>
                      {movement.period_return >= 0 ? "+" : ""}{movement.period_return}%
                    </span>
                    <span className="text-xs text-terminal-muted">
                      over {range}
                    </span>
                  </div>
                  <div className="text-[13px] text-terminal-dim leading-relaxed">
                    {movement.narrative || movement.summary}
                  </div>
                  <div className="flex items-center gap-2 mt-3 text-[10px] text-terminal-muted">
                    <span>{movement.signals_analyzed} signals analyzed</span>
                    <span>·</span>
                    <span>{movement.drivers?.length || 0} key drivers identified</span>
                  </div>
                </div>

                {/* Confidence Meter */}
                <div className="panel p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-terminal-muted uppercase tracking-wider">Confidence</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold ${
                        movement.overall_confidence > 0.7 ? "text-terminal-green" :
                        movement.overall_confidence > 0.4 ? "text-terminal-amber" :
                        "text-terminal-red"
                      }`}>
                        {movement.overall_confidence > 0.7 ? "High" :
                         movement.overall_confidence > 0.4 ? "Moderate" : "Low"}
                      </span>
                      <span className="font-mono text-sm font-bold text-terminal-text">
                        {(movement.overall_confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <div className="h-2.5 bg-terminal-surface rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        movement.overall_confidence > 0.7 ? "bg-terminal-green" :
                        movement.overall_confidence > 0.4 ? "bg-terminal-amber" :
                        "bg-terminal-red"
                      }`}
                      style={{ width: `${movement.overall_confidence * 100}%` }}
                    />
                  </div>
                  <div className="flex justify-between mt-2 text-[9px] text-terminal-muted">
                    <span>Data quality: {(movement.confidence_breakdown?.data_quality * 100).toFixed(0)}%</span>
                    <span>Signal agreement: {(movement.confidence_breakdown?.signal_agreement * 100).toFixed(0)}%</span>
                  </div>
                </div>

                {/* Top Drivers — redesigned */}
                <div className="panel">
                  <div className="panel-header"><span className="panel-title">What's driving the move</span></div>
                  <div className="divide-y divide-terminal-border/30">
                    {movement.drivers?.map((d: Driver, i: number) => (
                      <div key={i} className="px-4 py-3.5">
                        <div className="flex items-center gap-2.5 mb-1.5">
                          <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                            d.impact === "positive" ? "bg-terminal-green" :
                            d.impact === "negative" ? "bg-terminal-red" :
                            "bg-terminal-amber"
                          }`} />
                          <span className={`text-xs font-bold ${
                            d.impact === "positive" ? "text-terminal-green" :
                            d.impact === "negative" ? "text-terminal-red" :
                            "text-terminal-amber"
                          }`}>
                            {d.impact === "positive" ? "Bullish" : d.impact === "negative" ? "Bearish" : "Neutral"}
                          </span>
                          <span className="text-xs font-semibold text-terminal-text">
                            {d.short_label}
                          </span>
                          <div className="ml-auto flex items-center gap-1.5">
                            <div className="w-14 h-1.5 bg-terminal-surface rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  d.impact === "positive" ? "bg-terminal-green" :
                                  d.impact === "negative" ? "bg-terminal-red" :
                                  "bg-terminal-amber"
                                }`}
                                style={{ width: `${d.strength * 100}%` }}
                              />
                            </div>
                          </div>
                        </div>
                        <div className="text-[11px] text-terminal-dim leading-relaxed pl-5">
                          {d.explanation}
                        </div>
                      </div>
                    ))}
                    {(!movement.drivers || movement.drivers.length === 0) && (
                      <div className="px-4 py-4 text-xs text-terminal-muted">
                        No significant drivers detected — the move appears to be noise
                      </div>
                    )}
                  </div>
                </div>

                {/* Buy/Sell Zones */}
                {movement.buy_sell_zones && (movement.buy_sell_zones.buy_zone || movement.buy_sell_zones.sell_zone) && (
                  <div className="panel">
                    <div className="panel-header">
                      <span className="panel-title">Support / Resistance Zones</span>
                    </div>
                    <div className="p-4 space-y-3">
                      {movement.buy_sell_zones.buy_zone && (
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-[10px] text-terminal-green uppercase tracking-wider">Support Zone</div>
                            <div className="font-mono text-sm text-terminal-text mt-0.5">
                              ${movement.buy_sell_zones.buy_zone.low} — ${movement.buy_sell_zones.buy_zone.high}
                            </div>
                          </div>
                          <span className="text-[9px] text-terminal-muted">{movement.buy_sell_zones.buy_zone.method}</span>
                        </div>
                      )}
                      {movement.buy_sell_zones.sell_zone && (
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-[10px] text-terminal-red uppercase tracking-wider">Resistance Zone</div>
                            <div className="font-mono text-sm text-terminal-text mt-0.5">
                              ${movement.buy_sell_zones.sell_zone.low} — ${movement.buy_sell_zones.sell_zone.high}
                            </div>
                          </div>
                          <span className="text-[9px] text-terminal-muted">{movement.buy_sell_zones.sell_zone.method}</span>
                        </div>
                      )}
                      <div className="text-[9px] text-terminal-muted pt-2 border-t border-terminal-border/30">
                        {movement.buy_sell_zones.label}
                      </div>
                    </div>
                  </div>
                )}

                {/* Technical Context */}
                {movement.technical_context && (
                  <div className="panel">
                    <div className="panel-header"><span className="panel-title">Technical Context</span></div>
                    <div className="grid grid-cols-3 gap-px bg-terminal-border/30">
                      <MetricCell label="Trend" value={movement.technical_context.trend} color={
                        movement.technical_context.trend === "bullish" ? "text-terminal-green" :
                        movement.technical_context.trend === "bearish" ? "text-terminal-red" : undefined
                      } />
                      <MetricCell label="RSI" value={movement.technical_context.rsi?.toFixed(1)} />
                      <MetricCell label="MACD" value={movement.technical_context.macd?.toFixed(3)} />
                    </div>
                  </div>
                )}

                {/* Methodology */}
                <div className="text-[9px] text-terminal-muted px-1 space-y-0.5">
                  <div>Model: {movement.model_version}</div>
                  <div>{movement.disclaimer}</div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCell({ label, value, color }: { label: string; value: any; color?: string }) {
  return (
    <div className="bg-terminal-panel px-3 py-2">
      <div className="text-[9px] text-terminal-muted uppercase tracking-wider">{label}</div>
      <div className={`font-mono text-xs font-semibold mt-0.5 ${color || "text-terminal-text"}`}>
        {value ?? "—"}
      </div>
    </div>
  );
}

function formatLarge(n: number | null | undefined): string | null {
  if (n == null) return null;
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}
