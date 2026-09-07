export default function Loading() {
  return (
    <main className="mx-auto max-w-6xl animate-pulse px-6 py-8">
      <div className="h-7 w-40 rounded bg-slate-200" />
      <div className="mt-3 h-4 w-full max-w-2xl rounded bg-slate-100" />
      <div className="mt-2 h-4 w-3/4 max-w-2xl rounded bg-slate-100" />

      <div className="mt-8 h-4 w-48 rounded bg-slate-200" />
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-40 rounded-xl border border-slate-200 bg-slate-50" />
        ))}
      </div>

      <div className="mt-10 h-4 w-40 rounded bg-slate-200" />
      <div className="mt-4 h-96 rounded-xl border border-slate-200 bg-slate-50" />
    </main>
  );
}
