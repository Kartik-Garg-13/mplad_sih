import Link from "next/link";
import { flagsExportCsvUrl, getDatasets, getFlags, getMeta, getStats } from "@/lib/api";
import { pageParam } from "@/lib/params";
import Pagination from "@/components/site/Pagination";

function fmtInr(amount: number | null): string {
  if (amount === null || amount === undefined) return "—";
  const abs = Math.abs(amount);
  if (abs >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000) return `₹${(amount / 1_00_000).toFixed(2)}L`;
  return `₹${amount.toLocaleString("en-IN")}`;
}

function TierPill({ hasA, hasB }: { hasA: boolean; hasB: boolean }) {
  return (
    <div className="flex gap-1">
      {hasA && (
        <span className="inline-flex items-center rounded-sm bg-rose-50 px-1.5 py-0.5 text-[11px] font-semibold tracking-wide text-rose-700 ring-1 ring-inset ring-rose-200">
          A
        </span>
      )}
      {hasB && (
        <span className="inline-flex items-center rounded-sm bg-amber-50 px-1.5 py-0.5 text-[11px] font-semibold tracking-wide text-amber-700 ring-1 ring-inset ring-amber-200">
          B
        </span>
      )}
    </div>
  );
}

type SearchParams = { [key: string]: string | string[] | undefined };

function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function FlagsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const page = pageParam(sp.page);
  const detector = one(sp.detector);
  const tier = one(sp.tier);
  const state = one(sp.state);
  const category = one(sp.category);
  const search = one(sp.search);
  const source = one(sp.source);
  const includeReviewed = one(sp.include_reviewed);

  const [flagsRes, meta, stats, datasets] = await Promise.all([
    getFlags({ page, page_size: "25", detector, tier, state, category, search, source, include_reviewed: includeReviewed }),
    getMeta(),
    getStats(),
    // Only needed to resolve a source key into its display label, and that
    // full-corpus lookup isn't free (list_datasets() runs a GROUP BY over
    // every source) — skip it entirely on the very common case of no
    // source filter at all.
    source ? getDatasets().catch(() => null) : Promise.resolve(null),
  ]);
  const sourceLabel = datasets?.sources.find((s) => s.key === source)?.label ?? source;

  const buildHref = (overrides: Record<string, string | undefined>) => {
    const params = new URLSearchParams();
    const merged = { detector, tier, state, category, search, source, include_reviewed: includeReviewed, page: "1", ...overrides };
    for (const [k, v] of Object.entries(merged)) {
      if (v) params.set(k, v);
    }
    return `/flags?${params.toString()}`;
  };

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-ink-2">Flag list</h1>
            <p className="mt-1 text-sm text-ink-muted">
              Every flag says &ldquo;warrants review,&rdquo; never a verdict.
            </p>
          </div>
          <div className="text-right text-sm text-ink-muted">
            <div>
              <span className="font-semibold text-ink-2">{stats.total_works.toLocaleString("en-IN")}</span> works
              ingested
            </div>
            <div>
              <span className="font-semibold text-ink-2">{stats.flagged_works.toLocaleString("en-IN")}</span> flagged
              ({(stats.flagged_share * 100).toFixed(1)}%)
            </div>
          </div>
        </div>

        {source && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-accent-ink/20 bg-accent-soft px-3 py-2 text-sm text-accent-ink">
            <span>
              Showing only <strong>{sourceLabel}</strong>
            </span>
            <Link href={buildHref({ source: undefined })} className="ml-auto text-xs underline underline-offset-2 hover:no-underline">
              Clear
            </Link>
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          {stats.by_detector.map((d) => (
            <Link
              key={d.detector}
              href={buildHref({ detector: detector === d.detector ? undefined : d.detector })}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                detector === d.detector
                  ? "border-navy bg-navy text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
              }`}
            >
              {d.detector} <span className="text-slate-500">·</span> {d.n.toLocaleString("en-IN")}
            </Link>
          ))}
          <Link
            href={buildHref({ include_reviewed: includeReviewed === "true" ? undefined : "true" })}
            className={`rounded-full border px-2.5 py-1 text-xs font-medium transition ${
              includeReviewed === "true"
                ? "border-navy bg-navy text-white"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
            }`}
          >
            Include reviewed
          </Link>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <Link
            href={`/review?${new URLSearchParams(
              Object.entries({ detector, tier, state, category, search, source }).filter(
                (kv): kv is [string, string] => Boolean(kv[1])
              )
            ).toString()}`}
            className="rounded-md bg-accent-ink px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-ink/90"
          >
            Start review &rarr;
          </Link>
          <a
            href={flagsExportCsvUrl({ detector, tier, state, category, search, source, include_reviewed: includeReviewed })}
            className="text-slate-500 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-600"
          >
            Download CSV ({flagsRes.total.toLocaleString("en-IN")} works, current filters)
          </a>
        </div>
      </header>

      <form className="mb-6 grid grid-cols-2 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-5">
        <select
          name="tier"
          defaultValue={tier ?? ""}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
        >
          <option value="">All tiers</option>
          <option value="A">Tier A — integrity</option>
          <option value="B">Tier B — statistical</option>
        </select>
        <select
          name="state"
          defaultValue={state ?? ""}
          className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
        >
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
          className="col-span-2 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm sm:col-span-2"
        >
          <option value="">All categories</option>
          {meta.categories.map((c) => (
            <option key={c} value={c}>
              {c.length > 60 ? c.slice(0, 60) + "…" : c}
            </option>
          ))}
        </select>
        <input type="hidden" name="detector" value={detector ?? ""} />
        <input
          type="search"
          name="search"
          defaultValue={search ?? ""}
          placeholder="Search description, MP, agency…"
          className="col-span-2 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm sm:col-span-1"
        />
        <button
          type="submit"
          className="rounded-md bg-navy px-3 py-1.5 text-sm font-medium text-white hover:bg-navy-panel"
        >
          Filter
        </button>
      </form>

      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full min-w-[900px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <th className="px-3 py-2">Tier</th>
              <th className="px-3 py-2">Work</th>
              <th className="px-3 py-2">State / Agency</th>
              <th className="px-3 py-2">Category</th>
              <th className="px-3 py-2 text-right">Amount</th>
              <th className="px-3 py-2 text-right">Flags</th>
            </tr>
          </thead>
          <tbody>
            {flagsRes.results.map((row) => (
              <tr key={row.work_id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td className="px-3 py-2 align-top">
                  <TierPill hasA={row.has_tier_a} hasB={row.has_tier_b} />
                </td>
                <td className="px-3 py-2 align-top">
                  <Link
                    href={`/works/${row.work_id}`}
                    className="font-medium text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-600"
                  >
                    {row.description || row.work_id}
                  </Link>
                  <div className="mt-0.5 font-mono text-[11px] text-slate-500">{row.work_id}</div>
                </td>
                <td className="px-3 py-2 align-top text-slate-600">
                  <div>{row.state ?? "—"}</div>
                  <div className="text-[11px] text-slate-500">{row.mp_name ?? "—"}</div>
                </td>
                <td className="max-w-[220px] px-3 py-2 align-top text-slate-600">{row.category ?? "—"}</td>
                <td className="whitespace-nowrap px-3 py-2 text-right align-top tabular-nums text-slate-700">
                  {fmtInr(row.sanction_amount ?? row.recommended_amount)}
                </td>
                <td className="px-3 py-2 text-right align-top tabular-nums text-slate-500">{row.n_flags}</td>
              </tr>
            ))}
            {flagsRes.results.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-10 text-center text-sm text-slate-500">
                  No flagged works match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Pagination
        basePath="/flags"
        params={{ detector, tier, state, category, search, source, include_reviewed: includeReviewed }}
        page={flagsRes.page}
        totalPages={flagsRes.total_pages}
        label="Flagged works"
        summary={`${flagsRes.total.toLocaleString("en-IN")} flagged works`}
      />
    </main>
  );
}
