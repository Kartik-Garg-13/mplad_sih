"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { askAssistant, type AssistantReply } from "@/lib/api";

type Turn = { question: string; reply: AssistantReply | null; error?: string };

const OPENERS = [
  "How many works are there in total?",
  "What is detector B3?",
  "How many works have no flags?",
  "How was this validated?",
];

function TierPill({ tier }: { tier: string }) {
  const isA = tier === "A";
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
        isA ? "bg-tier-a-bg text-tier-a-ink" : "bg-tier-b-bg text-tier-b-ink"
      }`}
    >
      Tier {tier}
    </span>
  );
}

export default function Assistant({ snapshotDate }: { snapshotDate: string | null }) {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [pending, setPending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [turns, pending]);

  async function send(question: string) {
    const text = question.trim();
    if (!text || pending) return;
    setQ("");
    setPending(true);
    setTurns((t) => [...t, { question: text, reply: null }]);
    try {
      const reply = await askAssistant(text);
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, reply } : turn)));
    } catch {
      setTurns((t) =>
        t.map((turn, i) =>
          i === t.length - 1
            ? { ...turn, error: "Could not reach the API. Is it running on port 8020?" }
            : turn,
        ),
      );
    } finally {
      setPending(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full bg-navy px-4 py-3 text-sm font-medium text-white shadow-lg transition-colors hover:bg-navy-panel"
        aria-label="Open the corpus assistant"
      >
        <span aria-hidden>&#9873;</span> Ask about this data
      </button>
    );
  }

  return (
    <div
      role="dialog"
      aria-label="Corpus assistant"
      className="fixed bottom-5 right-5 z-50 flex h-[min(32rem,calc(100vh-3rem))] w-[min(24rem,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
    >
      <div className="flex items-start justify-between gap-2 border-b border-border bg-navy px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-white">Ask about this data</div>
          <div className="text-[11px] text-on-navy-muted">
            Every figure read from the corpus &mdash; nothing is generated.
          </div>
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded-md px-2 py-1 text-sm text-on-navy-muted hover:text-white"
          aria-label="Close the assistant"
        >
          &times;
        </button>
      </div>

      <div ref={logRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {turns.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-ink-muted">
              I answer from the built corpus only. I cannot rank members by flag count &mdash; flags
              belong to works, not to people.
            </p>
            <div className="flex flex-wrap gap-1.5">
              {OPENERS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-full border border-border px-2.5 py-1 text-xs text-ink-2 hover:border-ink-muted"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) => (
          <div key={i} className="space-y-2">
            <div className="ml-auto w-fit max-w-[85%] rounded-lg bg-surface-sunken px-3 py-2 text-sm text-ink-2">
              {turn.question}
            </div>

            {turn.error && <div className="text-sm text-ink-muted">{turn.error}</div>}

            {turn.reply && (
              <div
                className={`space-y-2 rounded-lg px-3 py-2 text-sm ${
                  turn.reply.declined
                    ? "border border-accent-soft bg-accent-soft/30 text-ink-2"
                    : "text-ink-2"
                }`}
              >
                {typeof turn.reply.data.tier === "string" && (
                  <TierPill tier={turn.reply.data.tier} />
                )}
                <p className="leading-relaxed">{turn.reply.answer}</p>

                {turn.reply.links.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {turn.reply.links.map((l) => (
                      <Link
                        key={l.href}
                        href={l.href}
                        onClick={() => setOpen(false)}
                        className="rounded-full border border-border px-2.5 py-1 text-xs text-ink-2 hover:border-ink-muted"
                      >
                        {l.label} &rarr;
                      </Link>
                    ))}
                  </div>
                )}

                {turn.reply.suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {turn.reply.suggestions.map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => send(s)}
                        className="rounded-full bg-surface-sunken px-2.5 py-1 text-xs text-ink-muted hover:text-ink-2"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {pending && <div className="text-sm text-ink-muted">Reading the corpus&hellip;</div>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(q);
        }}
        className="border-t border-border p-3"
      >
        <div className="flex gap-2">
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ask about the corpus&hellip;"
            maxLength={300}
            className="flex-1 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm focus:border-ink-muted focus:outline-none"
          />
          <button
            type="submit"
            disabled={pending || !q.trim()}
            className="rounded-md bg-navy px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-panel disabled:opacity-40"
          >
            Ask
          </button>
        </div>
        {snapshotDate && (
          <p className="mt-2 text-[11px] text-ink-muted">
            Answers read from the {snapshotDate} snapshot.
          </p>
        )}
      </form>
    </div>
  );
}
