import Link from "next/link";
import { search } from "@/lib/api";

function fmtInr(amount: number | null): string {
  if (amount === null || amount === undefined) return "—";
  const abs = Math.abs(amount);
  if (abs >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000) return `₹${(amount / 1_00_000).toFixed(2)}L`;
  return `₹${amount.toLocaleString("en-IN")}`;
}

function SeeAllLink({ n, shown, href }: { n: number; shown: number; href: string }) {
  if (n <= shown) return null;
  return (
    <Link
      href={href}
      className="block border-t border-border px-5 py-2.5 text-center text-xs font-medium text-accent-ink hover:bg-surface-sunken"
    >
      See all {n.toLocaleString("en-IN")} &rarr;
    </Link>
  );
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  const query = q?.trim() ?? "";

  if (query.length < 2) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-16 text-center">
        <h1 className="font-display text-2xl font-semibold text-ink-2">Search PARAKH</h1>
        <p className="mt-2 text-sm text-ink-muted">Enter at least two characters in the header search box.</p>
      </main>
    );
  }

  const results = await search(query);
  // The true total across all three categories — each category's own
  // count(*) from the backend, not the length of the (deliberately
  // capped-at-8) preview lists returned alongside them. Summing the
  // preview lengths instead would report "8 matches" for a query that
  // actually has thousands, understating the corpus by orders of
  // magnitude.
  const total = results.n_works + results.n_agencies + results.n_constituencies;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="font-display text-2xl font-semibold text-ink-2">
        Results for &ldquo;{results.query}&rdquo;
      </h1>
      <p className="mt-1 text-sm text-ink-muted">
        {total === 0 ? "No matches" : `${total.toLocaleString("en-IN")} match${total === 1 ? "" : "es"}`} across
        works, agencies, and constituencies.
      </p>

      {results.works.length > 0 && (
        <section className="mt-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-muted">
            Works {results.n_works > results.works.length && `(showing ${results.works.length} of ${results.n_works.toLocaleString("en-IN")})`}
          </h2>
          <ul className="mt-3 divide-y divide-border rounded-xl border border-border bg-surface">
            {results.works.map((w) => (
              <li key={w.work_id}>
                <Link href={`/works/${w.work_id}`} className="block px-5 py-3.5 hover:bg-surface-sunken">
                  <div className="font-medium text-ink-2">{w.description || w.work_id}</div>
                  <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-ink-muted">
                    <span className="font-mono">{w.work_id}</span>
                    <span>{w.state ?? "—"}</span>
                    <span>{w.mp_name ?? "—"}</span>
                    <span>{fmtInr(w.sanction_amount)}</span>
                  </div>
                </Link>
              </li>
            ))}
            <SeeAllLink n={results.n_works} shown={results.works.length} href={`/flags?search=${encodeURIComponent(query)}`} />
          </ul>
        </section>
      )}

      {results.agencies.length > 0 && (
        <section className="mt-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-muted">
            Agencies {results.n_agencies > results.agencies.length && `(showing ${results.agencies.length} of ${results.n_agencies.toLocaleString("en-IN")})`}
          </h2>
          <ul className="mt-3 divide-y divide-border rounded-xl border border-border bg-surface">
            {results.agencies.map((a) => (
              <li key={a.implementing_agency}>
                <Link href={`/agencies/${encodeURIComponent(a.implementing_agency)}`} className="block px-5 py-3.5 hover:bg-surface-sunken">
                  <div className="font-medium text-ink-2">{a.implementing_agency}</div>
                  <div className="mt-0.5 text-xs text-ink-muted">
                    {a.n_works.toLocaleString("en-IN")} works &middot; {fmtInr(a.total_value)} total value
                  </div>
                </Link>
              </li>
            ))}
            <SeeAllLink n={results.n_agencies} shown={results.agencies.length} href={`/agencies?search=${encodeURIComponent(query)}`} />
          </ul>
        </section>
      )}

      {results.constituencies.length > 0 && (
        <section className="mt-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-muted">
            Constituencies {results.n_constituencies > results.constituencies.length && `(showing ${results.constituencies.length} of ${results.n_constituencies.toLocaleString("en-IN")})`}
          </h2>
          <ul className="mt-3 divide-y divide-border rounded-xl border border-border bg-surface">
            {results.constituencies.map((c) => (
              <li key={`${c.state}-${c.constituency}`} className="px-5 py-3.5">
                <div className="font-medium text-ink-2">{c.constituency}</div>
                <div className="mt-0.5 text-xs text-ink-muted">
                  {c.state} &middot; {c.mp_name ?? "—"} &middot; {c.n_sanctioned.toLocaleString("en-IN")} sanctioned
                </div>
              </li>
            ))}
            <SeeAllLink
              n={results.n_constituencies}
              shown={results.constituencies.length}
              href={`/constituencies?search=${encodeURIComponent(query)}`}
            />
          </ul>
        </section>
      )}

      {total === 0 && (
        <p className="mt-10 text-center text-sm text-ink-muted">
          Try a work ID, an MP or agency name, or a constituency.
        </p>
      )}
    </main>
  );
}
