import { notFound } from "next/navigation";
import { getAgencyDetail } from "@/lib/api";
import Breadcrumbs from "@/components/site/Breadcrumbs";

function fmtInr(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "—";
  const abs = Math.abs(amount);
  if (abs >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000) return `₹${(amount / 1_00_000).toFixed(2)}L`;
  return `₹${amount.toLocaleString("en-IN")}`;
}

export default async function AgencyDetailPage({
  params,
}: {
  params: Promise<{ id: string[] }>;
}) {
  const { id } = await params;
  // Next.js 16's catch-all params arrive still percent-encoded (e.g. "%20"
  // stays literal, not " ") — decode each segment before use, or
  // getAgencyDetail's own encodeURIComponent double-encodes it and the
  // lookup 404s against the backend for any agency name with a space or
  // other reserved character.
  const agencyName = id.map(decodeURIComponent).join("/");

  let detail;
  try {
    detail = await getAgencyDetail(agencyName);
  } catch {
    notFound();
  }
  const { agency, states, mps, vendors } = detail;

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <Breadcrumbs items={[{ label: "Agencies", href: "/agencies" }, { label: agency.implementing_agency }]} />

      <header className="mt-3 mb-6 border-b border-border pb-6">
        <h1 className="text-xl font-semibold leading-snug text-ink-2">{agency.implementing_agency}</h1>
        <div className="mt-2 flex gap-2">
          {agency.is_thin_file && (
            <span className="rounded-sm bg-amber-50 px-1.5 py-0.5 text-[11px] font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
              thin-file
            </span>
          )}
          {agency.is_cross_state && (
            <span className="rounded-sm bg-sky-50 px-1.5 py-0.5 text-[11px] font-medium text-sky-700 ring-1 ring-inset ring-sky-200">
              cross-state
            </span>
          )}
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Works</dt>
            <dd className="tabular-nums text-ink-2">{agency.n_works}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">MPs served</dt>
            <dd className="tabular-nums text-ink-2">{agency.n_mps}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Value / work</dt>
            <dd className="tabular-nums text-ink-2">{fmtInr(agency.value_per_work)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Total value</dt>
            <dd className="tabular-nums text-ink-2">{fmtInr(agency.total_value)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">States on record</dt>
            <dd className="text-ink-2">{states.join(", ") || "—"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Graph community</dt>
            <dd className="tabular-nums text-ink-2">{agency.community ?? "—"}</dd>
          </div>
        </dl>
      </header>

      <section className="mb-6">
        <h2 className="mb-2 text-sm font-semibold text-ink-2">MPs whose works this agency implements</h2>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-sunken text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-3 py-2">MP</th>
                <th className="px-3 py-2 text-right">Works</th>
                <th className="px-3 py-2 text-right">Value</th>
              </tr>
            </thead>
            <tbody>
              {mps.map((m, i) => (
                <tr key={i} className="border-b border-border-soft last:border-0">
                  <td className="px-3 py-2 text-ink-2">{m.mp_name}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{m.n_works}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-2">{fmtInr(m.total_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {vendors.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-ink-2">Top paid vendors (up to 50)</h2>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-sunken text-left text-xs uppercase tracking-wide text-ink-muted">
                  <th className="px-3 py-2">Vendor</th>
                  <th className="px-3 py-2 text-right">Payments</th>
                  <th className="px-3 py-2 text-right">Total paid</th>
                </tr>
              </thead>
              <tbody>
                {vendors.map((v, i) => (
                  <tr key={i} className="border-b border-border-soft last:border-0">
                    <td className="px-3 py-2 text-ink-2">{v.vendor_name}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{v.n_payments}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-ink-2">{fmtInr(v.total_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
