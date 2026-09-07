"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { addOverride, removeOverride, type Override } from "@/lib/api";

export default function ReviewOverride({ workId, override }: { workId: string; override: Override }) {
  const router = useRouter();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function markReviewed() {
    setBusy(true);
    setError(null);
    try {
      await addOverride(workId, note.trim() || null);
      router.refresh();
    } catch {
      setError("Could not save the review — try again.");
    } finally {
      setBusy(false);
    }
  }

  async function undoReview() {
    setBusy(true);
    setError(null);
    try {
      await removeOverride(workId);
      router.refresh();
    } catch {
      setError("Could not undo the review — try again.");
    } finally {
      setBusy(false);
    }
  }

  if (override) {
    return (
      <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
        <div className="flex items-center justify-between gap-3">
          <div>
            <strong>Reviewed — explained.</strong>{" "}
            <span className="text-emerald-700">
              Marked {new Date(override.reviewed_at).toLocaleString("en-IN")}. Hidden from the default queue; the
              flags and evidence above stay on record.
            </span>
            {override.note && <p className="mt-1 text-emerald-800">{override.note}</p>}
          </div>
          <button
            onClick={undoReview}
            disabled={busy}
            className="shrink-0 rounded-md border border-emerald-300 bg-surface px-2.5 py-1 text-xs font-medium text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
          >
            Undo
          </button>
        </div>
        {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-surface-sunken px-4 py-3 text-sm">
      <p className="mb-2 text-ink-muted">
        A reviewer who has checked this work and found the flag adequately explained can mark it reviewed. This
        hides it from the default queue — it does not delete the flag or the evidence.
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Optional note — what explains this flag (site visit, records checked, etc.)"
          className="flex-1 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm"
        />
        <button
          onClick={markReviewed}
          disabled={busy}
          className="shrink-0 rounded-md bg-navy px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-panel disabled:opacity-50"
        >
          Mark reviewed — explained
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
    </div>
  );
}
