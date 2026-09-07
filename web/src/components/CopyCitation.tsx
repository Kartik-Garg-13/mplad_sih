"use client";

import { useState } from "react";
import type { Flag } from "@/lib/api";

type Props = {
  workId: string;
  description: string;
  state: string;
  mpName: string;
  implementingAgency: string;
  flags: Flag[];
  sourceName: string;
  sourceUrl: string;
  snapshotDate: string;
};

/** A plain-text, paste-ready block — not JSON, not a link — because the
 * people who need this (a journalist quoting a flag, an auditor filing a
 * note) work in email and documents, not APIs. Every flag's tier is kept
 * in the citation text itself (plan §08, rule 4: tier stays visible
 * wherever a flag appears, including once it has left the app). */
function buildCitation(p: Props): string {
  const flagLines = p.flags.map((f) => `  [Tier ${f.tier} · ${f.detector}] ${f.evidence}`).join("\n");
  return [
    `PARAKH — anomaly flag on MPLADS work ${p.workId}`,
    "",
    p.description,
    `${p.state} · ${p.mpName} · ${p.implementingAgency}`,
    "",
    "Flags:",
    flagLines,
    "",
    `Source: ${p.sourceName} (${p.sourceUrl})`,
    `Ingested: ${p.snapshotDate}`,
    "This flag says a pattern warrants a look — it is not a finding of wrongdoing.",
  ].join("\n");
}

export default function CopyCitation(props: Props) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(buildCitation(props));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be denied by the browser (permissions,
      // non-HTTPS context) — fail quietly rather than throw in a click
      // handler; the button simply doesn't confirm and the user can try
      // again or select the text on the page directly.
    }
  }

  return (
    <button
      onClick={copy}
      className="shrink-0 rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-ink-muted hover:bg-surface-sunken"
    >
      {copied ? "Copied" : "Copy citation"}
    </button>
  );
}
