"use client";

import { useState, useEffect } from "react";

interface Company {
  id: number;
  ticker: string;
  name: string;
  sector: string | null;
}

interface Props {
  onSelect: (ticker: string) => void;
  selectedTicker: string;
}

export default function CompanySelector({ onSelect, selectedTicker }: Props) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
  const [sectors, setSectors] = useState<{ name: string; display_name: string }[]>([]);

  useEffect(() => {
    fetch("/api/sectors")
      .then((r) => r.json())
      .then(setSectors)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const params = new URLSearchParams({ limit: "30" });
    if (search) params.set("search", search);
    if (sector) params.set("sector", sector);

    fetch(`/api/stocks?${params}`)
      .then((r) => r.json())
      .then(setCompanies)
      .catch(() => {});
  }, [search, sector]);

  return (
    <div className="flex flex-col h-full">
      <div className="panel-header">
        <span className="panel-title">Companies</span>
      </div>

      <div className="p-3 space-y-2 border-b border-terminal-border">
        <input
          type="text"
          placeholder="Search ticker or name..."
          className="input-field text-xs"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="input-field text-xs"
          value={sector}
          onChange={(e) => setSector(e.target.value)}
        >
          <option value="">All Sectors</option>
          {sectors.map((s) => (
            <option key={s.name} value={s.name}>
              {s.display_name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex-1 overflow-y-auto">
        {companies.map((c) => (
          <button
            key={c.id}
            onClick={() => onSelect(c.ticker)}
            className={`w-full text-left px-3 py-2 flex items-center justify-between border-b border-terminal-border/50 hover:bg-terminal-surface transition-colors ${
              selectedTicker === c.ticker ? "bg-terminal-surface border-l-2 border-l-terminal-accent" : ""
            }`}
          >
            <div>
              <span className="font-mono text-xs font-semibold text-terminal-text">
                {c.ticker}
              </span>
              <span className="text-xs text-terminal-muted ml-2 truncate">
                {c.name.length > 20 ? c.name.slice(0, 20) + "…" : c.name}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
