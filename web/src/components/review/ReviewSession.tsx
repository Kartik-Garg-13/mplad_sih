"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addOverride,
  getWorkDetail,
  type Detector,
  type Flag,
  type FlagRow,
  type WorkDetail,
} from "@/lib/api";

function fmtInr(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "—";
  const abs = Math.abs(amount);
  if (abs >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000) return `₹${(amount / 1_00_000).toFixed(2)}L`;
  return `₹${amount.toLocaleString("en-IN")}`;
}

function FlagList({ flags, benignById, tierClass }: { flags: Flag[]; benignById: Record<string, string>; tierClass: string }) {
  if (flags.length === 0) return null;
  return (
    <ul className="space-y-2">
      {flags.map((f, i) => (
        <li key={i} className={`rounded-md border px-3 py-2 text-sm text-ink-2 ${tierClass}`}>
          <div>
            <span className="mr-2 font-mono text-xs font-semibold">{f.detector}</span>
            {f.evidence}
          </div>
          {benignById[f.detector] && (
            <p className="mt-1.5 border-t border-current/10 pt-1.5 text-xs text-ink-muted">
              <span className="font-medium">Plausible innocent explanation:</span> {benignById[f.detector]}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

const SHORTCUTS: [string, string][] = [
  ["J", "Next work"],
  ["K", "Previous work"],
  ["R", "Mark reviewed — explained, then advance"],
  ["S", "Skip — advance without marking"],
  ["?", "Toggle this help"],
];

export default function ReviewSession({
  queue,
  totalMatchingFilters,
  detectors,
  filters,
}: {
  queue: FlagRow[];
  totalMatchingFilters: number;
  detectors: Detector[];
  filters: Record<string, string | undefined>;
}) {
  const benignById = useMemo(
    () => Object.fromEntries(detectors.map((d) => [d.id, d.benign_explanation])),
    [detectors]
  );

  // A plain-language readout of which /flags filters this session inherited
  // — so "Reviewing: ..." tells a reviewer what scope they're actually
  // working through, the same filters they set on the flag list itself.
  const filterSummary = useMemo(() => {
    const parts: string[] = [];
    if (filters.tier) parts.push(`Tier ${filters.tier}`);
    if (filters.detector) parts.push(filters.detector);
    if (filters.state) parts.push(filters.state);
    if (filters.category) parts.push(filters.category);
    if (filters.source) parts.push(`source: ${filters.source}`);
    if (filters.search) parts.push(`"${filters.search}"`);
    return parts.length > 0 ? parts.join(" · ") : null;
  }, [filters]);

  const [index, setIndex] = useState(0);
  const [detail, setDetail] = useState<WorkDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showShortcuts, setShowShortcuts] = useState(false);
  // Which work_ids were marked "reviewed — explained" in this session — the
  // batch itself stays fixed (see the page component's note on why), so
  // this local set is what drives both the progress count and the small
  // per-card "reviewed" badge, without needing to re-fetch the queue.
  const [reviewedThisSession, setReviewedThisSession] = useState<Set<string>>(new Set());

  const current = queue[index];
  const isLast = index >= queue.length - 1;
  const isFirst = index === 0;

  // Fetch full detail (flags with evidence, benign explanations rely on the
  // `detectors` prop already in hand) for whichever work is current — the
  // batch list itself only carries the flag list's summary shape.
  useEffect(() => {
    let cancelled = false;
    // Nested function, not bare top-level setState calls — same pattern as
    // useInView.ts elsewhere in this codebase: keeps the lint rule against
    // synchronous setState-in-effect-body happy without changing behavior,
    // since these still run once per work_id change, before the fetch.
    function startLoading() {
      setLoading(true);
      setNote("");
      setError(null);
    }
    startLoading();
    getWorkDetail(current.work_id)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load this work — try Next or Previous.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [current.work_id]);

  const goNext = useCallback(() => {
    setIndex((i) => Math.min(queue.length - 1, i + 1));
  }, [queue.length]);

  const goPrev = useCallback(() => {
    setIndex((i) => Math.max(0, i - 1));
  }, []);

  const markReviewed = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await addOverride(current.work_id, note.trim() || null);
      setReviewedThisSession((s) => new Set(s).add(current.work_id));
      if (!isLast) goNext();
    } catch {
      setError("Could not save the review — try again.");
    } finally {
      setBusy(false);
    }
  }, [current.work_id, note, isLast, goNext]);

  // Keyboard shortcuts — ignored while focus is in the note field so typing
  // a note doesn't accidentally fire "R"eviewed or "S"kip mid-sentence.
  const noteRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (document.activeElement === noteRef.current) {
        if (e.key === "Escape") noteRef.current?.blur();
        return;
      }
      switch (e.key.toLowerCase()) {
        case "j":
          goNext();
          break;
        case "k":
          goPrev();
          break;
        case "s":
          if (!isLast) goNext();
          break;
        case "r":
          if (!busy) markReviewed();
          break;
        case "?":
          setShowShortcuts((v) => !v);
          break;
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [goNext, goPrev, isLast, busy, markReviewed]);

  const reviewedCount = reviewedThisSession.size;
  const leftCount = queue.length - reviewedCount;
  const alreadyReviewed = reviewedThisSession.has(current.work_id);

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <div className="mb-5 flex items-center justify-between gap-4">
        <Link href="/flags" className="text-sm text-ink-muted hover:text-ink-2">
          &larr; Exit review
        </Link>
        <button
          onClick={() => setShowShortcuts((v) => !v)}
          className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-ink-muted hover:bg-surface-sunken"
        >
          Keyboard shortcuts (?)
        </button>
      </div>

      {filterSummary && (
        <p className="mb-3 text-xs text-ink-muted">
          Reviewing: <span className="font-medium text-ink-2">{filterSummary}</span>
        </p>
      )}

      <div className="mb-5">
        <div className="flex items-baseline justify-between text-sm">
          <span className="font-semibold text-ink-2">
            {reviewedCount} of {queue.length} reviewed
          </span>
          <span className="text-ink-muted">
            {leftCount} left this session
            {totalMatchingFilters > queue.length && ` · ${totalMatchingFilters.toLocaleString("en-IN")} match these filters in total`}
          </span>
        </div>
        <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken">
          <div
            className="h-full rounded-full bg-accent-ink transition-[width]"
            style={{ width: `${(reviewedCount / queue.length) * 100}%` }}
          />
        </div>
      </div>

      {showShortcuts && (
        <div className="mb-5 rounded-lg border border-border bg-surface-sunken p-4 text-sm">
          <div className="mb-2 font-semibold text-ink-2">Keyboard shortcuts</div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            {SHORTCUTS.map(([key, desc]) => (
              <div key={key} className="contents">
                <dt className="font-mono text-xs font-semibold text-ink-2">{key}</dt>
                <dd className="text-ink-muted">{desc}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <div className="rounded-lg border border-border bg-surface p-5">
        <div className="mb-1 flex items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold leading-snug text-ink-2">
              {current.description || current.work_id}
            </h1>
            <p className="mt-0.5 font-mono text-xs text-ink-muted">{current.work_id}</p>
          </div>
          <span className="shrink-0 text-xs text-ink-muted">
            {index + 1} / {queue.length}
          </span>
        </div>

        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">State</dt>
            <dd className="text-ink-2">{current.state ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">MP</dt>
            <dd className="text-ink-2">{current.mp_name ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Amount</dt>
            <dd className="tabular-nums text-ink-2">{fmtInr(current.sanction_amount ?? current.recommended_amount)}</dd>
          </div>
        </dl>

        <div className="mt-4 border-t border-border pt-4">
          {loading && <p className="text-sm text-ink-muted">Loading flags&hellip;</p>}
          {!loading && detail && (
            <div className="space-y-4">
              <FlagList
                flags={detail.flags.filter((f) => f.tier === "A")}
                benignById={benignById}
                tierClass="border-rose-100 bg-rose-50/50"
              />
              <FlagList
                flags={detail.flags.filter((f) => f.tier === "B")}
                benignById={benignById}
                tierClass="border-amber-100 bg-amber-50/50"
              />
            </div>
          )}
        </div>

        <div className="mt-5 border-t border-border pt-4">
          {alreadyReviewed ? (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              Marked reviewed — explained this session.{" "}
              <Link href={`/works/${current.work_id}`} className="underline">
                View work
              </Link>
            </div>
          ) : (
            <>
              <input
                ref={noteRef}
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Optional note — what explains this flag&hellip;"
                className="w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm"
              />
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  onClick={markReviewed}
                  disabled={busy}
                  className="rounded-md bg-navy px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-panel disabled:opacity-50"
                >
                  Mark reviewed — explained
                  <span className="ml-1.5 font-mono text-[10px] opacity-70">R</span>
                </button>
                <button
                  onClick={() => !isLast && goNext()}
                  disabled={isLast}
                  className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-ink-muted hover:bg-surface-sunken disabled:opacity-50"
                >
                  Skip
                  <span className="ml-1.5 font-mono text-[10px] opacity-70">S</span>
                </button>
              </div>
            </>
          )}
          {error && <p className="mt-1.5 text-xs text-rose-600">{error}</p>}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <button
          onClick={goPrev}
          disabled={isFirst}
          className="rounded-md border border-border px-3 py-1.5 text-sm text-ink-muted hover:bg-surface-sunken disabled:opacity-40"
        >
          &larr; Previous <span className="font-mono text-[10px] opacity-70">K</span>
        </button>
        {isLast ? (
          <span className="text-sm text-ink-muted">End of this batch</span>
        ) : (
          <button
            onClick={goNext}
            className="rounded-md border border-border px-3 py-1.5 text-sm text-ink-muted hover:bg-surface-sunken"
          >
            Next <span className="font-mono text-[10px] opacity-70">J</span> &rarr;
          </button>
        )}
      </div>
    </main>
  );
}
