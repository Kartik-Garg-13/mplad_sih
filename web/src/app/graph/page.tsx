import Link from "next/link";
import GraphView from "@/components/GraphView";

export default function GraphPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <Link href="/flags" className="text-sm text-ink-muted hover:text-ink-2">
        &larr; Flag list
      </Link>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink-2">Agency network</h1>
      <p className="mt-1 mb-6 max-w-2xl text-sm text-ink-muted">
        Every MP&ndash;agency relationship worth at least the threshold below, across the whole corpus. See{" "}
        <Link href="/agencies" className="underline decoration-border underline-offset-2 hover:decoration-ink-muted">
          the agencies list
        </Link>{" "}
        for the thin-file and cross-state findings as a sortable table instead.
      </p>
      <GraphView />
    </main>
  );
}
