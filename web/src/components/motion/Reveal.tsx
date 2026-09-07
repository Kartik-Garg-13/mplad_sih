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
 * globals.css): the element starts at opacity 0, and this component only
 * ever flips the attribute to "in" — it never toggles visibility off, so a
 * slow-to-hydrate page degrades to "always visible", not "always hidden".
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
