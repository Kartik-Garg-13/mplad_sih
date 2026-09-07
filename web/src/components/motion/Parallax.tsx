"use client";

import { type CSSProperties, type ReactNode, useEffect, useRef } from "react";

type ParallaxProps = {
  /** Optional — a purely decorative parallax layer (e.g. a background orb) has none. */
  children?: ReactNode;
  /** Pixels of travel per 1000px scrolled. Positive drifts down, negative up. */
  speed?: number;
  className?: string;
  style?: CSSProperties;
};

/**
 * Transform-only scroll parallax (never top/left — see the video-build lint
 * lesson on animating layout properties). Reads scrollY in a rAF loop scoped
 * to this element's own visibility, so idle sections cost nothing.
 */
export default function Parallax({ children, speed = 40, className, style }: ParallaxProps) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useRef(false);

  useEffect(() => {
    reduced.current =
      typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced.current) return;

    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") return;

    let ticking = false;
    let visible = false;

    const apply = () => {
      ticking = false;
      if (!visible || !node) return;
      const rect = node.getBoundingClientRect();
      const viewportCenter = window.innerHeight / 2;
      const distanceFromCenter = rect.top + rect.height / 2 - viewportCenter;
      const offset = (distanceFromCenter / 1000) * speed;
      node.style.transform = `translate3d(0, ${offset.toFixed(2)}px, 0)`;
    };

    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(apply);
    };

    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
        if (visible) onScroll();
      },
      { rootMargin: "20% 0px 20% 0px" }
    );
    observer.observe(node);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, [speed]);

  return (
    <div ref={ref} data-parallax className={className} style={style}>
      {children}
    </div>
  );
}
