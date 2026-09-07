import Link from "next/link";
import { getProvenance, getStats } from "@/lib/api";

export default async function MethodologyPage() {
  const [provenance, stats] = await Promise.all([getProvenance(), getStats()]);

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <Link href="/flags" className="text-sm text-ink-muted hover:text-ink-2">
        &larr; Flag list
      </Link>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink-2">Methodology &amp; restraint</h1>
      <p className="mt-2 text-sm text-ink-muted">
        PARAKH flags patterns in MPLADS implementation records that warrant a human&rsquo;s attention. It does not
        conclude, accuse, or rank suspects. This page states the rules that keep it that way, and is honest about
        where the build fell short of the original plan.
      </p>

      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Vocabulary lock</h2>
        <p className="mt-2 text-sm text-ink-2">
          Permitted words: flag, outlier, warrants review, departs from peer group, requires explanation. A short,
          fixed list of accusatory words &mdash; the vocabulary of a verdict already reached, not a pattern worth
          a look &mdash; is banned everywhere in this repository: code, evidence text, UI copy, variable names.
          This isn&rsquo;t a style guideline; it is enforced by a CI test (
          <code>tests/test_vocabulary_lock.py</code>, which names the list explicitly) that greps the entire
          source tree on every run and fails the build if any of those words appear outside the test itself.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Confidence tiers</h2>
        <p className="mt-2 text-sm text-ink-2">
          A flag&rsquo;s tier is always visible &mdash; on the flag list, the filter, and the work detail page. A
          ledger contradiction and a statistical outlier are different kinds of claim and are never presented as
          the same thing.
        </p>
        <dl className="mt-3 space-y-3 text-sm">
          <div>
            <dt className="font-medium text-rose-700">Tier A &mdash; deterministic integrity (5 detectors: A1&ndash;A5)</dt>
            <dd className="text-ink-muted">
              An arithmetic or logical contradiction a human can verify by hand from the evidence sentence alone
              &mdash; a payment exceeding the sanction, a completion date before the sanction date, and similar.
            </dd>
          </div>
          <div>
            <dt className="font-medium text-amber-700">Tier B &mdash; peer-relative statistical outliers (8 detectors: B1&ndash;B8)</dt>
            <dd className="text-ink-muted">
              A robust (median/MAD) z-score or share measure against a named peer group, always stating that peer
              group and its size. Abstains rather than flagging when the peer group is too small to be meaningful.
            </dd>
          </div>
        </dl>
      </section>

      <section className="mt-8 rounded-md border border-amber-200 bg-amber-50 px-4 py-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-800">
          What the plan called Tier C &mdash; not built
        </h2>
        <p className="mt-2 text-sm text-amber-900">
          The original plan scoped a third, model-based tier: an Isolation Forest (C1) and a Local Outlier Factor
          model (C2) trained on an engineered feature vector, combined into a &ldquo;Review Priority Score&rdquo;
          (C3) &mdash; a rank-average ensemble of Tiers A, B and C into a single 0&ndash;100 number. None of the
          three were built. Thirteen of the sixteen originally planned detectors shipped (Tier A&rsquo;s five,
          Tier B&rsquo;s eight); C1&ndash;C3 did not, and there is no composite priority score anywhere in this
          app. Saying so here, rather than quietly dropping it from the record, is itself part of the restraint
          this project asks of its own flags.
        </p>
        <p className="mt-2 text-sm text-amber-900">
          Two things in this app are sometimes mistaken for Tier C but are not it, and are not labelled as it: the{" "}
          <Link href="/at-risk" className="underline decoration-amber-400 underline-offset-2 hover:decoration-amber-700">
            stall-risk model
          </Link>{" "}
          is a single-purpose, calibrated classifier that predicts whether an open work is likely to stall &mdash;
          not a general anomaly ensemble &mdash; and the{" "}
          <Link href="/graph" className="underline decoration-amber-400 underline-offset-2 hover:decoration-amber-700">
            agency network graph
          </Link>{" "}
          surfaces structural patterns (thin-file agencies, cross-state naming) for a human to browse, not a score.
          Neither one ranks works by an aggregate suspicion number.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Benign explanations</h2>
        <p className="mt-2 text-sm text-ink-2">
          Every detector carries a curated, plausible innocent explanation for the pattern it catches &mdash;
          terrain and urban cost premiums, land-acquisition delays, legitimate batch rollouts, data-entry lag, and
          so on. It is shown by default on the work detail page next to the flag, not hidden behind a tooltip. A
          flag with no stated benign explanation would be a claim this project isn&rsquo;t willing to make.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">No MP suspicion ranking</h2>
        <p className="mt-2 text-sm text-ink-2">
          Works and agencies are ranked here; Members of Parliament are not. The one place an MP&rsquo;s name is
          tied to a number &mdash; the{" "}
          <Link href="/constituencies" className="underline decoration-border underline-offset-2 hover:decoration-ink-muted">
            constituency scorecard
          </Link>{" "}
          &mdash; measures district-level implementation performance (completion rate, fund utilisation), not
          integrity, and says so on that page. None of those numbers appear as a flag anywhere in this app.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Provenance, every screen</h2>
        <p className="mt-2 text-sm text-ink-2">
          Source, ingestion date, record counts and coverage percentages are shown in the footer of every page,
          not just this one. Right now: {stats.total_works.toLocaleString("en-IN")} works and{" "}
          {provenance.n_expenditure_records.toLocaleString("en-IN")} payment records from{" "}
          <a
            href={provenance.source_url}
            target="_blank"
            rel="noreferrer"
            className="underline decoration-border underline-offset-2 hover:decoration-ink-muted"
          >
            {provenance.source_name}
          </a>
          , ingested {provenance.snapshot_date}
          {provenance.financial_year_earliest && provenance.financial_year_latest && (
            <>
              {" "}
              &mdash; covering sanctions from FY {provenance.financial_year_earliest} to FY{" "}
              {provenance.financial_year_latest}
            </>
          )}
          . Coverage gaps are stated, not hidden in an average: only{" "}
          {(provenance.quantity_coverage * 100).toFixed(1)}% of works have an extractable physical quantity, and
          only {(provenance.image_evidence_coverage * 100).toFixed(1)}% have photo evidence on file &mdash; both
          are real limits of the source export, not this app&rsquo;s detectors.
        </p>
      </section>

      <section className="mt-8 mb-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Reviewer override</h2>
        <p className="mt-2 text-sm text-ink-2">
          A reviewer who checks a flagged work and finds the benign explanation credible can mark it &ldquo;reviewed
          &mdash; explained&rdquo; from the work detail page, with an optional note. That suppresses the work from
          the default queue &mdash; it does not delete the flag, the evidence, or the note, and can be undone. The{" "}
          <code>include_reviewed</code> filter on the flag list shows everything, reviewed or not.
        </p>
      </section>
    </main>
  );
}
