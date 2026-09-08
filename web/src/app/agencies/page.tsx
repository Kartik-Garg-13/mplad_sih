import Link from "next/link";
import { getAgencies } from "@/lib/api";
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

export default async function AgenciesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const page = one(sp.page) ?? "1";
  const thinFile = one(sp.thin_file);
  const crossState = one(sp.cross_state);
  const search = one(sp.search);
  const sort = one(sp.sort) ?? "total_value";

  const agencies = await getAgencies({
    page,
    page_size: "25",
    thin_file: thinFile,
    cross_state: crossState,
    search,
    sort,
  });

  const buildHref = (overrides: Record<string, string | undefined>) => {
    const params = new URLSearchParams();
    const merged = { thin_file: thinFile, cross_state: crossState, search, sort, page: "1", ...overrides };
    for (const [k, v] of Object.entries(merged)) {
      if (v) params.set(k, v);
    }
    return `/agencies?${params.toString()}`;
  };

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link href="/flags" className="text-sm text-ink-muted hover:text-ink-2">
            &larr; Flag list
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink-2">Agency network</h1>
          <p className="mt-1 max-w-2xl text-sm text-ink-muted">
            Implementing agencies, ranked by sanctioned value. Two signals below are worth a look, not a verdict —
            both have plausible innocent explanations stated alongside them.{" "}
            <Link href="/graph" className="underline decoration-border underline-offset-2 hover:decoration-ink-muted">
              View as a graph &rarr;
            </Link>
          </p>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <Link
          href={buildHref({ thin_file: thinFile === "true" ? undefined : "true", cross_state: undefined })}
          className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
            thinFile === "true"
              ? "border-navy bg-navy text-white"
              : "border-border bg-surface text-ink-muted hover:border-border"
          }`}
        >
          Thin-file agencies
        </Link>
        <Link
          href={buildHref({ cross_state: crossState === "true" ? undefined : "true", thin_file: undefined })}
          className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
            crossState === "true"
              ? "border-navy bg-navy text-white"
              : "border-border bg-surface text-ink-muted hover:border-border"
          }`}
        >
          Cross-state agency name
        </Link>
        {(thinFile || crossState) && (
          <Link href="/agencies" className="rounded-full px-3 py-1 text-xs text-ink-muted hover:text-ink-2">
            Clear
          </Link>
        )}
      </div>

      {thinFile === "true" && (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>Few works, high value each</strong> — often a remote or sparsely-populated district doing fewer,
          larger infrastructure works rather than many small ones (several of these are Northeast India hill
          districts). A real pattern worth a look, not evidence on its own.
        </div>
      )}
      {crossState === "true" && (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <strong>Same agency name recorded under more than one state.</strong> Most of these trace to the 2014
          Telangana/Andhra Pradesh split or Chandigarh&rsquo;s shared-capital status with Punjab — a naming
          artifact. A handful pairing Uttar Pradesh with Jammu &amp; Kashmir look like a genuine data-entry issue,
          worth a second look.
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[800px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-sunken text-left text-xs font-medium uppercase tracking-wide text-ink-muted">
              <th className="px-3 py-2">Agency</th>
              <th className="px-3 py-2 text-right">Works</th>
              <th className="px-3 py-2 text-right">MPs served</th>
              <th className="px-3 py-2 text-right">Value/work</th>
              <th className="px-3 py-2 text-right">Total value</th>
              <th className="px-3 py-2">Flags</th>
            </tr>
          </thead>
          <tbody>
            {agencies.results.map((a) => (
              <tr key={a.implementing_agency} className="border-b border-border-soft last:border-0 hover:bg-surface-sunken">
                <td className="px-3 py-2">
                  <Link
                    href={`/agencies/${encodeURIComponent(a.implementing_agency)}`}
                    className="font-medium text-ink-2 underline decoration-border underline-offset-2 hover:decoration-ink-muted"
                  >
                    {a.implementing_agency}
                  </Link>
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{a.n_works}</td>
                <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{a.n_mps}</td>
                <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{fmtInr(a.value_per_work)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-ink-2">{fmtInr(a.total_value)}</td>
                <td className="px-3 py-2">
                  <div className="flex gap-1">
                    {a.is_thin_file && (
                      <span className="rounded-sm bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
                        thin-file
                      </span>
                    )}
                    {a.is_cross_state && (
                      <span className="rounded-sm bg-sky-50 px-1.5 py-0.5 text-[11px] font-medium text-sky-700 ring-1 ring-inset ring-sky-200">
                        cross-state
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {agencies.results.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-10 text-center text-sm text-ink-muted">
                  No agencies match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Pagination
        basePath="/agencies"
        params={{ thin_file: thinFile, cross_state: crossState, search, sort }}
        page={agencies.page}
        totalPages={agencies.total_pages}
        label="Agencies"
        summary={`${agencies.total.toLocaleString("en-IN")} agencies`}
      />
    </main>
  );
}
