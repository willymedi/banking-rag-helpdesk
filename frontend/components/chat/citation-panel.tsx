"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, FileText } from "lucide-react";
import type { Citation } from "@/lib/types";

export function CitationPanel({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState(true);
  if (!citations?.length) return null;
  return (
    <div className="mt-3 border border-[var(--color-border)] rounded-md bg-[var(--color-panel-2)]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-[var(--color-muted)] hover:text-[var(--color-fg)]"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <FileText size={14} />
        <span>{citations.length} fuente(s) consultada(s)</span>
      </button>
      {open && (
        <ul className="px-3 pb-3 space-y-2">
          {citations.map((c, i) => (
            <li key={`${c.chunk_id}-${i}`} className="border-l-2 border-[var(--color-accent)]/60 pl-3 py-1">
              <div className="text-xs text-[var(--color-muted)]">
                {c.doc_title} · <span className="text-[var(--color-fg)]">{c.section_title}</span>
                <span className="ml-2 opacity-60">[{c.chunk_id}]</span>
              </div>
              <div className="text-sm mt-1 italic text-[var(--color-fg)]/80">{c.snippet}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
