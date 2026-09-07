"use client";

import { useInView } from "@/components/motion/useInView";

type YearRow = { financial_year: string; n_works: number; n_flagged: number };

const W = 640;
const H = 260;
const PAD_L = 48;
const PAD_R = 16;
const PAD_T = 16;
const PAD_B = 32;

// Compact axis label ("58K", not "58,000") — the three gridlines drawn
// below used to carry no value at all, which made this a chart with an
// unlabelled scale: two lines rising against each other with no way to
// read off what either one is actually worth.
function compactCount(v: number): string {
  if (v >= 1000) return `${(v / 1000).toFixed(v >= 10_000 ? 0 : 1)}K`;
  return Math.round(v).toString();
}

export default function TrendChart({ data }: { data: YearRow[] }) {
  const { ref, inView } = useInView<HTMLDivElement>();
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;
  const max = Math.max(1, ...data.map((d) => d.n_works));

  const x = (i: number) => PAD_L + (data.length <= 1 ? plotW / 2 : (i / (data.length - 1)) * plotW);
  const y = (v: number) => PAD_T + plotH - (v / max) * plotH;

  const worksPath = data.map((d, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(d.n_works)}`).join(" ");
  const flaggedPath = data.map((d, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(d.n_flagged)}`).join(" ");

  return (
    <div ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Works and flagged works by financial year">
        {[0, 0.5, 1].map((f) => {
          const gridY = PAD_T + plotH * (1 - f);
          return (
            <g key={f}>
              <line
                x1={PAD_L}
                y1={gridY}
                x2={W - PAD_R}
                y2={gridY}
                stroke="#e2e8f0"
                strokeDasharray={f === 0 ? undefined : "3 4"}
              />
              <text x={PAD_L - 8} y={gridY} dy="0.32em" fontSize="10" fill="#94a3b8" textAnchor="end">
                {compactCount(max * f)}
              </text>
            </g>
          );
        })}

        <path
          d={worksPath}
          fill="none"
          stroke="#94a3b8"
          strokeWidth={2}
          strokeDasharray={1000}
          strokeDashoffset={inView ? 0 : 1000}
          style={{ transition: "stroke-dashoffset 1100ms ease-out" }}
        />
        <path
          d={flaggedPath}
          fill="none"
          stroke="#b45309"
          strokeWidth={2.5}
          strokeDasharray={1000}
          strokeDashoffset={inView ? 0 : 1000}
          style={{ transition: "stroke-dashoffset 1100ms ease-out 150ms" }}
        />

        {data.map((d, i) => (
          <g key={d.financial_year} style={{ opacity: inView ? 1 : 0, transition: `opacity 400ms ${300 + i * 80}ms` }}>
            <circle cx={x(i)} cy={y(d.n_works)} r={3.5} fill="#94a3b8" />
            <circle cx={x(i)} cy={y(d.n_flagged)} r={3.5} fill="#b45309" />
            <text x={x(i)} y={H - 10} fontSize="11" fill="#475569" textAnchor="middle">
              {d.financial_year}
            </text>
          </g>
        ))}
      </svg>

      <div className="mt-2 flex gap-5 text-xs text-ink-muted">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: "#94a3b8" }} /> sanctioned works
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: "#b45309" }} /> flagged
        </span>
      </div>
    </div>
  );
}
