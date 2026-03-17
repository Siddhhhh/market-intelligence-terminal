"use client";

interface Props {
  selected: string;
  onChange: (range: string) => void;
}

const RANGES = ["1M", "6M", "1Y", "5Y", "MAX"];

export default function TimelineNav({ selected, onChange }: Props) {
  return (
    <div className="flex items-center gap-1">
      {RANGES.map((r) => (
        <button
          key={r}
          onClick={() => onChange(r)}
          className={`px-3 py-1 text-xs font-mono font-semibold rounded transition-colors ${
            selected === r
              ? "bg-terminal-accent text-white"
              : "text-terminal-muted hover:text-terminal-text hover:bg-terminal-surface"
          }`}
        >
          {r}
        </button>
      ))}
    </div>
  );
}
