export default function Loading() {
  return (
    <main className="mx-auto max-w-6xl animate-pulse px-6 py-12">
      <div className="h-4 w-24 rounded bg-slate-200" />
      <div className="mt-4 h-9 w-48 rounded bg-slate-200" />
      <div className="mt-3 h-4 w-full max-w-2xl rounded bg-slate-100" />

      <div className="mt-8 grid grid-cols-2 gap-5 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 rounded-2xl border border-slate-200 bg-slate-50" />
        ))}
      </div>

      <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-72 rounded-2xl border border-slate-200 bg-slate-50" />
        ))}
      </div>
    </main>
  );
}
