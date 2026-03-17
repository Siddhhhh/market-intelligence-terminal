import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Market Intelligence Terminal",
  description: "Bloomberg-style financial intelligence dashboard powered by AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-terminal-bg text-terminal-text">
        <header className="h-12 bg-terminal-panel border-b border-terminal-border flex items-center px-5 gap-6 sticky top-0 z-50">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 rounded-full bg-terminal-accent" />
            <span className="font-display font-semibold text-sm tracking-wide text-terminal-accent">
              MARKET INTELLIGENCE
            </span>
          </div>

          <div className="w-px h-5 bg-terminal-border" />

          <nav className="flex items-center gap-1">
            <Link
              href="/"
              className="px-3 py-1.5 text-[11px] font-semibold text-terminal-dim hover:text-terminal-text hover:bg-terminal-surface rounded transition-colors uppercase tracking-widest"
            >
              Dashboard
            </Link>
            <Link
              href="/crypto"
              className="px-3 py-1.5 text-[11px] font-semibold text-terminal-dim hover:text-terminal-text hover:bg-terminal-surface rounded transition-colors uppercase tracking-widest"
            >
              Crypto
            </Link>
            <Link
              href="/company?ticker=AAPL"
              className="px-3 py-1.5 text-[11px] font-semibold text-terminal-dim hover:text-terminal-text hover:bg-terminal-surface rounded transition-colors uppercase tracking-widest"
            >
              Intelligence
            </Link>
            <Link
              href="/investments"
              className="px-3 py-1.5 text-[11px] font-semibold text-terminal-dim hover:text-terminal-text hover:bg-terminal-surface rounded transition-colors uppercase tracking-widest"
            >
              Portfolio
            </Link>
          </nav>

          <div className="ml-auto flex items-center gap-4">
            <span className="text-[11px] font-mono text-terminal-muted">
              {new Date().toLocaleDateString("en-US", {
                weekday: "short",
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-terminal-green" />
              <span className="text-[10px] text-terminal-dim tracking-wider">LIVE</span>
            </div>
          </div>
        </header>

        <main className="grid-bg">{children}</main>
      </body>
    </html>
  );
}
