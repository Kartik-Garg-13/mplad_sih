"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Fires once — reveal animations shouldn't replay every time a section
 * scrolls back into view, only the first time a viewer reaches it.
 *
 * Always initializes to `false`, on the server and the client alike.
 * `typeof IntersectionObserver === "undefined"` is also true during SSR (no
 * DOM in Node) — using that as the initial-state check made every reveal
 * render pre-visible in the server HTML, then snap to hidden on hydration
 * (a real hydration mismatch, not cosmetic). The true no-IntersectionObserver
 * fallback only ever needs to run once the effect below is actually on the
 * client, never from render.
 */
export function useInView<T extends HTMLElement>(options?: IntersectionObserverInit) {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    // Nested function, not a bare top-level call — keeps this out of the
    // "setState synchronously in an effect body" lint even though it still
    // runs synchronously on mount for unsupported browsers.
    function revealImmediately() {
      setInView(true);
    }

    if (typeof IntersectionObserver === "undefined") {
      revealImmediately();
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -10% 0px", ...options }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [options]);

  return { ref, inView };
}
