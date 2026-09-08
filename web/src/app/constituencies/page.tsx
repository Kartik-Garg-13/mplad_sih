import Link from "next/link";
import { getConstituencies } from "@/lib/api";
import Pagination from "@/components/site/Pagination";

function fmtInr(amount: number | null): string {
  if (amount === null || amount === undefined) return "—";
  const abs = Math.abs(amount);
  if (abs >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000) return `₹${(amount / 1_00_000).toFixed(2)}L`;
  return `₹${amount.toLocaleString("en-IN")}`;
}

function fmtPct(v: number | null): string {
  return v === null || v === undefined ? "—" : `${(v * 100).toFixed(0)}%`;
}

type SearchParams = { [key: string]: string | string[] | undefined };
function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "total_sanctioned", label: "Total sanctioned" },
  { value: "completion_rate", label: "Completion rate" },
  { value: "fund_utilisation", label: "Fund utilisation" },
  { value: "unspent_balance", label: "Unspent balance" },
  { value: "n_sanctioned", label: "Works sanctioned" },
];

export default async function ConstituenciesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const page = one(sp.page) ?? "1";
  const search = one(sp.search);
  const sort = one(sp.sort) ?? "total_sanctioned";
  const direction = one(sp.direction) ?? "desc";

  const constituencies = await getConstituencies({ page, page_size: "25", search, sort, direction });

  const buildHref = (overrides: Record<string, string | undefined>) => {
    const params = new URLSearchParams();
    const merged = { search, sort, direction, page: "1", ...overrides };
    for (const [k, v] of Object.entries(merged)) {
      if (v) params.set(k, v);
    }
    return `/constituencies?${params.toString()}`;
  };

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <Link href="/flags" className="text-sm text-ink-muted hover:text-ink-2">
        &larr; Flag list
      </Link>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink-2">Constituency scorecard</h1>
      <p className="mt-1 mb-2 max-w-3xl text-sm text-ink-muted">
        Lok Sabha constituencies only &mdash; Rajya Sabha members have no constituency. This is an{" "}
        <strong>implementation-performance measure, not an integrity measure</strong>: a low completion rate or
        slow fund utilisation usually reflects district-administration capacity or a young term, not misconduct.
        None of these numbers appear as flags anywhere else in this app.
      </p>
      <p className="mb-6 max-w-3xl text-xs text-ink-muted">
        Two things the plan called for aren&rsquo;t here: a constituency-boundary map (no GeoJSON was ever pulled
        for this) and a population-normalised works-per-lakh rate (no population dataset was ever sourced). Both
        left out rather than faked.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-xs uppercase tracking-wide text-ink-muted">Sort by</span>
        {SORT_OPTIONS.map((opt) => (
          <Link
            key={opt.value}
            href={buildHref({ sort: opt.value, direction: sort === opt.value && direction === "desc" ? "asc" : "desc" })}
            className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
              sort === opt.value
                ? "border-navy bg-navy text-white"
                : "border-border bg-surface text-ink-muted hover:border-border"
            }`}
          >
            {opt.label} {sort === opt.value && (direction === "desc" ? "↓" : "↑")}
          </Link>
        ))}
      </div>

      <form className="mb-4 flex gap-2">
        <input type="hidden" name="sort" value={sort} />
        <input type="hidden" name="direction" value={direction} />
        <input
          type="search"
          name="search"
          defaultValue={search ?? ""}
          placeholder="Search constituency or MP…"
          className="w-72 rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
        />
        <button type="submit" className="rounded-md bg-navy px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-panel">
          Search
        </button>
      </form>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[900px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-sunken text-left text-xs font-medium uppercase tracking-wide text-ink-muted">
              <th className="px-3 py-2">Constituency</th>
              <th className="px-3 py-2 text-right">Sanctioned</th>
              <th className="px-3 py-2 text-right">Completion</th>
              <th className="px-3 py-2 text-right">Median days</th>
              <th className="px-3 py-2 text-right">Fund used</th>
              <th className="px-3 py-2 text-right">Unspent</th>
              <th className="px-3 py-2">Dominant sector</th>
            </tr>
          </thead>
          <tbody>
            {constituencies.results.map((c) => {
              const noWorks = c.n_sanctioned === 0;
              return (
                <tr key={`${c.state}-${c.constituency}`} className="border-b border-border-soft last:border-0 hover:bg-surface-sunken">
                  <td className="px-3 py-2 align-top">
                    <div className="font-medium text-ink-2">{c.constituency}</div>
                    <div className="text-[11px] text-ink-muted">
                      {c.state} &middot; {c.mp_name ?? "—"}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right align-top tabular-nums text-ink-muted">{c.n_sanctioned}</td>
                  <td className="px-3 py-2 text-right align-top tabular-nums text-ink-muted">
                    {noWorks ? <span className="text-[11px] text-ink-muted">no works yet</span> : fmtPct(c.completion_rate)}
                  </td>
                  <td className="px-3 py-2 text-right align-top tabular-nums text-ink-muted">
                    {c.median_days_to_complete !== null ? c.median_days_to_complete.toFixed(0) : "—"}
                  </td>
                  <td className="px-3 py-2 text-right align-top tabular-nums text-ink-muted">{fmtPct(c.fund_utilisation)}</td>
                  <td className="px-3 py-2 text-right align-top tabular-nums text-ink-2">{fmtInr(c.unspent_balance)}</td>
                  <td className="max-w-[200px] px-3 py-2 align-top text-ink-muted">{c.dominant_category ?? "—"}</td>
                </tr>
              );
            })}
            {constituencies.results.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-10 text-center text-sm text-ink-muted">
                  No constituencies match this search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Pagination
        basePath="/constituencies"
        params={{ search, sort, direction }}
        page={constituencies.page}
        totalPages={constituencies.total_pages}
        label="Constituencies"
        summary={`${constituencies.total.toLocaleString("en-IN")} constituencies`}
      />
    </main>
  );
}
