"use client";

import { useEffect, useRef, useState } from "react";
import {
  createDataset,
  deleteDataset,
  getDatasets,
  getRebuildJob,
  type DatasetsResponse,
  type RebuildJob,
} from "@/lib/api";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

/** Polls a rebuild job until it settles, calling onSettle once with the
 * final state. A rebuild is a real ~15s-to-a-minute pipeline run (13
 * detectors, the agency graph, the stall model) — there is no push channel
 * for it, so polling is the honest way to reflect progress. */
function usePollJob(onSettle: () => void) {
  const [job, setJob] = useState<RebuildJob | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function stop() {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }

  function poll(id: string) {
    stop();
    timer.current = setTimeout(async () => {
      try {
        const next = await getRebuildJob(id);
        setJob(next);
        if (next.status === "running") {
          poll(id);
        } else {
          onSettle();
        }
      } catch {
        // A transient fetch error while the API is mid-rebuild (the
        // connection is briefly closed for the unlink+recreate) is
        // expected, not fatal — just try again shortly.
        poll(id);
      }
    }, 1200);
  }

  function start(initial: RebuildJob) {
    setJob(initial);
    poll(initial.id);
  }

  function clear() {
    stop();
    setJob(null);
  }

  useEffect(() => stop, []);

  return { job, start, clear };
}

export default function DatasetsClient({ initial }: { initial: DatasetsResponse }) {
  const [data, setData] = useState(initial);
  const [label, setLabel] = useState("");
  const [house, setHouse] = useState("");
  const [term, setTerm] = useState("");
  const [note, setNote] = useState("");
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  const { job, start, clear } = usePollJob(async () => {
    try {
      setData(await getDatasets());
    } catch {
      // Keep the last-known list rather than blanking the page on a
      // one-off refresh failure right after a rebuild.
    }
  });

  const rebuilding = job?.status === "running" || data.rebuild?.status === "running";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!files.recommended) {
      setError('"Works Recommended" is required — every other file builds on it.');
      return;
    }
    if (!label.trim()) {
      setError("Give this batch a name so it can be told apart later.");
      return;
    }

    const form = new FormData();
    form.set("label", label.trim());
    form.set("house", house.trim());
    form.set("term", term.trim());
    form.set("note", note.trim());
    for (const stage of data.stages.map((s) => s.key)) {
      const f = files[stage];
      if (f) form.set(stage, f);
    }

    setSubmitting(true);
    try {
      const result = await createDataset(form);
      start(result.job);
      setLabel("");
      setHouse("");
      setTerm("");
      setNote("");
      setFiles({});
      formRef.current?.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the dataset — try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(key: string) {
    setError(null);
    setPendingDelete(null);
    try {
      const result = await deleteDataset(key);
      start(result.job);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove the dataset — try again.");
    }
  }

  const activeJob = job ?? data.rebuild;

  return (
    <div className="mt-6 space-y-10">
      {activeJob && activeJob.status === "running" && (
        <div className="flex items-center gap-3 rounded-xl border border-accent-ink/20 bg-accent-soft px-5 py-4 text-sm text-ink-2">
          <span
            className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-accent-ink/30 border-t-accent-ink"
            aria-hidden
          />
          <div>
            <div className="font-medium">{activeJob.reason}</div>
            <div className="text-ink-muted">
              {activeJob.step_label} (step {activeJob.step + 1} of {activeJob.total_steps}) — every detector re-runs
              against the full corpus, so this touches the whole site briefly.
            </div>
          </div>
        </div>
      )}
      {activeJob && activeJob.status === "error" && (
        <div className="rounded-xl border border-tier-a-ink/25 bg-tier-a-bg px-5 py-4 text-sm text-tier-a-ink">
          <div className="font-medium">The rebuild failed.</div>
          <div className="mt-1">{activeJob.error}</div>
        </div>
      )}
      {activeJob && activeJob.status === "done" && job && (
        <div className="flex items-center justify-between rounded-xl border border-reviewed-ink/25 bg-reviewed-bg px-5 py-3 text-sm text-reviewed-ink">
          <span>{activeJob.reason} — done. The corpus is back online.</span>
          <button onClick={clear} className="text-xs underline underline-offset-2 hover:no-underline">
            Dismiss
          </button>
        </div>
      )}

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-widest text-ink-muted">
          Sources in the corpus
        </h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.sources.map((s) => (
            <div key={s.key} className="rounded-xl border border-border bg-surface p-5">
              <div className="flex items-start justify-between gap-2">
                <div className="font-medium text-ink-2">{s.label}</div>
                {s.builtin ? (
                  <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-ink-muted">
                    built-in
                  </span>
                ) : (
                  <span className="shrink-0 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-ink">
                    uploaded
                  </span>
                )}
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <div>
                  <dt className="text-xs text-ink-muted">Works</dt>
                  <dd className="tabular-nums text-ink-2">{s.n_works.toLocaleString("en-IN")}</dd>
                </div>
                <div>
                  <dt className="text-xs text-ink-muted">Flagged</dt>
                  <dd className="tabular-nums text-ink-2">{s.n_flagged.toLocaleString("en-IN")}</dd>
                </div>
              </dl>
              {!s.builtin && (
                <div className="mt-2 text-xs text-ink-muted">Added {fmtDate(s.created_at)}</div>
              )}
              {s.note && <p className="mt-2 text-xs text-ink-muted">{s.note}</p>}
              <div className="mt-4 flex items-center gap-3">
                <a
                  href={`/flags?source=${encodeURIComponent(s.key)}`}
                  className="text-xs font-medium text-accent-ink underline underline-offset-2 hover:no-underline"
                >
                  View this source&rsquo;s flags &rarr;
                </a>
                {!s.builtin && (
                  <button
                    onClick={() => setPendingDelete(s.key)}
                    disabled={rebuilding}
                    className="ml-auto text-xs text-ink-muted hover:text-tier-a-ink disabled:opacity-40"
                  >
                    Remove
                  </button>
                )}
              </div>
              {pendingDelete === s.key && (
                <div className="mt-3 rounded-lg border border-tier-a-ink/20 bg-tier-a-bg p-3 text-xs text-tier-a-ink">
                  <p>Remove &ldquo;{s.label}&rdquo; and rebuild the corpus without it?</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => onDelete(s.key)}
                      className="rounded-md bg-tier-a-ink px-2.5 py-1 font-medium text-white"
                    >
                      Remove
                    </button>
                    <button onClick={() => setPendingDelete(null)} className="rounded-md px-2.5 py-1 text-ink-muted">
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-widest text-ink-muted">Add a dataset</h2>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">
          Upload the same eSAKSHI exports the built-in corpus uses. &ldquo;Works Recommended&rdquo; is required
          &mdash; it&rsquo;s the spine every other file joins onto. Everything else is optional and only unlocks
          the detectors that need it. Adding a batch re-runs the full pipeline (all 13 detectors, the agency
          graph, the stall-risk model) so peer-relative detectors compare your works against the whole corpus,
          not just the new rows &mdash; that takes under a minute, and the site stays read-only until it
          finishes.
        </p>

        <form ref={formRef} onSubmit={onSubmit} className="mt-5 rounded-xl border border-border bg-surface p-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <label className="block text-sm">
              <span className="text-ink-muted">Batch name *</span>
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g. Sikkim pilot, 2026"
                className="mt-1 w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-ink-muted">House / constituency</span>
              <input
                type="text"
                value={house}
                onChange={(e) => setHouse(e.target.value)}
                placeholder="optional"
                className="mt-1 w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink-2"
              />
            </label>
            <label className="block text-sm">
              <span className="text-ink-muted">Term</span>
              <input
                type="text"
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                placeholder="optional"
                className="mt-1 w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink-2"
              />
            </label>
          </div>

          <label className="mt-4 block text-sm">
            <span className="text-ink-muted">Note</span>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="optional — where this batch came from"
              className="mt-1 w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink-2"
            />
          </label>

          <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {data.stages.map((stage) => (
              <div key={stage.key} className="rounded-lg border border-border-soft bg-surface-sunken p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-ink-2">{stage.label}</span>
                  {stage.required && (
                    <span className="rounded-full bg-tier-b-bg px-2 py-0.5 text-[10px] font-medium text-tier-b-ink">
                      required
                    </span>
                  )}
                </div>
                <p className="mt-1 text-xs text-ink-muted">{stage.unlocks}</p>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) =>
                    setFiles((prev) => ({ ...prev, [stage.key]: e.target.files?.[0] ?? null }))
                  }
                  className="mt-2 block w-full text-xs text-ink-muted file:mr-3 file:rounded-md file:border-0 file:bg-navy-panel file:px-2.5 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-navy"
                />
              </div>
            ))}
          </div>

          {error && <p className="mt-4 text-sm text-tier-a-ink">{error}</p>}

          <button
            type="submit"
            disabled={submitting || rebuilding}
            className="mt-6 rounded-md bg-accent px-4 py-2 text-sm font-medium text-navy-deep hover:bg-accent/90 disabled:opacity-50"
          >
            {submitting ? "Uploading…" : rebuilding ? "A rebuild is already running…" : "Add dataset & rebuild"}
          </button>
        </form>
      </section>
    </div>
  );
}
