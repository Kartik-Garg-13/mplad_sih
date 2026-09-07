import Link from "next/link";
import { getOverrides } from "@/lib/api";
import UndoReviewButton from "@/components/UndoReviewButton";

function fmtInr(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "—";
  const abs = Math.abs(amount);
  if (abs >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000) return `₹${(amount / 1_00_000).toFixed(2)}L`;
  return `₹${amount.toLocaleString("en-IN")}`;
}

type SearchParams = { [key: string]: string | string[] | undefined };
function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function ReviewedPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const search = one(sp.search);
  const { overrides } = await getOverrides({ search });

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8">
        <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-2">Reviewed</h1>
        <p className="mt-1 max-w-2xl text-sm text-ink-muted">
          Every work a reviewer has marked &ldquo;reviewed &mdash; explained.&rdquo; Suppressed from the flag
          queue, never deleted &mdash; the flag and its evidence stay on the work detail page, and any of these
          can be undone.
        </p>
        <p className="mt-3 text-sm text-ink-muted">
          <span className="font-semibold text-ink-2">{overrides.length.toLocaleString("en-IN")}</span>{" "}
          work{overrides.length === 1 ? "" : "s"} reviewed
          {search && (
            <>
              {" "}
              matching &ldquo;{search}&rdquo; &mdash;{" "}
              <Link href="/reviewed" className="underline decoration-border underline-offset-2 hover:decoration-ink-muted">
                clear
              </Link>
            </>
          )}
        </p>
      </header>

      <form className="mb-6 flex gap-2">
        <input
          type="search"
          name="search"
          defaultValue={search ?? ""}
          placeholder="Search description, MP, agency…"
          className="w-72 rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
        />
        <button type="submit" className="rounded-md bg-navy px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-panel">
          Search
        </button>
      </form>

      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full min-w-[900px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <th className="px-3 py-2">Work</th>
              <th className="px-3 py-2">State / Agency</th>
              <th className="px-3 py-2">Note</th>
              <th className="px-3 py-2">Reviewed</th>
              <th className="px-3 py-2 text-right">Amount</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {overrides.map((o) => (
              <tr key={o.work_id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td className="px-3 py-2 align-top">
                  <Link
                    href={`/works/${o.work_id}`}
                    className="font-medium text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-600"
                  >
                    {o.work?.description || o.work_id}
                  </Link>
                  <div className="mt-0.5 font-mono text-[11px] text-slate-500">{o.work_id}</div>
                </td>
                <td className="px-3 py-2 align-top text-slate-600">
                  {o.work ? (
                    <>
                      <div>{o.work.state ?? "—"}</div>
                      <div className="text-[11px] text-slate-500">{o.work.implementing_agency ?? "—"}</div>
                    </>
                  ) : (
                    <span className="text-slate-400">no longer in corpus</span>
                  )}
                </td>
                <td className="max-w-[260px] px-3 py-2 align-top text-slate-600">{o.note || "—"}</td>
                <td className="whitespace-nowrap px-3 py-2 align-top text-slate-600">
                  {new Date(o.reviewed_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right align-top tabular-nums text-slate-700">
                  {fmtInr(o.work?.sanction_amount ?? o.work?.recommended_amount)}
                </td>
                <td className="px-3 py-2 align-top">
                  <UndoReviewButton workId={o.work_id} />
                </td>
              </tr>
            ))}
            {overrides.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-10 text-center text-sm text-slate-500">
                  {search ? (
                    <>
                      No reviewed work matches &ldquo;{search}&rdquo;.{" "}
                      <Link href="/reviewed" className="underline decoration-slate-300 underline-offset-2 hover:decoration-slate-600">
                        Show all reviewed
                      </Link>
                      .
                    </>
                  ) : (
                    <>
                      Nothing reviewed yet. Mark a flag &ldquo;reviewed &mdash; explained&rdquo; from any work
                      detail page, or work through the{" "}
                      <Link href="/flags" className="underline decoration-slate-300 underline-offset-2 hover:decoration-slate-600">
                        flag list
                      </Link>
                      .
                    </>
                  )}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
