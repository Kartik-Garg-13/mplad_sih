"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { removeOverride } from "@/lib/api";

/** The reversibility half of plan §08, rule 7 — a reviewed work is
 * suppressed from the queue, never deleted, and this button is what makes
 * that promise actually usable rather than a claim nobody can act on. */
export default function UndoReviewButton({ workId }: { workId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function undo() {
    setBusy(true);
    setError(null);
    try {
      await removeOverride(workId);
      router.refresh();
    } catch {
      setError("Could not undo — try again.");
      setBusy(false);
    }
  }

  return (
    <div className="text-right">
      <button
        onClick={undo}
        disabled={busy}
        className="rounded-md border border-emerald-300 bg-surface px-2.5 py-1 text-xs font-medium text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
      >
        {busy ? "Undoing…" : "Undo"}
      </button>
      {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
    </div>
  );
}
