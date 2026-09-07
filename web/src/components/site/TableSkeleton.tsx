export default function TableSkeleton({ rows = 8, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <main className="mx-auto max-w-6xl animate-pulse px-6 py-10">
      <div className="h-4 w-40 rounded bg-slate-200" />
      <div className="mt-4 h-8 w-64 rounded bg-slate-200" />
      <div className="mt-2 h-4 w-96 max-w-full rounded bg-slate-100" />

      <div className="mt-8 flex flex-wrap gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-7 w-20 rounded-full bg-slate-100" />
        ))}
      </div>

      <div className="mt-6 h-16 rounded-lg bg-slate-100" />

      <div className="mt-6 overflow-hidden rounded-lg border border-slate-200">
        <div className="h-10 bg-slate-50" />
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex gap-6 border-t border-slate-100 px-4 py-4">
            {Array.from({ length: cols }).map((_, c) => (
              <div key={c} className="h-4 flex-1 rounded bg-slate-100" style={{ maxWidth: c === 0 ? 60 : undefined }} />
            ))}
          </div>
        ))}
      </div>
    </main>
  );
}
