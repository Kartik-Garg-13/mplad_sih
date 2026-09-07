import { getDatasets } from "@/lib/api";
import DatasetsClient from "@/components/datasets/DatasetsClient";

export default async function DatasetsPage() {
  const data = await getDatasets();

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <h1 className="text-xl font-semibold text-ink-2">Datasets</h1>
      <p className="mt-2 max-w-2xl text-sm text-ink-muted">
        PARAKH ships with the eSAKSHI Lok Sabha and Rajya Sabha exports (18th term). Add another set of the same
        exports — a different constituency, a later snapshot, a pilot district — and it joins the corpus
        alongside them. Every screen can then be filtered down to just that source.
      </p>
      <DatasetsClient initial={data} />
    </main>
  );
}
