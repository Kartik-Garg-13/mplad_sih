"use client";

import { useEffect, useRef, useState } from "react";
import { useInView } from "./useInView";

type CountUpProps = {
  to: number;
  duration?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  /** en-IN grouping (1,31,437) — this app's real numbers are Indian-style. */
  format?: "en-IN" | "none";
  className?: string;
};

function easeOutExpo(t: number): number {
  return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

export default function CountUp({
  to,
  duration = 1400,
  decimals = 0,
  prefix = "",
  suffix = "",
  format = "en-IN",
  className,
}: CountUpProps) {
  const { ref, inView } = useInView<HTMLSpanElement>();
  // Starts at the real target, not 0: `to` is already known server-side
  // (the page that renders a CountUp already fetched the stat), so the
  // server HTML — and the client's first paint, before the reveal
  // animation below ever runs — shows the true number. Confirmed live:
  // the old `useState(0)` meant a crawler, a slow hydration, or JS
  // disabled entirely permanently showed "0 works ingested" on the
  // landing page. The animation itself is untouched — the effect below
  // still resets to 0 and counts back up the moment the element scrolls
  // into view, exactly as designed; this only fixes what shows *before*
  // that reveal moment.
  const [value, setValue] = useState(to);
  // Tracks which target the animation has already run for, not just
  // whether it has ever run — a bare boolean would mean a CountUp whose
  // `to` prop changes after its first reveal (a live stat re-fetched
  // after a dataset upload rebuilds the corpus, for instance) silently
  // stops animating forever, permanently displaying whatever number was
  // current the first time this element scrolled into view.
  const animatedTo = useRef<number | null>(null);

  useEffect(() => {
    if (!inView || animatedTo.current === to) return;
    animatedTo.current = to;

    // Reduced-motion collapses the animation to a single frame — t reaches 1
    // immediately — rather than branching to a setState call in the effect
    // body itself; setValue only ever runs inside the rAF callback below.
    const reduced =
      typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const effectiveDuration = reduced ? 0 : duration;

    const start = performance.now();
    let raf: number;
    const tick = (now: number) => {
      const t = effectiveDuration === 0 ? 1 : Math.min(1, (now - start) / effectiveDuration);
      setValue(to * easeOutExpo(t));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to, duration]);

  const display =
    format === "en-IN"
      ? value.toLocaleString("en-IN", { maximumFractionDigits: decimals, minimumFractionDigits: decimals })
      : value.toFixed(decimals);

  return (
    <span ref={ref} className={className}>
      {prefix}
      {display}
      {suffix}
    </span>
  );
}
