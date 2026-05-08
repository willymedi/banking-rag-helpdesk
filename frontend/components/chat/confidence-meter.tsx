export function ConfidenceMeter({ value, threshold = 0.65 }: { value: number; threshold?: number }) {
  const pct = Math.round(value * 100);
  const ok = value >= threshold;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-[var(--color-muted)]">Confianza</span>
      <div className="w-32 h-2 bg-[var(--color-panel-2)] rounded-full overflow-hidden border border-[var(--color-border)]">
        <div
          className="h-full"
          style={{
            width: `${pct}%`,
            background: ok ? "var(--color-good)" : "var(--color-warn)",
          }}
        />
      </div>
      <span className={ok ? "text-[var(--color-good)]" : "text-[var(--color-warn)]"}>{pct}%</span>
    </div>
  );
}
