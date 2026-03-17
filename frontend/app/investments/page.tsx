"use client";

import { useState, useEffect } from "react";

const API = "http://localhost:8000";

export default function InvestmentsPage() {
  const [holdings, setHoldings] = useState<any[]>([]);
  const [analysis, setAnalysis] = useState<any>(null);
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Add holding form
  const [addTicker, setAddTicker] = useState("");
  const [addQty, setAddQty] = useState("");
  const [addPrice, setAddPrice] = useState("");
  const [addType, setAddType] = useState("stock");
  const [addMsg, setAddMsg] = useState("");

  // Score lookup
  const [scoreTicker, setScoreTicker] = useState("");
  const [scoreData, setScoreData] = useState<any>(null);
  const [scoreLoading, setScoreLoading] = useState(false);

  const loadData = () => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/api/portfolio/analysis`).then((r) => r.json()),
      fetch(`${API}/api/investments/profile`).then((r) => r.json()),
    ])
      .then(([a, p]) => {
        setAnalysis(a);
        setHoldings(a.holdings || []);
        setProfile(p);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []);

  const handleAdd = async () => {
    if (!addTicker || !addQty || !addPrice) return;
    setAddMsg("");
    try {
      const r = await fetch(`${API}/api/portfolio/holdings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: addTicker.toUpperCase(),
          quantity: parseFloat(addQty),
          avg_buy_price: parseFloat(addPrice),
          asset_type: addType,
        }),
      });
      const d = await r.json();
      if (r.ok) {
        setAddMsg(d.message);
        setAddTicker(""); setAddQty(""); setAddPrice("");
        loadData();
      } else {
        setAddMsg(d.detail || "Error adding holding");
      }
    } catch { setAddMsg("Failed to connect"); }
  };

  const handleDelete = async (id: number) => {
    await fetch(`${API}/api/portfolio/holdings/${id}`, { method: "DELETE" });
    loadData();
  };

  const handleScore = async () => {
    if (!scoreTicker) return;
    setScoreLoading(true);
    try {
      const r = await fetch(`${API}/api/investments/score/${scoreTicker.toUpperCase()}`);
      if (r.ok) setScoreData(await r.json());
      else setScoreData(null);
    } catch { setScoreData(null); }
    setScoreLoading(false);
  };

  const handleProfileUpdate = async (field: string, value: string) => {
    await fetch(`${API}/api/investments/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: value }),
    });
    loadData();
  };

  const totalPnl = analysis?.total_pnl || 0;
  const totalPnlPct = analysis?.total_pnl_pct || 0;

  return (
    <div className="p-4 max-w-7xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="font-display text-lg font-bold text-terminal-accent tracking-wide">
          INVESTMENT INTELLIGENCE
        </h1>
        {profile && (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-terminal-muted uppercase">Risk:</span>
              {["conservative", "moderate", "aggressive"].map((r) => (
                <button
                  key={r}
                  onClick={() => handleProfileUpdate("risk_tolerance", r)}
                  className={`px-2 py-0.5 text-[10px] font-semibold rounded transition-colors ${
                    profile.risk_tolerance === r
                      ? r === "conservative" ? "bg-blue-500/20 text-blue-400"
                        : r === "moderate" ? "bg-terminal-amber/20 text-terminal-amber"
                        : "bg-red-500/20 text-red-400"
                      : "text-terminal-muted hover:text-terminal-text"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <span className="text-terminal-muted cursor-blink text-sm">Loading portfolio</span>
        </div>
      ) : (
        <>
          {/* Portfolio Summary Cards */}
          <div className="grid grid-cols-4 gap-3">
            <SummaryCard label="Portfolio Value" value={`$${(analysis?.total_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
            <SummaryCard
              label="Total P&L"
              value={`${totalPnl >= 0 ? "+" : ""}$${totalPnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
              sub={`${totalPnlPct >= 0 ? "+" : ""}${totalPnlPct.toFixed(1)}%`}
              color={totalPnl >= 0 ? "text-terminal-green" : "text-terminal-red"}
            />
            <SummaryCard
              label="Diversification"
              value={`${analysis?.diversification_score || 0}/100`}
              color={
                (analysis?.diversification_score || 0) > 60 ? "text-terminal-green"
                : (analysis?.diversification_score || 0) > 30 ? "text-terminal-amber"
                : "text-terminal-red"
              }
            />
            <SummaryCard
              label="Risk Level"
              value={(analysis?.risk_level || "none").toUpperCase()}
              color={
                analysis?.risk_level === "high" ? "text-terminal-red"
                : analysis?.risk_level === "moderate" ? "text-terminal-amber"
                : "text-terminal-green"
              }
            />
          </div>

          <div className="grid grid-cols-[1fr_380px] gap-4">
            {/* ── LEFT: Holdings + Add ── */}
            <div className="space-y-3">
              {/* Add Holding */}
              <div className="panel p-4">
                <div className="text-xs text-terminal-muted uppercase tracking-wider mb-3">Add Position</div>
                <div className="flex gap-2">
                  <select value={addType} onChange={(e) => setAddType(e.target.value)} className="input-field text-xs w-20">
                    <option value="stock">Stock</option>
                    <option value="crypto">Crypto</option>
                  </select>
                  <input value={addTicker} onChange={(e) => setAddTicker(e.target.value.toUpperCase())} placeholder="Ticker" className="input-field text-xs w-24" onKeyDown={(e) => e.key === "Enter" && handleAdd()} />
                  <input value={addQty} onChange={(e) => setAddQty(e.target.value)} placeholder="Qty" type="number" className="input-field text-xs w-20" />
                  <input value={addPrice} onChange={(e) => setAddPrice(e.target.value)} placeholder="Buy price" type="number" className="input-field text-xs w-28" />
                  <button onClick={handleAdd} className="btn-primary text-xs">Add</button>
                </div>
                {addMsg && <div className="text-[11px] text-terminal-accent mt-2">{addMsg}</div>}
              </div>

              {/* Holdings Table */}
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Holdings ({holdings.length})</span>
                  <span className="text-[10px] text-terminal-muted">${(analysis?.total_value || 0).toLocaleString()}</span>
                </div>
                {holdings.length === 0 ? (
                  <div className="p-6 text-center text-xs text-terminal-muted">
                    No holdings yet — add some positions above
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-[10px] text-terminal-muted uppercase tracking-wider border-b border-terminal-border/30">
                          <td className="px-3 py-2">Ticker</td>
                          <td className="px-3 py-2 text-right">Qty</td>
                          <td className="px-3 py-2 text-right">Avg Cost</td>
                          <td className="px-3 py-2 text-right">Price</td>
                          <td className="px-3 py-2 text-right">Value</td>
                          <td className="px-3 py-2 text-right">P&L</td>
                          <td className="px-3 py-2 text-right">P&L %</td>
                          <td className="px-3 py-2"></td>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-terminal-border/20">
                        {holdings.map((h) => (
                          <tr key={h.id} className="hover:bg-terminal-surface/30 transition-colors">
                            <td className="px-3 py-2">
                              <span className="font-mono font-bold text-terminal-text">{h.ticker}</span>
                              <span className="text-[9px] text-terminal-muted ml-1">{h.asset_type === "crypto" ? "C" : ""}</span>
                            </td>
                            <td className="px-3 py-2 text-right font-mono text-terminal-dim">{h.quantity}</td>
                            <td className="px-3 py-2 text-right font-mono text-terminal-dim">${h.avg_buy_price}</td>
                            <td className="px-3 py-2 text-right font-mono text-terminal-text">${h.current_price}</td>
                            <td className="px-3 py-2 text-right font-mono text-terminal-text">${h.current_value.toLocaleString()}</td>
                            <td className={`px-3 py-2 text-right font-mono font-semibold ${h.pnl >= 0 ? "gain" : "loss"}`}>
                              {h.pnl >= 0 ? "+" : ""}${h.pnl.toLocaleString()}
                            </td>
                            <td className={`px-3 py-2 text-right font-mono font-semibold ${h.pnl_pct >= 0 ? "gain" : "loss"}`}>
                              {h.pnl_pct >= 0 ? "+" : ""}{h.pnl_pct.toFixed(1)}%
                            </td>
                            <td className="px-3 py-2 text-right">
                              <button onClick={() => handleDelete(h.id)} className="text-terminal-muted hover:text-terminal-red text-[10px] transition-colors">
                                Remove
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Warnings & Suggestions */}
              {analysis && (analysis.warnings?.length > 0 || analysis.suggestions?.length > 0) && (
                <div className="panel">
                  <div className="panel-header"><span className="panel-title">Portfolio Insights</span></div>
                  <div className="p-4 space-y-2">
                    {analysis.warnings?.map((w: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <span className="text-terminal-red mt-0.5">●</span>
                        <span className="text-terminal-dim">{w}</span>
                      </div>
                    ))}
                    {analysis.suggestions?.map((s: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <span className="text-terminal-accent mt-0.5">●</span>
                        <span className="text-terminal-dim">{s}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* ── RIGHT: Sector + Score ── */}
            <div className="space-y-3">
              {/* Sector Breakdown */}
              <div className="panel">
                <div className="panel-header"><span className="panel-title">Sector Allocation</span></div>
                <div className="p-4 space-y-2">
                  {analysis?.sector_breakdown && Object.entries(analysis.sector_breakdown as Record<string, number>)
                    .sort(([, a], [, b]) => b - a)
                    .map(([sector, pct]) => (
                      <div key={sector}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-terminal-dim">{sector}</span>
                          <span className="font-mono text-terminal-text">{pct}%</span>
                        </div>
                        <div className="h-1.5 bg-terminal-surface rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${pct > 50 ? "bg-terminal-red" : pct > 30 ? "bg-terminal-amber" : "bg-terminal-accent"}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  {(!analysis?.sector_breakdown || Object.keys(analysis.sector_breakdown).length === 0) && (
                    <div className="text-xs text-terminal-muted text-center py-3">Add holdings to see allocation</div>
                  )}
                </div>
              </div>

              {/* Investment Score Checker */}
              <div className="panel">
                <div className="panel-header"><span className="panel-title">Investment Score</span></div>
                <div className="p-4">
                  <div className="flex gap-2 mb-3">
                    <input
                      value={scoreTicker}
                      onChange={(e) => setScoreTicker(e.target.value.toUpperCase())}
                      placeholder="Enter ticker..."
                      className="input-field text-xs flex-1"
                      onKeyDown={(e) => e.key === "Enter" && handleScore()}
                    />
                    <button onClick={handleScore} disabled={scoreLoading} className="btn-primary text-xs">
                      Score
                    </button>
                  </div>

                  {scoreLoading && <div className="text-xs text-terminal-muted cursor-blink">Scoring</div>}

                  {scoreData && !scoreLoading && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-mono text-lg font-bold text-terminal-text">{scoreData.ticker}</span>
                          <span className="text-xs text-terminal-muted ml-2">{scoreData.name}</span>
                        </div>
                        <div className="text-right">
                          <div className={`font-mono text-2xl font-bold ${
                            scoreData.score >= 65 ? "text-terminal-green" :
                            scoreData.score >= 40 ? "text-terminal-amber" :
                            "text-terminal-red"
                          }`}>
                            {scoreData.score}
                          </div>
                          <div className={`text-xs font-semibold ${
                            scoreData.rating === "Strong Buy" || scoreData.rating === "Buy" ? "text-terminal-green" :
                            scoreData.rating === "Hold" ? "text-terminal-amber" :
                            "text-terminal-red"
                          }`}>
                            {scoreData.rating}
                          </div>
                        </div>
                      </div>

                      {/* Factor bars */}
                      <div className="space-y-1.5">
                        {Object.entries(scoreData.factors as Record<string, number>).map(([factor, val]) => (
                          <div key={factor}>
                            <div className="flex justify-between text-[10px] mb-0.5">
                              <span className="text-terminal-muted capitalize">{factor}</span>
                              <span className="font-mono text-terminal-dim">{val.toFixed(1)}/10</span>
                            </div>
                            <div className="h-1.5 bg-terminal-surface rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${val >= 7 ? "bg-terminal-green" : val >= 4 ? "bg-terminal-amber" : "bg-terminal-red"}`}
                                style={{ width: `${val * 10}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Suitability */}
                      <div className={`text-xs p-2 rounded ${
                        scoreData.matches_profile ? "bg-terminal-green/10 text-terminal-green" : "bg-terminal-red/10 text-terminal-red"
                      }`}>
                        {scoreData.matches_profile
                          ? `Suitable for your ${scoreData.user_profile} profile`
                          : `May not suit your ${scoreData.user_profile} profile`}
                      </div>

                      {/* Reasoning */}
                      {scoreData.reasoning?.length > 0 && (
                        <div className="space-y-1">
                          {scoreData.reasoning.map((r: string, i: number) => (
                            <div key={i} className="text-[10px] text-terminal-dim">• {r}</div>
                          ))}
                        </div>
                      )}

                      <div className="text-[9px] text-terminal-muted">{scoreData.disclaimer}</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function SummaryCard({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="panel p-3">
      <div className="text-[9px] text-terminal-muted uppercase tracking-wider">{label}</div>
      <div className={`font-mono text-lg font-bold mt-1 ${color || "text-terminal-text"}`}>{value}</div>
      {sub && <div className={`font-mono text-xs ${color || "text-terminal-dim"}`}>{sub}</div>}
    </div>
  );
}
