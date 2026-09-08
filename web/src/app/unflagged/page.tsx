import Link from "next/link";
import { getMeta, getStats, getUnflagged } from "@/lib/api";
import { pageParam } from "@/lib/params";
import Pagination from "@/components/site/Pagination";

function fmtInr(amount: number | null): string {
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

export default async function UnflaggedPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const page = pageParam(sp.page);
  const state = one(sp.state);
  const category = one(sp.category);
  const search = one(sp.search);
  const source = one(sp.source);
  const includeUnsanctioned = one(sp.include_unsanctioned);

  const [res, meta, stats] = await Promise.all([
    getUnflagged({ page, page_size: "25", state, category, search, source, include_unsanctioned: includeUnsanctioned }),
    getMeta(),
    getStats(),
  ]);

  const buildHref = (overrides: Record<string, string | undefined>) => {
    const params = new URLSearchParams();
    const merged = { state, category, search, source, include_unsanctioned: includeUnsanctioned, page: "1", ...overrides };
    for (const [k, v] of Object.entries(merged)) {
      if (v) params.set(k, v);
    }
    return `/unflagged?${params.toString()}`;
  };

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-2">No flags</h1>
            <p className="mt-1 max-w-2xl text-sm text-ink-muted">
              Works that every detector ran against and none flagged. The other side of the{" "}
              <Link href="/flags" className="underline decoration-border underline-offset-2 hover:decoration-ink-muted">
                flag list
              </Link>{" "}
              &mdash; useful for checking what &ldquo;normal&rdquo; looks like in a category or state.
            </p>
          </div>
          <div className="text-right text-sm text-ink-muted">
            <div>
              <span className="font-semibold text-ink-2">{res.total.toLocaleString("en-IN")}</span> with no flags
            </div>
            <div>
              of <span className="font-semibold text-ink-2">{stats.total_works.toLocaleString("en-IN")}</span> works
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-border bg-surface-sunken px-3 py-2 text-xs text-ink-muted">
          By default this counts only works that were actually <strong className="text-ink-2">evaluated</strong> &mdash;
          a sanctioned work every detector examined and cleared. Works with no sanction amount yet
          (&ldquo;not yet sanctioned&rdquo;) are skipped by nearly every detector by construction, so counting them
          as clean would mean counting works that were never inspected.{" "}
          <Link
            href={buildHref({ include_unsanctioned: includeUnsanctioned === "true" ? undefined : "true" })}
            className="underline decoration-border underline-offset-2 hover:decoration-ink-muted"
          >
            {includeUnsanctioned === "true" ? "Hide not-yet-sanctioned works" : "Include not-yet-sanctioned works"}
          </Link>
        </div>
      </header>

      <form className="mb-6 grid grid-cols-2 gap-3 rounded-lg border border-border bg-surface-sunken p-4 sm:grid-cols-4">
        <select name="state" defaultValue={state ?? ""} className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm">
          <option value="">All states</option>
          {meta.states.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          name="category"
          defaultValue={category ?? ""}
          className="col-span-2 rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
        >
          <option value="">All categories</option>
          {meta.categories.map((c) => (
            <option key={c} value={c}>
              {c.length > 60 ? c.slice(0, 60) + "…" : c}
            </option>
          ))}
        </select>
        {includeUnsanctioned === "true" && <input type="hidden" name="include_unsanctioned" value="true" />}
        <input
          type="search"
          name="search"
          defaultValue={search ?? ""}
          placeholder="Search description, MP, agency…"
          className="col-span-2 rounded-md border border-border bg-surface px-2 py-1.5 text-sm sm:col-span-1"
        />
        <button type="submit" className="rounded-md bg-navy px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-panel">
          Filter
        </button>
      </form>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[820px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-sunken text-left text-xs font-medium uppercase tracking-wide text-ink-muted">
              <th className="px-3 py-2">Work</th>
              <th className="px-3 py-2">State / MP</th>
              <th className="px-3 py-2">Category</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {res.results.map((row, i) => (
              <tr key={`${i}-${row.work_id}`} className="border-b border-border-soft last:border-0 hover:bg-surface-sunken">
                <td className="px-3 py-2 align-top">
                  <Link
                    href={`/works/${row.work_id}`}
                    className="font-medium text-ink-2 underline decoration-border underline-offset-2 hover:decoration-ink-muted"
                  >
                    {row.description || row.work_id}
                  </Link>
                  <div className="mt-0.5 font-mono text-[11px] text-ink-muted">{row.work_id}</div>
                </td>
                <td className="px-3 py-2 align-top text-ink-muted">
                  <div>{row.state ?? "—"}</div>
                  <div className="text-[11px]">{row.mp_name ?? "—"}</div>
                </td>
                <td className="max-w-[220px] px-3 py-2 align-top text-ink-muted">{row.category ?? "—"}</td>
                <td className="px-3 py-2 align-top text-ink-muted">{row.work_status ?? "—"}</td>
                <td className="whitespace-nowrap px-3 py-2 text-right align-top tabular-nums text-ink-2">
                  {fmtInr(row.sanction_amount ?? row.recommended_amount)}
                </td>
              </tr>
            ))}
            {res.results.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center text-sm text-ink-muted">
                  No unflagged works match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Pagination
        basePath="/unflagged"
        params={{ state, category, search, source, include_unsanctioned: includeUnsanctioned }}
        page={res.page}
        totalPages={res.total_pages}
        label="Works with no flags"
        summary={`${res.total.toLocaleString("en-IN")} works with no flags`}
      />
    </main>
  );
}
