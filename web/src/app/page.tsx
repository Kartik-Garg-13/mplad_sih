import Link from "next/link";
import { getProvenance, getStats } from "@/lib/api";
import Reveal from "@/components/motion/Reveal";
import CountUp from "@/components/motion/CountUp";
import Parallax from "@/components/motion/Parallax";

const PIPELINE = [
  { n: "01", title: "Ingest", body: "eSAKSHI CSVs → Polars → clean Parquet. No scraper, no login." },
  { n: "02", title: "Detect", body: "13 detectors run offline against the full corpus → DuckDB. Nothing computed live." },
  { n: "03", title: "Serve", body: "FastAPI, read-only. Every endpoint is a SELECT against the pre-built database." },
  { n: "04", title: "Review", body: "This site — flag list, graph, models, and a reviewer override that closes the loop." },
];

const TIER_A = [
  { id: "A1", title: "Ledger contradiction", body: "A payment recorded against a work exceeds its sanctioned amount." },
  { id: "A2", title: "Phantom completion", body: "Marked complete, but little or nothing has actually been paid out." },
  { id: "A3", title: "Duplicate record", body: "The same work ID appears more than once in the source export." },
  { id: "A4", title: "Orphan sanction", body: "A sanctioned work is missing its agency, state, or category." },
  { id: "A5", title: "Unverified completion", body: "Marked complete with no photo evidence on file." },
];

const TIER_B = [
  { id: "B1", title: "Peer cost outlier", body: "Sanctioned amount is a statistical outlier against its real peer group." },
  { id: "B2", title: "Cost-per-unit outlier", body: "Cost per physical unit departs from the category’s peer median." },
  { id: "B3", title: "Stalled work", body: "Open well past the category’s empirical P95 completion time." },
  { id: "B4", title: "Threshold bunching", body: "Sanctions cluster just under a round-rupee administrative tier." },
  { id: "B5", title: "Work splitting", body: "Several similarly-worded works from one agency, clustered in time." },
  { id: "B6", title: "Agency concentration", body: "One agency handles an unusual share of an MP’s sanctioned value." },
  { id: "B7", title: "Year-end bunching", body: "A disproportionate share of sanctions land in the final 90 days." },
  { id: "B8", title: "Near-duplicate funding", body: "Near-identical descriptions, same district, close in time." },
];

const RESTRAINT_RULES = [
  { n: "1", title: "Vocabulary lock", body: "A CI test greps the entire codebase for a fixed list of accusatory words before every build." },
  { n: "2", title: "No flag without evidence", body: "Every flag states its trigger, peer group, n, and the observed value — or it doesn’t ship." },
  { n: "3", title: "Benign explanations", body: "Every detector carries a plausible innocent explanation, shown by default, not behind a tooltip." },
  { n: "4", title: "Confidence tier always visible", body: "A / B is on the card, the list, and the filter. Deterministic and statistical are never conflated." },
  { n: "5", title: "No MP suspicion ranking", body: "Works and agencies are ranked. Members of Parliament never are." },
  { n: "6", title: "Provenance on every screen", body: "Source, ingestion date, record counts, and coverage percentages, everywhere — see the footer." },
  { n: "7", title: "Reviewer override", body: "A human can mark a flag “reviewed — explained.” Suppressed, never deleted, always reversible." },
];

export default async function LandingPage() {
  const [stats, provenance] = await Promise.all([getStats(), getProvenance()]);

  return (
    <main>
      {/* ---------------------------------------------------------------- Hero */}
      <section className="relative overflow-hidden bg-navy-deep">
        <Parallax speed={-70} className="pointer-events-none absolute -right-40 -top-56 h-[560px] w-[560px] rounded-full bg-navy-panel/60" />
        <Parallax speed={50} className="pointer-events-none absolute -bottom-52 -left-40 h-[420px] w-[420px] rounded-full bg-navy/70" />
        <Parallax speed={-30} className="pointer-events-none absolute right-1/4 top-1/3 h-40 w-40 rounded-full border border-accent/20" />

        <div className="relative mx-auto max-w-6xl px-6 pb-28 pt-20 sm:pt-28">
          <Reveal mode="fade">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium tracking-wide text-on-navy-muted">
              SIH26102 &middot; MoSPI &middot; Anomaly Detection in the MPLADS Scheme
            </span>
          </Reveal>

          <Reveal delay={80}>
            <h1 className="font-display mt-7 max-w-3xl text-5xl font-semibold leading-[1.08] tracking-tight text-white sm:text-6xl">
              A review queue.
              <br />
              <span className="text-accent">Not a verdict.</span>
            </h1>
          </Reveal>

          <Reveal delay={160}>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-on-navy-2">
              PARAKH flags patterns in MPLADS implementation records that warrant a human&rsquo;s
              attention &mdash; thirteen real detectors, five independent validation methods, and a
              restraint contract enforced by code, not good intentions.
            </p>
          </Reveal>

          <Reveal delay={240}>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link
                href="/flags"
                className="rounded-full bg-accent px-6 py-3 text-sm font-semibold text-navy-deep transition-transform hover:scale-[1.03]"
              >
                Open the flag list
              </Link>
              <Link
                href="/dashboard"
                className="rounded-full border border-white/20 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
              >
                View the dashboard
              </Link>
            </div>
          </Reveal>

          <Reveal delay={320}>
            <div className="mt-16 grid grid-cols-2 gap-8 border-t border-white/10 pt-8 sm:grid-cols-4">
              <div>
                <div className="font-display text-3xl font-semibold text-white">
                  <CountUp to={stats.total_works} />
                </div>
                <div className="mt-1 text-xs text-on-navy-muted">works ingested</div>
              </div>
              <div>
                <div className="font-display text-3xl font-semibold text-white">
                  <CountUp to={stats.flagged_works} />
                </div>
                <div className="mt-1 text-xs text-on-navy-muted">flagged for review</div>
              </div>
              <div>
                <div className="font-display text-3xl font-semibold text-white">
                  <CountUp to={stats.n_detectors} />
                </div>
                <div className="mt-1 text-xs text-on-navy-muted">real detectors</div>
              </div>
              <div>
                <div className="font-display text-3xl font-semibold text-white">
                  <CountUp to={5} />
                </div>
                <div className="mt-1 text-xs text-on-navy-muted">validation methods</div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ------------------------------------------------------------- Problem */}
      <section className="bg-surface py-24">
        <div className="mx-auto max-w-6xl px-6">
          <Reveal>
            <span className="text-xs font-semibold uppercase tracking-widest text-ink-muted">The problem</span>
            <h2 className="font-display mt-3 max-w-2xl text-3xl font-semibold text-ink-2 sm:text-4xl">
              Scale without visibility
            </h2>
          </Reveal>

          <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-3">
            {[
              { to: provenance.n_works / 100000, suffix: "L", label: "sanctioned works", decimals: 1 },
              { to: provenance.n_expenditure_records / 100000, suffix: "L", label: "payment transactions", decimals: 2 },
              { to: provenance.n_agencies, suffix: "", label: "district implementing agencies", decimals: 0 },
            ].map((s, i) => (
              <Reveal key={s.label} delay={i * 90}>
                <div className="rounded-2xl border border-border bg-surface-sunken p-7">
                  <div className="font-display text-4xl font-semibold text-ink-2">
                    <CountUp to={s.to} decimals={s.decimals} format="none" suffix={s.suffix} />
                  </div>
                  <div className="mt-2 text-sm text-ink-muted">{s.label}</div>
                </div>
              </Reveal>
            ))}
          </div>

          <Reveal delay={280}>
            <div className="mt-8 max-w-3xl rounded-2xl border border-rose-100 bg-rose-50 px-7 py-6">
              <p className="text-[15px] leading-relaxed text-rose-900">
                <strong>The trap this problem statement warns about:</strong> an AI that decides
                which MP is at fault is a defamation engine, not a tool. That risk shaped every
                design decision here before a single detector was written.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* --------------------------------------------------------- How it works */}
      <section className="bg-surface-sunken py-24">
        <div className="mx-auto max-w-6xl px-6">
          <Reveal>
            <span className="text-xs font-semibold uppercase tracking-widest text-ink-muted">Under the hood</span>
            <h2 className="font-display mt-3 max-w-2xl text-3xl font-semibold text-ink-2 sm:text-4xl">
              A batch pipeline, not a live guess
            </h2>
          </Reveal>

          <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {PIPELINE.map((step, i) => (
              <Reveal key={step.n} delay={i * 100}>
                <div className="h-full rounded-2xl border border-border bg-surface p-6">
                  <div className="font-display text-3xl font-semibold text-accent-ink">{step.n}</div>
                  <div className="mt-3 text-lg font-semibold text-ink-2">{step.title}</div>
                  <p className="mt-2 text-sm leading-relaxed text-ink-muted">{step.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* -------------------------------------------------------- What it flags */}
      <section className="bg-surface py-24">
        <div className="mx-auto max-w-6xl px-6">
          <Reveal>
            <span className="text-xs font-semibold uppercase tracking-widest text-ink-muted">What actually fires</span>
            <h2 className="font-display mt-3 max-w-2xl text-3xl font-semibold text-ink-2 sm:text-4xl">
              Thirteen detectors, two tiers
            </h2>
            <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-ink-muted">
              Tier A is a deterministic contradiction a human can verify by hand. Tier B is a
              statistical outlier against a stated peer group, abstaining below 30 peers so it
              never flags on noise.
            </p>
          </Reveal>

          <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-2">
            <Reveal>
              <div className="rounded-2xl border border-rose-100 bg-rose-50 p-7">
                <div className="text-xs font-bold uppercase tracking-widest text-rose-700">
                  Tier A &middot; deterministic integrity
                </div>
                <ul className="mt-5 space-y-4">
                  {TIER_A.map((d) => (
                    <li key={d.id} className="flex gap-3">
                      <span className="mt-0.5 shrink-0 font-mono text-xs font-bold text-rose-700">{d.id}</span>
                      <div>
                        <div className="text-sm font-semibold text-ink-2">{d.title}</div>
                        <div className="text-sm text-ink-muted">{d.body}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>

            <Reveal delay={120}>
              <div className="rounded-2xl border border-amber-100 bg-amber-50 p-7">
                <div className="text-xs font-bold uppercase tracking-widest text-accent-ink">
                  Tier B &middot; peer-relative statistical
                </div>
                <ul className="mt-5 space-y-4">
                  {TIER_B.map((d) => (
                    <li key={d.id} className="flex gap-3">
                      <span className="mt-0.5 shrink-0 font-mono text-xs font-bold text-accent-ink">{d.id}</span>
                      <div>
                        <div className="text-sm font-semibold text-ink-2">{d.title}</div>
                        <div className="text-sm text-ink-muted">{d.body}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------ Restraint */}
      <section className="relative overflow-hidden bg-navy-deep py-24">
        <Parallax speed={-40} className="pointer-events-none absolute -left-32 top-0 h-[420px] w-[420px] rounded-full bg-navy-panel/50" />

        <div className="relative mx-auto max-w-6xl px-6">
          <Reveal>
            <span className="text-xs font-semibold uppercase tracking-widest text-on-navy-muted">
              The restraint contract
            </span>
            <h2 className="font-display mt-3 max-w-2xl text-3xl font-semibold text-white sm:text-4xl">
              Seven rules, enforced &mdash; not just written down
            </h2>
          </Reveal>

          <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {RESTRAINT_RULES.map((rule, i) => (
              <Reveal key={rule.n} delay={i * 70}>
                <div className="h-full rounded-2xl border border-white/10 bg-navy p-6">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-bold text-navy-deep">
                    {rule.n}
                  </div>
                  <div className="mt-4 text-base font-semibold text-white">{rule.title}</div>
                  <p className="mt-2 text-sm leading-relaxed text-on-navy-muted">{rule.body}</p>
                </div>
              </Reveal>
            ))}
          </div>

          <Reveal delay={RESTRAINT_RULES.length * 70 + 40}>
            <div className="mt-8 max-w-3xl rounded-2xl border border-white/10 bg-navy p-7">
              <p className="text-[15px] leading-relaxed text-on-navy-2">
                <strong className="text-accent">Honesty, applied to ourselves:</strong> the original
                plan scoped a third detector tier &mdash; a composite priority score across every
                signal. It wasn&rsquo;t built. Thirteen of sixteen originally planned detectors
                shipped, stated on the{" "}
                <Link href="/methodology" className="underline decoration-white/30 underline-offset-2 hover:text-accent">
                  methodology page
                </Link>
                , not hidden from it.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* -------------------------------------------------------------- Closing */}
      <section className="bg-surface py-24">
        <div className="mx-auto max-w-6xl px-6 text-center">
          <Reveal>
            <h2 className="font-display mx-auto max-w-2xl text-3xl font-semibold text-ink-2 sm:text-4xl">
              It tells you where to look, and why &mdash; and just as plainly, where it can&rsquo;t
              tell you anything yet.
            </h2>
          </Reveal>
          <Reveal delay={120}>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link
                href="/flags"
                className="rounded-full bg-navy px-6 py-3 text-sm font-semibold text-white transition-transform hover:scale-[1.03]"
              >
                Open the flag list
              </Link>
              <Link
                href="/validation"
                className="rounded-full border border-border px-6 py-3 text-sm font-semibold text-ink-2 transition-colors hover:bg-surface-sunken"
              >
                See how it&rsquo;s validated
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </main>
  );
}
