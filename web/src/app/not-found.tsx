import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center px-6 text-center">
      <h1 className="text-lg font-semibold text-ink-2">Not found</h1>
      <p className="mt-2 text-sm text-ink-muted">
        Nothing here &mdash; the work, agency, or page you&rsquo;re looking for doesn&rsquo;t exist in this corpus.
      </p>
      <Link
        href="/flags"
        className="mt-5 rounded-md bg-navy px-4 py-1.5 text-sm font-medium text-white hover:bg-navy-panel"
      >
        Back to flag list
      </Link>
    </main>
  );
}
