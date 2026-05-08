"use client";

import { Loader2, Check } from "lucide-react";

export type ProgressStep = {
  node: string;
  label: string;
  done: boolean;
};

export function ProgressIndicator({ steps, elapsed }: { steps: ProgressStep[]; elapsed: number }) {
  console.log("[ProgressIndicator render]", { steps, elapsed });
  if (steps.length === 0) {
    return (
      <div className="self-start w-full max-w-[95%] bg-[var(--color-panel)] border border-[var(--color-border)] rounded-lg p-3 text-xs text-[var(--color-muted)]">
        Iniciando…
      </div>
    );
  }
  const last = steps[steps.length - 1];
  return (
    <div className="self-start w-full max-w-[95%] bg-[var(--color-panel)] border border-[var(--color-border)] rounded-lg p-3">
      <div className="flex items-center gap-2 mb-2">
        <Loader2 size={14} className="animate-spin text-[var(--color-accent)]" />
        <span className="text-sm font-medium">{last.label}…</span>
        <span className="text-xs text-[var(--color-muted)] ml-auto font-mono">
          {(elapsed / 1000).toFixed(1)}s
        </span>
      </div>
      <ul className="space-y-1 text-xs text-[var(--color-muted)]">
        {steps.map((s, i) => (
          <li key={`${s.node}-${i}`} className="flex items-center gap-2">
            {s.done ? (
              <Check size={12} className="text-emerald-400" />
            ) : (
              <Loader2 size={12} className="animate-spin text-[var(--color-accent)]" />
            )}
            <span className={s.done ? "" : "text-[var(--color-text)]"}>{s.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
