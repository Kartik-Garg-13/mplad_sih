"use client";

import { useInView } from "@/components/motion/useInView";

type Bar = { label: string; value: number };

export default function BarChart({
  data,
  color = "#1b2a4e",
  formatValue = (v: number) => v.toLocaleString("en-IN"),
}: {
  data: Bar[];
  color?: string;
  formatValue?: (v: number) => string;
}) {
  const { ref, inView } = useInView<HTMLDivElement>();
  const max = Math.max(1, ...data.map((d) => d.value));

  return (
    <div ref={ref} className="space-y-3">
      {data.map((d, i) => (
        // `${i}-${d.label}` not `d.label` alone: a caller that truncates a
        // long label (the dashboard's category chart cuts to 42 chars) can
        // produce two entries with the same displayed label from two
        // different underlying rows — a bare label key would then collide
        // and React would misrender one of the bars.
        <div key={`${i}-${d.label}`}>
          <div className="mb-1 flex items-baseline justify-between text-sm">
            <span className="max-w-[70%] truncate text-ink-2" title={d.label}>
              {d.label}
            </span>
            <span className="tabular-nums text-ink-muted">{formatValue(d.value)}</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface-sunken">
            <div
              className="h-full rounded-full transition-[width] ease-out"
              style={{
                width: inView ? `${(d.value / max) * 100}%` : "0%",
                background: color,
                transitionDuration: "900ms",
                transitionDelay: `${i * 60}ms`,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
