"use client";

import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import type { QueryResult } from "@/lib/types";

export function FeedbackButtons({ result }: { result: QueryResult }) {
  const [sent, setSent] = useState<number | null>(null);

  async function send(rating: 1 | -1) {
    setSent(rating);
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        payload: {
          query_id: result.query_id,
          trace_id: result.trace_id,
          rating,
          final_answer_excerpt: result.answer.slice(0, 300),
          participating_agents: result.participating_agents,
        },
      }),
    });
  }

  return (
    <div className="flex items-center gap-2 mt-2 text-xs">
      <button
        disabled={sent !== null}
        onClick={() => send(1)}
        className={`p-1.5 rounded border border-[var(--color-border)] hover:bg-[var(--color-panel-2)] ${
          sent === 1 ? "text-[var(--color-good)]" : "text-[var(--color-muted)]"
        }`}
        aria-label="thumbs-up"
      >
        <ThumbsUp size={14} />
      </button>
      <button
        disabled={sent !== null}
        onClick={() => send(-1)}
        className={`p-1.5 rounded border border-[var(--color-border)] hover:bg-[var(--color-panel-2)] ${
          sent === -1 ? "text-[var(--color-bad)]" : "text-[var(--color-muted)]"
        }`}
        aria-label="thumbs-down"
      >
        <ThumbsDown size={14} />
      </button>
      {sent && <span className="text-[var(--color-muted)]">Gracias por tu feedback.</span>}
    </div>
  );
}
