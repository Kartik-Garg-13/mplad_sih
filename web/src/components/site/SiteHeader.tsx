"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const NAV = [
  { href: "/flags", label: "Flags" },
  { href: "/unflagged", label: "No flags" },
  { href: "/reviewed", label: "Reviewed" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/agencies", label: "Agencies" },
  { href: "/graph", label: "Graph" },
  { href: "/at-risk", label: "At-risk" },
  { href: "/constituencies", label: "Constituencies" },
  { href: "/datasets", label: "Datasets" },
  { href: "/methodology", label: "Methodology" },
  { href: "/validation", label: "Validation" },
];

export default function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [progress, setProgress] = useState(0);
  const [q, setQ] = useState("");
  const navRef = useRef<HTMLElement>(null);
  const [hasOverflow, setHasOverflow] = useState(false);

  useEffect(() => {
    const doc = document.documentElement;
    const onScroll = () => {
      const max = doc.scrollHeight - doc.clientHeight;
      setProgress(max > 0 ? Math.min(1, doc.scrollTop / max) : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Whether the nav item strip is wider than what's on screen — the
  // no-scrollbar treatment hides the browser's own overflow cue, so
  // without this the tail of the nav can go silently unreachable at a
  // narrower window (confirmed real at common laptop widths once the
  // nav grew past 9 items). When it's overflowing, a right-edge fade
  // mask (applied via the nav's own style, see below) says so instead.
  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    // Measured twice: once inline, then again on a macrotask. The
    // second read is what's trustworthy — confirmed live that reading
    // scrollWidth/clientWidth straight from the ResizeObserver callback
    // catches the flex row mid-reflow, so widening the window back past
    // the overflow point left the fade mask stuck on. The inline read
    // only exists so the cue is still correct where the deferred one is
    // starved (a background tab throttles timers hard).
    let timer = 0;
    const measure = () => {
      const el = navRef.current;
      if (el) setHasOverflow(el.scrollWidth > el.clientWidth + 1);
    };
    const check = () => {
      measure();
      window.clearTimeout(timer);
      timer = window.setTimeout(measure, 0);
    };
    check();
    const observer = new ResizeObserver(check);
    observer.observe(nav);
    // Belt and suspenders: a plain window resize listener alongside the
    // ResizeObserver, since a viewport-size change from a devtools-style
    // emulation override doesn't always trigger the same box-observation
    // callback a real OS window drag reliably does.
    window.addEventListener("resize", check);
    return () => {
      window.clearTimeout(timer);
      observer.disconnect();
      window.removeEventListener("resize", check);
    };
  }, []);

  function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (q.trim()) router.push(`/search?q=${encodeURIComponent(q.trim())}`);
  }

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-navy-deep/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-xs text-navy-deep">
            &#9873;
          </span>
          <span className="text-base font-semibold tracking-tight text-white">PARAKH</span>
        </Link>

        {/* Ten items has to fit the fixed width `max-w-7xl` leaves it —
            confirmed it doesn't at the padding/gap this had before
            "Reviewed" was added as an 11th... 10th item, and the
            no-scrollbar treatment then hid that overflow instead of
            signalling it, so the tail of the nav went silently
            unreachable rather than obviously scrollable. Tightened
            padding/gap here closes the gap at realistic laptop widths;
            the fade mask below is the fallback for whatever's still
            narrower than that, so an overflow is never invisible again. */}
        <nav
          ref={navRef}
          className="no-scrollbar hidden flex-1 items-center gap-0.5 overflow-x-auto lg:flex"
          style={hasOverflow ? { maskImage: "linear-gradient(to right, black calc(100% - 28px), transparent 100%)" } : undefined}
        >
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`whitespace-nowrap rounded-full px-2.5 py-1.5 text-sm transition-colors ${
                  active ? "bg-white/10 text-white" : "text-on-navy-muted hover:text-on-navy-2"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <form onSubmit={onSearch} className="ml-auto flex shrink-0 items-center">
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search works, agencies, seats&hellip;"
            className="w-32 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-sm text-white placeholder:text-on-navy-muted focus:w-56 focus:border-accent/60 focus:outline-none transition-[width] duration-300 sm:w-44 sm:focus:w-64"
          />
        </form>
      </div>

      <div className="h-[2px] w-full bg-white/5">
        <div
          className="h-full bg-accent transition-[width] duration-150 ease-out"
          style={{ width: `${progress * 100}%` }}
        />
      </div>
    </header>
  );
}
