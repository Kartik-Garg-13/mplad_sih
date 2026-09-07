import Link from "next/link";
import { getProvenance } from "@/lib/api";

const NAV_COLUMNS = [
  {
    heading: "Review",
    links: [
      { href: "/flags", label: "Flag list" },
      { href: "/unflagged", label: "No flags" },
      { href: "/reviewed", label: "Reviewed" },
      { href: "/agencies", label: "Agencies" },
      { href: "/graph", label: "Network graph" },
      { href: "/at-risk", label: "At-risk works" },
      { href: "/constituencies", label: "Constituencies" },
    ],
  },
  {
    heading: "Understand",
    links: [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/datasets", label: "Datasets" },
      { href: "/methodology", label: "Methodology" },
      { href: "/validation", label: "Validation" },
    ],
  },
];

export default async function SiteFooter() {
  let provenance;
  try {
    provenance = await getProvenance();
  } catch {
    provenance = null;
  }

  return (
    <footer className="border-t border-white/10 bg-navy-deep text-on-navy-2">
      <div className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid grid-cols-1 gap-10 sm:grid-cols-[1.3fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-sm text-navy-deep">
                &#9873;
              </span>
              <span className="text-lg font-semibold tracking-tight text-white">PARAKH</span>
            </div>
            <p className="mt-3 max-w-xs text-sm text-on-navy-muted">
              A review queue for MPLADS implementation records &mdash; every flag warrants a look,
              never a verdict. SIH26102, MoSPI.
            </p>
          </div>

          {NAV_COLUMNS.map((col) => (
            <div key={col.heading}>
              <div className="text-xs font-semibold uppercase tracking-wider text-on-navy-muted">
                {col.heading}
              </div>
              <ul className="mt-3 space-y-2">
                {col.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href} className="text-sm text-on-navy-2 hover:text-accent">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="hairline mt-10" />

        {provenance && (
          <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-on-navy-muted">
            <span>
              Source:{" "}
              <a
                href={provenance.source_url}
                target="_blank"
                rel="noreferrer"
                className="underline decoration-white/20 underline-offset-2 hover:text-on-navy-2"
              >
                {provenance.source_name}
              </a>{" "}
              &mdash; {provenance.houses_covered}
              {provenance.financial_year_earliest && provenance.financial_year_latest && (
                <>
                  {" "}
                  &mdash; FY {provenance.financial_year_earliest} to FY {provenance.financial_year_latest}
                </>
              )}
            </span>
            <span>
              Ingested {provenance.snapshot_date} &mdash; {provenance.n_works.toLocaleString("en-IN")} works,{" "}
              {provenance.n_expenditure_records.toLocaleString("en-IN")} payment records,{" "}
              {provenance.n_states} states, {provenance.n_mps} MPs, {provenance.n_agencies} agencies
            </span>
            <span>
              Coverage: quantity data {(provenance.quantity_coverage * 100).toFixed(1)}% &middot; photo
              evidence {(provenance.image_evidence_coverage * 100).toFixed(1)}%
            </span>
          </div>
        )}
      </div>
    </footer>
  );
}
