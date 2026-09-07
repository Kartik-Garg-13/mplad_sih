import Link from "next/link";
import { getStallModelMetrics, getValidation } from "@/lib/api";

const RETENTION_CEILING = 0.6321; // 1 - 1/e — see stability.py's module docstring

function classPill(classification: string) {
  const map: Record<string, string> = {
    plausibly_irregular: "bg-rose-50 text-rose-700 ring-rose-200",
    undecided: "bg-amber-50 text-amber-700 ring-amber-200",
    benign_explained: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  };
  const label: Record<string, string> = {
    plausibly_irregular: "plausibly irregular",
    undecided: "undecided",
    benign_explained: "benign-explained",
  };
  return (
    <span className={`inline-flex items-center rounded-sm px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${map[classification] ?? ""}`}>
      {label[classification] ?? classification}
    </span>
  );
}

export default async function ValidationPage() {
  const [validation, stallModel] = await Promise.all([getValidation(), getStallModelMetrics()]);
  const { synthetic_injection, stability, known_cases, adjudication } = validation;
  const nMatchedCases = known_cases.filter((c) => c.matched).length;
  const nMismatchedCases = known_cases.length - nMatchedCases;

  const byClass = adjudication.clusters.reduce<Record<string, number>>((acc, c) => {
    acc[c.classification] = (acc[c.classification] ?? 0) + c.n_works_in_top50;
    return acc;
  }, {});

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <Link href="/flags" className="text-sm text-ink-muted hover:text-ink-2">
        &larr; Flag list
      </Link>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink-2">Validation</h1>
      <p className="mt-1 mb-8 max-w-3xl text-sm text-ink-muted">
        &ldquo;How do you validate unsupervised anomaly detection with no labels?&rdquo; Five answers, with the real numbers
        here rather than only on a slide &mdash; including the ones that came out less flattering than hoped. See{" "}
        <Link href="/methodology" className="underline decoration-border underline-offset-2 hover:decoration-ink-muted">
          methodology
        </Link>{" "}
        for what these detectors are and aren&rsquo;t claiming.
      </p>

      <section className="mb-10">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          1. Synthetic injection
        </h2>
        <p className="mt-2 mb-3 text-sm text-ink-muted">
          182 constructed anomalies of five known types, injected into a copy of the real corpus, then run through
          the same detector suite as everything else in this app. Recall is per detector; precision/recall@k use
          the flag list&rsquo;s own default ranking (has_tier_a desc, n_flags desc) &mdash; there is no trained
          composite score to rank by (see methodology&rsquo;s Tier C note).
        </p>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[600px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-sunken text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-3 py-2">Injected type</th>
                <th className="px-3 py-2">Target detector</th>
                <th className="px-3 py-2 text-right">n</th>
                <th className="px-3 py-2 text-right">Recall (target)</th>
                <th className="px-3 py-2 text-right">Recall (any)</th>
              </tr>
            </thead>
            <tbody>
              {synthetic_injection.per_type.map((r) => (
                <tr key={r.injected_type} className="border-b border-border-soft last:border-0">
                  <td className="px-3 py-2 text-ink-2">{r.injected_type.replace(/_/g, " ")}</td>
                  <td className="px-3 py-2 font-mono text-xs text-ink-muted">{r.target_detector}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{r.n_injected}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-2">
                    {(r.recall_target_detector * 100).toFixed(1)}%
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-muted">
                    {(r.recall_any_detector * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          split_work&rsquo;s target-detector recall (57.1%) is lower than its any-detector recall (100%): every
          injected split-work row got flagged, just more often by B8 (near-duplicate description) than by B5
          itself &mdash; a real, not a missing, signal.
        </p>

        <div className="mt-4 overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[400px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-sunken text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-3 py-2">k</th>
                <th className="px-3 py-2 text-right">Precision@k</th>
                <th className="px-3 py-2 text-right">Recall@k</th>
              </tr>
            </thead>
            <tbody>
              {synthetic_injection.at_k.map((r) => (
                <tr key={r.k} className="border-b border-border-soft last:border-0">
                  <td className="px-3 py-2 tabular-nums text-ink-2">{r.k}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-2">{(r.precision_at_k * 100).toFixed(1)}%</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-2">{(r.recall_at_k * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          Precision@50 and @100 are both 0% &mdash; the single-flag synthetic injections rank below real works
          that stack many flags from one legitimate batch-procurement pattern. See the adjudication section below
          for the same finding from the other side.
        </p>
      </section>

      <section className="mb-10">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          2. Known-case backtest
        </h2>
        <p className="mt-2 mb-3 text-sm text-ink-muted">
          {nMatchedCases} of {known_cases.length} researched, named CAG/press cases matched this corpus.
        </p>
        <ul className="space-y-2">
          {known_cases.map((c, i) => (
            <li key={i} className="rounded-md border border-border bg-surface-sunken px-4 py-3 text-sm">
              <div className="font-medium text-ink-2">{c.source}</div>
              <div className="mt-0.5 text-ink-muted">{c.description}</div>
              <div className="mt-1.5 text-xs text-ink-muted">
                <span className={c.matched ? "text-emerald-700" : "text-rose-700"}>
                  {c.matched ? "Matched" : "Not matched"}
                </span>{" "}
                &mdash; {c.reason}
              </div>
            </li>
          ))}
        </ul>
        {nMismatchedCases > 0 && (
          <p className="mt-2 text-xs text-ink-muted">
            {nMismatchedCases === 1 ? "The mismatch is" : `All ${nMismatchedCases} mismatches are`} structural
            &mdash; CAG audits review works that are already years old; this corpus reflects recent sanctions.
            Not a search failure.
          </p>
        )}
      </section>

      <section className="mb-10">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          3. Manual adjudication &mdash; top {adjudication.n_reviewed}
        </h2>
        <p className="mt-2 mb-3 text-sm text-ink-muted">
          Every one of the top {adjudication.n_reviewed} flagged works (the flag list&rsquo;s own default
          ranking), reviewed by hand: {byClass.plausibly_irregular ?? 0} plausibly irregular,{" "}
          {byClass.undecided ?? 0} undecided, {byClass.benign_explained ?? 0} benign-explained. All{" "}
          {adjudication.n_reviewed} reduce to {adjudication.clusters.length} real batch-procurement programmes.
        </p>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[700px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-sunken text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-3 py-2">Cluster</th>
                <th className="px-3 py-2 text-right">n</th>
                <th className="px-3 py-2">Classification</th>
                <th className="px-3 py-2">Note</th>
              </tr>
            </thead>
            <tbody>
              {adjudication.clusters.map((c) => (
                <tr key={c.cluster} className="border-b border-border-soft align-top last:border-0">
                  <td className="px-3 py-2 text-ink-2">
                    {c.cluster}
                    <div className="text-[11px] text-ink-muted">{c.state} &middot; {c.mp_name}</div>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{c.n_works_in_top50}</td>
                  <td className="px-3 py-2">{classPill(c.classification)}</td>
                  <td className="max-w-[320px] px-3 py-2 text-xs text-ink-muted">{c.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">4. Stability</h2>
        <p className="mt-2 mb-3 text-sm text-ink-muted">
          The plan&rsquo;s original wording targeted a composite Review Priority Score&rsquo;s rank stability under bootstrap
          resampling &mdash; that score (Tier C) was never built. The closest honest analogue: do Tier B&rsquo;s
          own peer-relative thresholds hold up under resampling? Scoped to the six detectors that reduce to a
          statistic over a peer group (B1&ndash;B4, B6, B7); B5/B8 (text-similarity) are excluded &mdash; bootstrap
          duplicates rows verbatim, which reads as a false near-duplicate to a similarity detector, an artifact of
          the method, not the detector.
        </p>
        <p className="mb-3 text-xs text-ink-muted">
          A same-size bootstrap resample only ever contains ~{(RETENTION_CEILING * 100).toFixed(1)}% of the
          corpus&rsquo;s distinct rows (1&nbsp;&minus;&nbsp;1/e) &mdash; so even a perfectly stable detector can&rsquo;t
          score near 1.0 against the un-resampled baseline. Read the numbers below against that ceiling, not
          against 1.0.
        </p>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[600px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-sunken text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="px-3 py-2">Detector</th>
                <th className="px-3 py-2 text-right">Baseline flagged</th>
                <th className="px-3 py-2 text-right">Mean Jaccard</th>
                <th className="px-3 py-2 text-right">Min</th>
                <th className="px-3 py-2 text-right">Max</th>
              </tr>
            </thead>
            <tbody>
              {stability.map((r) => (
                <tr key={r.detector} className="border-b border-border-soft last:border-0">
                  <td className="px-3 py-2 font-mono text-xs text-ink-2">{r.detector}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{r.baseline_n_flagged.toLocaleString("en-IN")}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-2">{r.mean_jaccard_vs_baseline.toFixed(3)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{r.min_jaccard_vs_baseline.toFixed(3)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-muted">{r.max_jaccard_vs_baseline.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          B1&ndash;B4 sit close to the {(RETENTION_CEILING * 100).toFixed(0)}% ceiling &mdash; most of their
          apparent instability is just sample turnover, not a fragile rule. B6 (0.36) and especially B7 (0.06,
          with one bootstrap run at 0.0) sit well below it &mdash; a real finding, consistent with B7&rsquo;s own
          documented tie-at-the-percentile-ceiling issue (see its detector docstring): its threshold is
          genuinely sensitive to exactly which sample it sees, not just which works happen to be present.
        </p>
      </section>

      <section className="mb-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">5. Stall model</h2>
        <p className="mt-2 text-sm text-ink-muted">
          Time-split PR-AUC {stallModel.metrics.pr_auc.toFixed(3)} vs a {stallModel.metrics.positive_rate_test.toFixed(3)}{" "}
          base rate, ROC-AUC {stallModel.metrics.roc_auc.toFixed(3)} &mdash; never a random split, never plain
          accuracy, both of which would flatter the model dishonestly. Full metrics, calibration curve and
          feature importances live on the{" "}
          <Link href="/at-risk" className="underline decoration-border underline-offset-2 hover:decoration-ink-muted">
            at-risk works page
          </Link>
          .
        </p>
      </section>
    </main>
  );
}
