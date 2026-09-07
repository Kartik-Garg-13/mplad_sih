"use client";

import { useInView } from "@/components/motion/useInView";

type Segment = { label: string; value: number; color: string };

const SIZE = 200;
const STROKE = 26;
const R = (SIZE - STROKE) / 2;
const C = 2 * Math.PI * R;

export default function DonutChart({ segments }: { segments: Segment[] }) {
  const { ref, inView } = useInView<HTMLDivElement>();
  const total = Math.max(1, segments.reduce((s, seg) => s + seg.value, 0));

  // Each segment's start offset derived purely from the segments before it —
  // no accumulator mutated during render (the react-compiler's immutability
  // check flags exactly that pattern).
  const arcLengths = segments.map((seg) => (seg.value / total) * C);
  const offsets = arcLengths.map((_, i) => arcLengths.slice(0, i).reduce((sum, len) => sum + len, 0));

  return (
    <div ref={ref} className="flex items-center gap-8">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width={SIZE} height={SIZE}>
        <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
          <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none" stroke="#f1f5f9" strokeWidth={STROKE} />
          {segments.map((seg, i) => {
            const len = arcLengths[i];
            const offset = offsets[i];
            return (
              <circle
                key={seg.label}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={R}
                fill="none"
                stroke={seg.color}
                strokeWidth={STROKE}
                strokeDasharray={`${len} ${C - len}`}
                strokeDashoffset={inView ? -offset : -C}
                style={{ transition: `stroke-dashoffset 900ms ease-out ${i * 120}ms` }}
              />
            );
          })}
        </g>
        <text x={SIZE / 2} y={SIZE / 2 - 4} textAnchor="middle" fontSize="26" fontWeight={700} fill="#0f172a">
          {total.toLocaleString("en-IN")}
        </text>
        <text x={SIZE / 2} y={SIZE / 2 + 16} textAnchor="middle" fontSize="11" fill="#475569">
          flagged works
        </text>
      </svg>

      <ul className="space-y-2.5">
        {segments.map((seg) => (
          <li key={seg.label} className="flex items-center gap-2.5 text-sm">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: seg.color }} />
            <span className="text-ink-2">{seg.label}</span>
            <span className="tabular-nums text-ink-muted">
              {seg.value.toLocaleString("en-IN")} ({((seg.value / total) * 100).toFixed(0)}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
