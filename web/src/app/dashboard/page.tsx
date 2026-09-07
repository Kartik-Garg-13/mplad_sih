import { getOverview, getProvenance, getStats } from "@/lib/api";
import Reveal from "@/components/motion/Reveal";
import CountUp from "@/components/motion/CountUp";
import BarChart from "@/components/charts/BarChart";
import TrendChart from "@/components/charts/TrendChart";
import DonutChart from "@/components/charts/DonutChart";

const TIER_COLORS: Record<string, string> = {
  both: "#1b2a4e",
  tier_a_only: "#be123c",
  tier_b_only: "#b45309",
};
const TIER_LABELS: Record<string, string> = {
  both: "Tier A and B",
  tier_a_only: "Tier A only",
  tier_b_only: "Tier B only",
};

export default async function DashboardPage() {
  const [overview, stats, provenance] = await Promise.all([getOverview(), getStats(), getProvenance()]);

  const tierSegments = overview.tier_composition
    .slice()
    .sort((a, b) => b.n - a.n)
    .map((t) => ({ label: TIER_LABELS[t.bucket] ?? t.bucket, value: t.n, color: TIER_COLORS[t.bucket] ?? "#94a3b8" }));

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <Reveal>
        <span className="text-xs font-semibold uppercase tracking-widest text-ink-muted">Overview</span>
        <h1 className="font-display mt-3 text-3xl font-semibold tracking-tight text-ink-2 sm:text-4xl">Dashboard</h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-muted">
          Every chart below is a plain aggregate over the same database every other page reads &mdash;
          nothing here is computed differently or ranks a Member of Parliament.
        </p>
      </Reveal>

      <Reveal delay={80}>
        <div className="mt-8 grid grid-cols-2 gap-5 sm:grid-cols-4">
          {[
            { label: "works ingested", value: stats.total_works },
            { label: "flagged works", value: stats.flagged_works },
            { label: "detectors", value: stats.n_detectors },
            { label: "validation methods", value: 5 },
          ].map((s) => (
            <div key={s.label} className="rounded-2xl border border-border bg-surface p-5">
              <div className="font-display text-2xl font-semibold text-ink-2">
                <CountUp to={s.value} />
              </div>
              <div className="mt-1 text-xs text-ink-muted">{s.label}</div>
            </div>
          ))}
        </div>
      </Reveal>

      <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Reveal>
          <div className="rounded-2xl border border-border bg-surface p-7">
            <h2 className="text-base font-semibold text-ink-2">Flagged works by state</h2>
            <p className="mt-1 text-xs text-ink-muted">Top 12 states by flagged-work count.</p>
            <div className="mt-6">
              <BarChart data={overview.by_state.map((r) => ({ label: r.state, value: r.n_flagged }))} color="#1b2a4e" />
            </div>
          </div>
        </Reveal>

        <Reveal delay={80}>
          <div className="rounded-2xl border border-border bg-surface p-7">
            <h2 className="text-base font-semibold text-ink-2">Sanctioned vs. flagged, by financial year</h2>
            <p className="mt-1 text-xs text-ink-muted">
              {provenance.financial_year_earliest && provenance.financial_year_latest
                ? `The corpus spans FY ${provenance.financial_year_earliest} through FY ${provenance.financial_year_latest}.`
                : "Financial-year coverage of the current corpus."}
            </p>
            <div className="mt-6">
              <TrendChart data={overview.by_year} />
            </div>
          </div>
        </Reveal>

        <Reveal>
          <div className="rounded-2xl border border-border bg-surface p-7">
            <h2 className="text-base font-semibold text-ink-2">Flagged works by category</h2>
            <p className="mt-1 text-xs text-ink-muted">Top 8 work categories by flagged-work count.</p>
            <div className="mt-6">
              <BarChart
                data={overview.by_category.map((r) => ({
                  label: r.category.length > 42 ? r.category.slice(0, 42) + "…" : r.category,
                  value: r.n_flagged,
                }))}
                color="#b45309"
              />
            </div>
          </div>
        </Reveal>

        <Reveal delay={80}>
          <div className="rounded-2xl border border-border bg-surface p-7">
            <h2 className="text-base font-semibold text-ink-2">Tier composition</h2>
            <p className="mt-1 text-xs text-ink-muted">
              Deterministic (A) vs. peer-relative statistical (B) — never conflated on any card.
            </p>
            <div className="mt-6">
              <DonutChart segments={tierSegments} />
            </div>
          </div>
        </Reveal>
      </div>
    </main>
  );
}
