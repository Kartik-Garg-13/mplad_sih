import Link from "next/link";
import CalibrationChart from "@/components/CalibrationChart";
import { getAtRisk, getStallModelMetrics } from "@/lib/api";
import Pagination from "@/components/site/Pagination";

function fmtInr(amount: number | null): string {
  if (amount === null || amount === undefined) return "—";
  const abs = Math.abs(amount);
  if (abs >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000) return `₹${(amount / 1_00_000).toFixed(2)}L`;
  return `₹${amount.toLocaleString("en-IN")}`;
}

function riskBand(risk: number): { label: string; className: string } {
  if (risk >= 0.7) return { label: "high", className: "bg-rose-50 text-rose-700 ring-rose-200" };
  if (risk >= 0.4) return { label: "medium", className: "bg-amber-50 text-amber-700 ring-amber-200" };
  return { label: "low", className: "bg-emerald-50 text-emerald-700 ring-emerald-200" };
}

type SearchParams = { [key: string]: string | string[] | undefined };
function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function AtRiskPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const page = one(sp.page) ?? "1";
  const search = one(sp.search);

  const [model, atRisk] = await Promise.all([
    getStallModelMetrics(),
    getAtRisk({ page, page_size: "25", search }),
  ]);
  const { metrics, feature_importances } = model;
  // The calibration blurb below used to hardcode "0.87" / "63%" — accurate
  // the day it was written, wrong the next time the model was retrained
  // on a fresh corpus snapshot (confirmed live: the real highest-bin
  // numbers had already drifted to 0.87/67%). Read the top calibration
  // bin straight from the same data the chart plots, so the prose can
  // never say something the chart next to it contradicts.
  const topBinIdx = metrics.calibration_mean_predicted.length - 1;
  const topBinPredicted = metrics.calibration_mean_predicted[topBinIdx];
  const topBinActual = metrics.calibration_fraction_positive[topBinIdx];

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <Link href="/flags" className="text-sm text-ink-muted hover:text-ink-2">
        &larr; Flag list
      </Link>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink-2">Stall-risk model</h1>
      <p className="mt-1 mb-6 max-w-3xl text-sm text-ink-muted">
        A LightGBM classifier trained on works with a known outcome (completed, or in progress and already past
        their category&rsquo;s normal completion time) predicts a stall-risk score for the {atRisk.total.toLocaleString("en-IN")}{" "}
        works still within their normal completion window &mdash; before they become an obvious delay. This is an
        early-warning ranking, not a verdict.
      </p>

      <section className="mb-8 grid grid-cols-1 gap-4 rounded-lg border border-border bg-surface p-5 sm:grid-cols-[auto_1fr]">
        <div>
          <CalibrationChart
            meanPredicted={metrics.calibration_mean_predicted}
            fractionPositive={metrics.calibration_fraction_positive}
          />
          <p className="mt-1 max-w-[220px] text-xs text-ink-muted">
            The dashed line is perfect calibration. The model runs a bit below it at the high end &mdash; a work
            scored ~{(topBinPredicted * 100).toFixed(0)}% is actually stalled about{" "}
            {(topBinActual * 100).toFixed(0)}% of the time, not {(topBinPredicted * 100).toFixed(0)}%. Reported
            honestly, not smoothed over.
          </p>
        </div>
        <div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-muted">PR-AUC</dt>
              <dd className="text-lg font-semibold tabular-nums text-ink-2">{metrics.pr_auc.toFixed(3)}</dd>
              <dd className="text-xs text-ink-muted">vs. {metrics.positive_rate_test.toFixed(3)} base rate</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-muted">ROC-AUC</dt>
              <dd className="text-lg font-semibold tabular-nums text-ink-2">{metrics.roc_auc.toFixed(3)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-ink-muted">Train / test</dt>
              <dd className="text-lg font-semibold tabular-nums text-ink-2">
                {metrics.n_train.toLocaleString("en-IN")} / {metrics.n_test.toLocaleString("en-IN")}
              </dd>
              <dd className="text-xs text-ink-muted">split by sanction date, not random</dd>
            </div>
          </dl>

          <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-ink-muted">What drives the score</h3>
          <ul className="mt-2 space-y-1">
            {/* Math.max over the whole array, not feature_importances[0].importance:
                the API happens to return these already sorted descending
                today, but reading the bar scale off "whichever element sits
                first" both throws on an empty array and silently produces
                the wrong scale the moment that ordering assumption doesn't
                hold. Math.max(1, ...) also keeps a divide-by-zero from
                turning into every bar at 0% if every importance were 0. */}
            {feature_importances.slice(0, 6).map((f) => {
              const max = Math.max(1, ...feature_importances.map((fi) => fi.importance));
              return (
                <li key={f.feature} className="flex items-center gap-2 text-xs">
                  <span className="w-32 shrink-0 text-ink-muted">{f.feature}</span>
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface-sunken">
                    <span
                      className="block h-full rounded-full bg-navy"
                      style={{ width: `${(f.importance / max) * 100}%` }}
                    />
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </section>

      <form className="mb-4 flex gap-2">
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

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[900px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-sunken text-left text-xs font-medium uppercase tracking-wide text-ink-muted">
              <th className="px-3 py-2">Risk</th>
              <th className="px-3 py-2">Work</th>
              <th className="px-3 py-2">State / MP</th>
              <th className="px-3 py-2 text-right">Days open</th>
              <th className="px-3 py-2 text-right">Normal (P75)</th>
              <th className="px-3 py-2 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {atRisk.results.map((r) => {
              const band = riskBand(r.stall_risk);
              return (
                <tr key={r.work_id} className="border-b border-border-soft last:border-0 hover:bg-surface-sunken">
                  <td className="px-3 py-2 align-top">
                    <span className={`rounded-sm px-1.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${band.className}`}>
                      {(r.stall_risk * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="px-3 py-2 align-top">
                    <Link
                      href={`/works/${r.work_id}`}
                      className="font-medium text-ink-2 underline decoration-border underline-offset-2 hover:decoration-ink-muted"
                    >
                      {r.description || r.work_id}
                    </Link>
                    <div className="mt-0.5 text-[11px] text-ink-muted">{r.category}</div>
                  </td>
                  <td className="px-3 py-2 align-top text-ink-muted">
                    <div>{r.state ?? "—"}</div>
                    <div className="text-[11px] text-ink-muted">{r.mp_name ?? "—"}</div>
                  </td>
                  <td className="px-3 py-2 text-right align-top tabular-nums text-ink-muted">{r.days_open}</td>
                  <td className="px-3 py-2 text-right align-top tabular-nums text-ink-muted">{r.p75_days.toFixed(0)}</td>
                  <td className="px-3 py-2 text-right align-top tabular-nums text-ink-2">{fmtInr(r.sanction_amount)}</td>
                </tr>
              );
            })}
            {atRisk.results.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-10 text-center text-sm text-ink-muted">
                  No at-risk works match this search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Pagination
        basePath="/at-risk"
        params={{ search }}
        page={atRisk.page}
        totalPages={atRisk.total_pages}
        label="At-risk works"
        summary={`${atRisk.total.toLocaleString("en-IN")} works`}
      />
    </main>
  );
}
