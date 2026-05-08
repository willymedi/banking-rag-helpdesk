"use client";

import type { QueryResult } from "@/lib/types";
import { AgentBadges } from "./agent-badges";
import { CitationPanel } from "./citation-panel";
import { ConfidenceMeter } from "./confidence-meter";
import { FeedbackButtons } from "./feedback-buttons";

export type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  result?: QueryResult;
};

export function MessageList({ messages }: { messages: Message[] }) {
  return (
    <div className="flex flex-col gap-4">
      {messages.map((m) => (
        <Bubble key={m.id} message={m} />
      ))}
    </div>
  );
}

function Bubble({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="self-end max-w-[80%] bg-[var(--color-accent)]/15 border border-[var(--color-accent)]/30 rounded-lg px-3 py-2 text-sm">
        {message.text}
      </div>
    );
  }
  const r = message.result;
  const blocked = r?.blocked_reason && r.blocked_reason !== "";
  return (
    <div className="self-start w-full max-w-[95%] bg-[var(--color-panel)] border border-[var(--color-border)] rounded-lg p-3">
      <div className="flex items-center justify-between gap-3 mb-2">
        <AgentBadges agents={r?.participating_agents ?? []} />
        {r && <ConfidenceMeter value={r.confidence} />}
      </div>
      <div className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</div>
      {blocked && (
        <div className="mt-2 text-xs text-[var(--color-warn)]">
          Motivo: <code>{r!.blocked_reason}</code>
        </div>
      )}
      {r && <CitationPanel citations={r.citations} />}
      {r?.trace_id && (
        <div className="mt-2 text-[10px] text-[var(--color-muted)] font-mono">
          trace_id: {r.trace_id || "(local)"} · query_id: {r.query_id}
        </div>
      )}
      {r && !blocked && <FeedbackButtons result={r} />}
    </div>
  );
}
