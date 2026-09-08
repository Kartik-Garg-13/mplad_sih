"use client";

import { type CSSProperties, type ElementType, type ReactNode } from "react";
import { useInView } from "./useInView";

type RevealProps = {
  children: ReactNode;
  as?: ElementType;
  /** Stagger delay in ms — e.g. index * 80 from a .map(). */
  delay?: number;
  mode?: "up" | "fade";
  className?: string;
};

/**
 * Fades (and optionally rises) an element into place the first time it
 * enters the viewport. Resting state is plain CSS (`[data-reveal]` in
 * globals.css): the element starts at opacity 0 and only this component
 * flips the attribute to "in".
 *
 * That means the hidden state is the one that survives when the script
 * doesn't run — with JavaScript off, every revealed section would stay
 * invisible forever, which on a page built entirely of them (the landing
 * page, the dashboard) is a blank page rather than a missing animation.
 * The `<noscript>` override in layout.tsx is what makes the no-JS case
 * degrade to "always visible" instead.
 */
export default function Reveal({ children, as: Tag = "div", delay = 0, mode = "up", className }: RevealProps) {
  const { ref, inView } = useInView<HTMLDivElement>();

  return (
    <Tag
      ref={ref}
      data-reveal={inView ? "in" : ""}
      data-reveal-mode={mode}
      style={{ "--reveal-delay": `${delay}ms` } as CSSProperties}
      className={className}
    >
      {children}
    </Tag>
  );
}
