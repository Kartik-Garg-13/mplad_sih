import Link from "next/link";

type Params = Record<string, string | undefined>;

/**
 * Page controls for the record lists. A server component on purpose: the
 * jump box is a plain GET form, so picking a page works with scripts off
 * and needs no function props (which cannot cross into a client
 * component anyway).
 */
export default function Pagination({
  basePath,
  params,
  page,
  totalPages,
  label,
  summary,
}: {
  basePath: string;
  params: Params;
  page: number;
  totalPages: number;
  /** Names the collection, for the landmark's accessible name. */
  label: string;
  /** The row count this list is paging through, e.g. "37,700 flagged works". */
  summary: string;
}) {
  const href = (target: number) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...params, page: String(target) })) {
      if (v) qs.set(k, v);
    }
    return `${basePath}?${qs.toString()}`;
  };

  const last = Math.max(1, totalPages);
  const current = Math.min(Math.max(1, page), last);

  const hidden = Object.entries(params).filter(([k, v]) => k !== "page" && v);

  return (
    <nav
      aria-label={`${label} pages`}
      className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-ink-muted"
    >
      <div>
        Page {current.toLocaleString("en-IN")} of {last.toLocaleString("en-IN")} &mdash; {summary}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <PageLink href={href(1)} disabled={current === 1} label="First page">
          &laquo;
        </PageLink>
        <PageLink href={href(current - 1)} disabled={current === 1} label="Previous page">
          Previous
        </PageLink>

        {pageWindow(current, last).map((p, i) =>
          p === null ? (
            <span key={`gap-${i}`} aria-hidden className="px-1 text-ink-muted">
              &hellip;
            </span>
          ) : (
            <Link
              key={p}
              href={href(p)}
              aria-current={p === current ? "page" : undefined}
              className={`rounded-md border px-2.5 py-1 tabular-nums transition-colors ${
                p === current
                  ? "border-navy bg-navy text-white"
                  : "border-border hover:border-ink-muted"
              }`}
            >
              {p.toLocaleString("en-IN")}
            </Link>
          ),
        )}

        <PageLink href={href(current + 1)} disabled={current === last} label="Next page">
          Next
        </PageLink>
        <PageLink href={href(last)} disabled={current === last} label="Last page">
          &raquo;
        </PageLink>

        <form action={basePath} className="ml-1 flex items-center gap-1.5">
          {hidden.map(([k, v]) => (
            <input key={k} type="hidden" name={k} value={v} />
          ))}
          <label htmlFor={`${basePath}-page`} className="sr-only">
            Go to page
          </label>
          <input
            id={`${basePath}-page`}
            type="number"
            name="page"
            min={1}
            max={last}
            defaultValue={current}
            aria-label={`Go to page, 1 to ${last}`}
            className="w-20 rounded-md border border-border bg-surface px-2 py-1 tabular-nums focus:border-ink-muted focus:outline-none"
          />
          <button
            type="submit"
            className="rounded-md border border-border px-2.5 py-1 hover:border-ink-muted"
          >
            Go
          </button>
        </form>
      </div>
    </nav>
  );
}

function PageLink({
  href,
  disabled,
  label,
  children,
}: {
  href: string;
  disabled: boolean;
  label: string;
  children: React.ReactNode;
}) {
  if (disabled) {
    return (
      <span aria-disabled className="rounded-md border border-border px-2.5 py-1 opacity-40">
        {children}
      </span>
    );
  }
  return (
    <Link
      href={href}
      aria-label={label}
      className="rounded-md border border-border px-2.5 py-1 transition-colors hover:border-ink-muted"
    >
      {children}
    </Link>
  );
}

/** Page numbers around `current`, with `null` marking an elided run. */
function pageWindow(current: number, last: number): (number | null)[] {
  if (last <= 7) return Array.from({ length: last }, (_, i) => i + 1);

  const pages = new Set<number>([1, last, current]);
  for (const p of [current - 1, current + 1]) {
    if (p >= 1 && p <= last) pages.add(p);
  }
  // Keep the row a stable width near the ends, where the window would
  // otherwise collapse against the first or last page.
  if (current <= 3) [2, 3, 4].forEach((p) => pages.add(p));
  if (current >= last - 2) [last - 3, last - 2, last - 1].forEach((p) => pages.add(p));

  const sorted = [...pages].filter((p) => p >= 1 && p <= last).sort((a, b) => a - b);
  const out: (number | null)[] = [];
  let previous = 0;
  for (const p of sorted) {
    if (previous && p - previous > 1) out.push(null);
    out.push(p);
    previous = p;
  }
  return out;
}
