"use client";

import { useInView } from "@/components/motion/useInView";
import type { PeerDistribution } from "@/lib/api";

const W = 320;
const H = 120;
const PAD_L = 8;
const PAD_R = 8;
const PAD_T = 8;
const PAD_B = 20;

function fmtInr(amount: number): string {
  const abs = Math.abs(amount);
  if (abs >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(2)}Cr`;
  if (abs >= 1_00_000) return `₹${(amount / 1_00_000).toFixed(2)}L`;
  return `₹${amount.toLocaleString("en-IN")}`;
}

function fmtDays(v: number): string {
  return `${Math.round(v).toLocaleString("en-IN")} day${Math.round(v) === 1 ? "" : "s"}`;
}

// A plain function reference can't cross the Server->Client Component
// boundary as a prop (functions aren't serializable in RSC payloads) — so
// this takes a `kind` string instead of a formatter callback, and formats
// internally. Add a case here, not a new prop, for a future detector's
// distribution.
const FORMATTERS: Record<string, { format: (v: number) => string; label: string }> = {
  B1: { format: fmtInr, label: "sanctioned" },
  B3: { format: fmtDays, label: "since sanction" },
};

/** Shows what a Tier B evidence sentence otherwise only asserts in prose
 * ("4.2x the peer median, n=151") — the real distribution of this work's
 * peer group, with this work's own value marked against it. Precomputed
 * server-side (see peer_distributions.py / api/main.py's /peers endpoint),
 * so this component only draws what it's handed, the same "nothing
 * computes live" rule every other chart in this app follows.
 */
export default function PeerHistogram({ dist, detector }: { dist: PeerDistribution; detector: string }) {
  const { format: formatValue, label: valueLabel } = FORMATTERS[detector] ?? {
    format: (v: number) => v.toLocaleString("en-IN"),
    label: "",
  };
  const { ref, inView } = useInView<HTMLDivElement>();
  const buckets = dist.bucket_counts;
  const maxCount = Math.max(1, ...buckets);
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;
  const barW = plotW / buckets.length;

  return (
    <div ref={ref} className="mt-2 max-w-xs">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="img"
        aria-label={`Distribution of ${dist.n} peers, this work marked at ${formatValue(dist.own_value)}`}
      >
        {buckets.map((count, i) => {
          const barH = (count / maxCount) * plotH;
          const x = PAD_L + i * barW;
          const y = PAD_T + plotH - barH;
          const isOwn = i === dist.own_bucket;
          return (
            <rect
              key={i}
              x={x + 1}
              y={inView ? y : PAD_T + plotH}
              width={Math.max(0, barW - 2)}
              height={inView ? barH : 0}
              fill={isOwn ? "#b45309" : "#dbe3ef"}
              style={{ transition: `y 600ms ease-out ${i * 25}ms, height 600ms ease-out ${i * 25}ms` }}
            />
          );
        })}
        <line
          x1={PAD_L}
          y1={PAD_T + plotH}
          x2={W - PAD_R}
          y2={PAD_T + plotH}
          stroke="#cbd5e1"
          strokeWidth={1}
        />
        {/* This work's own marker — the whole point of the chart, so it
            gets a distinct label rather than relying on bar color alone
            (color-only signaling fails anyone who can't distinguish the
            two hues, and is lost entirely in a screen reader). */}
        <text
          x={PAD_L + (dist.own_bucket + 0.5) * barW}
          y={H - 6}
          fontSize="9"
          fill="#b45309"
          fontWeight={600}
          textAnchor="middle"
        >
          this work
        </text>
      </svg>
      <p className="mt-0.5 text-[11px] text-ink-muted">
        {dist.n.toLocaleString("en-IN")} peers &middot; median {formatValue(dist.median)} &middot; this work{" "}
        {formatValue(dist.own_value)} {valueLabel}
      </p>
    </div>
  );
}
