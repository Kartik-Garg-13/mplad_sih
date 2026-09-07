import Link from "next/link";
import { getDetectors, getFlags } from "@/lib/api";
import ReviewSession from "@/components/review/ReviewSession";

type SearchParams = { [key: string]: string | string[] | undefined };
function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

// One batch, fetched once at the start of a session — the queue a reviewer
// works through does not shift under them as they go (see ReviewSession's
// own note on why marking a flag reviewed doesn't remove it from the
// loaded batch). 50 is a realistic single sitting, not the whole filtered
// queue, which can run into the tens of thousands.
const BATCH_SIZE = 50;

export default async function ReviewPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const filters = {
    detector: one(sp.detector),
    tier: one(sp.tier),
    state: one(sp.state),
    category: one(sp.category),
    search: one(sp.search),
    source: one(sp.source),
  };

  const [batch, { detectors }] = await Promise.all([
    getFlags({ ...filters, page: "1", page_size: String(BATCH_SIZE) }),
    getDetectors(),
  ]);

  if (batch.results.length === 0) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16 text-center">
        <h1 className="font-display text-2xl font-semibold text-ink-2">Nothing to review</h1>
        <p className="mt-2 text-sm text-ink-muted">
          No flagged works match these filters right now &mdash; either everything here has already been
          reviewed, or the filters are too narrow.
        </p>
        <Link
          href="/flags"
          className="mt-5 inline-block rounded-md bg-navy px-4 py-1.5 text-sm font-medium text-white hover:bg-navy-panel"
        >
          Back to flag list
        </Link>
      </main>
    );
  }

  return (
    <ReviewSession
      queue={batch.results}
      totalMatchingFilters={batch.total}
      detectors={detectors}
      filters={filters}
    />
  );
}
