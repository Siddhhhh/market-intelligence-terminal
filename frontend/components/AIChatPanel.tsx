"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
  category?: string;
  confidence?: number;
  sources?: string[];
  time?: number;
}

export default function AIChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "I'm your AI market analyst. Ask me about stocks, sectors, market events, or financial concepts. I use real data from the database to ground my answers.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const question = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    try {
        const resp = await fetch("http://localhost:8000/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const data = await resp.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          category: data.category,
          confidence: data.confidence,
          sources: data.sources_used,
          time: data.processing_time,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Make sure the API server and Ollama are running.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="panel-header">
        <span className="panel-title">AI Analyst</span>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-terminal-green" />
          <span className="text-[10px] text-terminal-dim">ONLINE</span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.map((msg, i) => (
          <div key={i} className={`${msg.role === "user" ? "flex justify-end" : ""}`}>
            <div
              className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-terminal-accent/20 text-terminal-text border border-terminal-accent/30"
                  : "bg-terminal-surface text-terminal-dim"
              }`}
            >
              <div className="whitespace-pre-wrap leading-relaxed text-xs">
                {msg.content}
              </div>
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 pt-2 border-t border-terminal-border/50 flex flex-wrap gap-1">
                  {msg.sources.map((s) => (
                    <span
                      key={s}
                      className="text-[9px] px-1.5 py-0.5 rounded bg-terminal-accent/10 text-terminal-accent"
                    >
                      {s}
                    </span>
                  ))}
                  {msg.confidence !== undefined && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-terminal-amber/10 text-terminal-amber">
                      conf: {(msg.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  {msg.time !== undefined && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-terminal-surface text-terminal-muted">
                      {msg.time.toFixed(1)}s
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="bg-terminal-surface rounded-lg px-3 py-2">
            <span className="text-xs text-terminal-muted cursor-blink">Analyzing</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-terminal-border">
        <div className="flex gap-2">
          <input
            type="text"
            className="input-field text-xs flex-1"
            placeholder="Ask about markets, stocks, or financial concepts..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="btn-primary text-xs disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
