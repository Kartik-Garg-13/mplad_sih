import Link from "next/link";

type Crumb = { label: string; href?: string };

export default function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-ink-muted">
      <Link href="/" className="hover:text-ink-2">
        Home
      </Link>
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1.5">
          <span className="text-slate-300">/</span>
          {item.href ? (
            <Link href={item.href} className="hover:text-ink-2">
              {item.label}
            </Link>
          ) : (
            <span className="max-w-[38ch] truncate text-ink-2" title={item.label}>
              {item.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  );
}
