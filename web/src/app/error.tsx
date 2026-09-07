"use client";

export default function Error({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center px-6 text-center">
      <h1 className="text-lg font-semibold text-ink-2">Couldn&rsquo;t load this page</h1>
      <p className="mt-2 text-sm text-ink-muted">
        PARAKH&rsquo;s API didn&rsquo;t respond. If you&rsquo;re running this locally, check that the FastAPI
        server is up (<code className="rounded bg-slate-100 px-1 py-0.5 text-xs">uvicorn parakh.api.main:app</code>).
      </p>
      <button
        onClick={() => retry()}
        className="mt-5 rounded-md bg-navy px-4 py-1.5 text-sm font-medium text-white hover:bg-navy-panel"
      >
        Try again
      </button>
      {process.env.NODE_ENV === "development" && (
        <p className="mt-4 max-w-md break-words text-xs text-ink-muted">{error.message}</p>
      )}
    </main>
  );
}
