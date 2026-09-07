import { notFound } from "next/navigation";
import { getDetectors, getProvenance, getWorkDetail, getWorkPeers, type WorkPeersResponse } from "@/lib/api";
import ReviewOverride from "@/components/ReviewOverride";
import CopyCitation from "@/components/CopyCitation";
import Breadcrumbs from "@/components/site/Breadcrumbs";
import PeerHistogram from "@/components/charts/PeerHistogram";

function fmtInr(amount: unknown): string {
  if (typeof amount !== "number") return "—";
  const abs = Math.abs(amount);
  if (abs >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000) return `₹${(amount / 1_00_000).toFixed(2)}L`;
  return `₹${amount.toLocaleString("en-IN")}`;
}

function field(work: Record<string, unknown>, key: string): string {
  const v = work[key];
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}

export default async function WorkDetailPage({
  params,
}: {
  params: Promise<{ id: string[] }>;
}) {
  const { id } = await params;
  // See agencies/[...id]/page.tsx — Next.js 16's catch-all params arrive
  // still percent-encoded, so each segment must be decoded before use.
  const workId = id.map(decodeURIComponent).join("/");

  let detail;
  try {
    detail = await getWorkDetail(workId);
  } catch {
    notFound();
  }
  const { work, flags, payments, override } = detail;

  // Fetched alongside the work, not hardcoded on the page: detector
  // metadata is served from the backend (see api/main.py's /api/detectors)
  // precisely so the benign explanation shown here is the exact same text
  // that lands in a CSV export — one copy of this text, not two that could
  // drift apart.
  const [{ detectors }, provenance, peersRes] = await Promise.all([
    getDetectors(),
    getProvenance(),
    // Best-effort: a peers histogram is an enhancement to the evidence
    // sentence, not a requirement for the page to render it — a work
    // whose category/state/FY never reached a peer group's own n>=30
    // floor legitimately has none, and that must not 404 the whole page.
    getWorkPeers(workId).catch((): WorkPeersResponse => ({ work_id: workId, peers: {} })),
  ]);
  const benignById = Object.fromEntries(detectors.map((d) => [d.id, d.benign_explanation]));
  const peersByDetector = peersRes.peers;

  const tierA = flags.filter((f) => f.tier === "A");
  const tierB = flags.filter((f) => f.tier === "B");

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <Breadcrumbs
        items={[
          { label: "Flag list", href: "/flags" },
          { label: field(work, "description") !== "—" ? field(work, "description") : workId },
        ]}
      />

      <header className="mt-3 mb-6 border-b border-border pb-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold leading-snug text-ink-2">{field(work, "description")}</h1>
            <p className="mt-1 font-mono text-xs text-ink-muted">{workId}</p>
          </div>
          {flags.length > 0 && (
            <CopyCitation
              workId={workId}
              description={field(work, "description")}
              state={field(work, "state")}
              mpName={field(work, "mp_name")}
              implementingAgency={field(work, "implementing_agency")}
              flags={flags}
              sourceName={provenance.source_name}
              sourceUrl={provenance.source_url}
              snapshotDate={provenance.snapshot_date}
            />
          )}
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">State / District</dt>
            <dd className="text-ink-2">
              {field(work, "state")} / {field(work, "district_raw")}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">MP</dt>
            <dd className="text-ink-2">{field(work, "mp_name")}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Implementing agency</dt>
            <dd className="text-ink-2">{field(work, "implementing_agency")}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Category</dt>
            <dd className="text-ink-2">{field(work, "category")}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Status</dt>
            <dd className="text-ink-2">{field(work, "work_status")}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Financial year</dt>
            <dd className="text-ink-2">{field(work, "financial_year")}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Sanctioned amount</dt>
            <dd className="tabular-nums text-ink-2">{fmtInr(work.sanction_amount)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Recommended date</dt>
            <dd className="text-ink-2">{field(work, "recommended_date")}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-ink-muted">Sanction date</dt>
            <dd className="text-ink-2">{field(work, "sanction_date")}</dd>
          </div>
        </dl>
      </header>

      {tierA.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink-2">
            <span className="inline-flex items-center rounded-sm bg-rose-50 px-1.5 py-0.5 text-[11px] font-semibold tracking-wide text-rose-700 ring-1 ring-inset ring-rose-200">
              TIER A
            </span>
            Integrity flags &mdash; deterministic
          </h2>
          <ul className="space-y-2">
            {tierA.map((f, i) => (
              <li key={i} className="rounded-md border border-rose-100 bg-rose-50/50 px-3 py-2 text-sm text-ink-2">
                <div>
                  <span className="mr-2 font-mono text-xs font-semibold text-rose-700">{f.detector}</span>
                  {f.evidence}
                </div>
                {benignById[f.detector] && (
                  <p className="mt-1.5 border-t border-rose-100 pt-1.5 text-xs text-ink-muted">
                    <span className="font-medium text-ink-muted">Plausible innocent explanation:</span>{" "}
                    {benignById[f.detector]}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {tierB.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink-2">
            <span className="inline-flex items-center rounded-sm bg-amber-50 px-1.5 py-0.5 text-[11px] font-semibold tracking-wide text-amber-700 ring-1 ring-inset ring-amber-200">
              TIER B
            </span>
            Statistical outliers &mdash; peer-relative
          </h2>
          <ul className="space-y-2">
            {tierB.map((f, i) => (
              <li key={i} className="rounded-md border border-amber-100 bg-amber-50/50 px-3 py-2 text-sm text-ink-2">
                <div>
                  <span className="mr-2 font-mono text-xs font-semibold text-amber-700">{f.detector}</span>
                  {f.evidence}
                </div>
                {benignById[f.detector] && (
                  <p className="mt-1.5 border-t border-amber-100 pt-1.5 text-xs text-ink-muted">
                    <span className="font-medium text-ink-muted">Plausible innocent explanation:</span>{" "}
                    {benignById[f.detector]}
                  </p>
                )}
                {peersByDetector[f.detector] && (
                  <PeerHistogram dist={peersByDetector[f.detector]} detector={f.detector} />
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {flags.length > 0 && (
        <section className="mb-6">
          <ReviewOverride workId={work.work_id as string} override={override} />
        </section>
      )}

      {payments.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-ink-2">Payment history</h2>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-border bg-surface-sunken text-left text-xs uppercase tracking-wide text-ink-muted">
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Vendor</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p, i) => (
                  <tr key={i} className="border-b border-border-soft last:border-0">
                    <td className="px-3 py-2 text-ink-muted">{p.expenditure_date ?? "—"}</td>
                    <td className="px-3 py-2 text-ink-muted">{p.vendor_name ?? "—"}</td>
                    <td className="px-3 py-2 text-ink-muted">{p.payment_status ?? "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-ink-2">{fmtInr(p.amount)}</td>
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
