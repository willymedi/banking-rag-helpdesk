import { cn } from "@/lib/utils";

const COLORS: Record<string, string> = {
  ArchitectureAgent: "bg-[var(--color-accent)]/20 text-[var(--color-accent)] border-[var(--color-accent)]/40",
  SecurityAgent: "bg-[var(--color-bad)]/15 text-[var(--color-bad)] border-[var(--color-bad)]/40",
  ProductionAgent: "bg-[var(--color-good)]/15 text-[var(--color-good)] border-[var(--color-good)]/40",
};

export function AgentBadges({ agents }: { agents: string[] }) {
  if (!agents.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {agents.map((a) => (
        <span
          key={a}
          className={cn(
            "px-2 py-0.5 text-xs rounded-full border",
            COLORS[a] ?? "bg-[var(--color-panel-2)] border-[var(--color-border)] text-[var(--color-muted)]"
          )}
        >
          {a}
        </span>
      ))}
    </div>
  );
}
