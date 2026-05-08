"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Loader2 } from "lucide-react";
import { Message, MessageList } from "./message-list";
import { ProgressIndicator, type ProgressStep } from "./progress-indicator";
import type { QueryResult } from "@/lib/types";

const SUGGESTIONS: { label: string; query: string }[] = [
  {
    label: "Multi-dominio",
    query:
      "Necesito publicar una nueva API interna que consume datos sensibles. ¿Qué controles técnicos, de seguridad y de paso a producción debo cumplir?",
  },
  {
    label: "Arquitectura",
    query: "¿Qué debe cumplir un microservicio antes de exponerse como API interna?",
  },
  {
    label: "Seguridad",
    query: "¿Puedo registrar el número de identificación de un cliente en los logs para depurar un error?",
  },
  {
    label: "Producción",
    query: "¿Qué evidencias necesito para pasar un microservicio a producción?",
  },
  {
    label: "Fuera de scope",
    query: "¿Cuál es la capital de Francia?",
  },
];

export function ChatForm() {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [progress, setProgress] = useState<ProgressStep[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number>(0);

  useEffect(() => {
    if (!busy) return;
    startRef.current = Date.now();
    setElapsed(0);
    const t = setInterval(() => setElapsed(Date.now() - startRef.current), 100);
    return () => clearInterval(t);
  }, [busy]);

  async function send(query: string) {
    if (!query.trim() || busy) return;
    const userMsg: Message = { id: `u-${Date.now()}`, role: "user", text: query };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setBusy(true);
    setProgress([]);

    try {
      const r = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ query }),
      });
      if (!r.ok || !r.body) {
        const err = await r.text().catch(() => "");
        setMessages((m) => [
          ...m,
          { id: `e-${Date.now()}`, role: "assistant", text: `Error ${r.status}: ${err}` },
        ]);
        return;
      }

      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalResult: QueryResult | null = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const normalized = buffer.replace(/\r\n/g, "\n");
        const events = normalized.split("\n\n");
        buffer = events.pop() ?? "";
        for (const raw of events) {
          if (!raw.trim()) continue;
          const lines = raw.split("\n");
          let event = "message";
          let data = "";
          for (const line of lines) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            else if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          if (!data) continue;
          try {
            const json = JSON.parse(data);
            if (event === "step") {
              setProgress((prev) => {
                const next = prev.map((p) => ({ ...p, done: true }));
                next.push({ node: json.node, label: json.label, done: false });
                return next;
              });
            } else if (event === "result") {
              finalResult = json as QueryResult;
            } else if (event === "error") {
              setMessages((m) => [
                ...m,
                { id: `e-${Date.now()}`, role: "assistant", text: `Error: ${json.message ?? "desconocido"}` },
              ]);
            }
          } catch (err) {
            console.error("[SSE parse error]", err, data);
          }
        }
      }

      if (finalResult) {
        setProgress((prev) => prev.map((p) => ({ ...p, done: true })));
        setMessages((m) => [
          ...m,
          {
            id: `a-${Date.now()}`,
            role: "assistant",
            text: finalResult!.answer,
            result: finalResult!,
          },
        ]);
      }
    } catch (err) {
      setMessages((m) => [
        ...m,
        { id: `e-${Date.now()}`, role: "assistant", text: `Error de red: ${String(err)}` },
      ]);
    } finally {
      setBusy(false);
      setProgress([]);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between p-3 border-b border-[var(--color-border)]">
        <div>
          <div className="text-sm font-semibold">Mesa de Ayuda IA — Banco</div>
          <div className="text-xs text-[var(--color-muted)]">
            Agentes: Arquitectura · Seguridad · Producción · Orquestador
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 && !busy ? (
          <div className="max-w-2xl mx-auto mt-8">
            <div className="text-sm text-[var(--color-muted)] mb-3">Probá una de estas consultas:</div>
            <div className="grid gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.label}
                  onClick={() => send(s.query)}
                  className="text-left p-3 border border-[var(--color-border)] rounded-md bg-[var(--color-panel)] hover:bg-[var(--color-panel-2)]"
                >
                  <span className="text-xs text-[var(--color-accent)] uppercase">{s.label}</span>
                  <div className="text-sm mt-1">{s.query}</div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto flex flex-col gap-4">
            <MessageList messages={messages} />
            {busy && <ProgressIndicator steps={progress} elapsed={elapsed} />}
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="p-3 border-t border-[var(--color-border)]"
      >
        <div className="max-w-3xl mx-auto flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Tu consulta técnica…"
            disabled={busy}
            className="flex-1 bg-[var(--color-panel)] border border-[var(--color-border)] rounded-md px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="px-3 py-2 bg-[var(--color-accent)] text-white rounded-md disabled:opacity-50 flex items-center gap-2"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            <span className="text-sm">Enviar</span>
          </button>
        </div>
      </form>
    </div>
  );
}
