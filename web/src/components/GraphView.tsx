"use client";

import cytoscape, { type Core, type ElementDefinition, type NodeSingular } from "cytoscape";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getMpAgencyGraph, type GraphData } from "@/lib/api";

const COMMUNITY_PALETTE = [
  "#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444",
  "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#84cc16",
];

function communityColor(c: number | null): string {
  if (c === null) return "#94a3b8";
  return COMMUNITY_PALETTE[c % COMMUNITY_PALETTE.length];
}

export default function GraphView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const router = useRouter();

  // Default to a threshold that renders quickly (~139 nodes) — the
  // full unfiltered graph is ~700 nodes, which is fine to explore but
  // too slow for `cose`'s default iteration count to be a sane
  // starting view. Nothing in this corpus exceeds ~15-20Cr for a
  // single MP-agency pair (MPs' annual entitlement is capped well
  // below that), so the slider's range is bounded accordingly.
  const [minValueCr, setMinValueCr] = useState(10);
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ label: string; kind: string } | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      setLoading(true);
      setError(null);
      const minValue = minValueCr * 1_00_00_000;
      try {
        const d: GraphData = await getMpAgencyGraph(minValue);
        if (!cancelled) setData(d);
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [minValueCr]);

  useEffect(() => {
    if (!containerRef.current || !data) return;

    const maxValue = Math.max(1, ...data.edges.map((e) => e.total_value));
    const elements: ElementDefinition[] = [
      ...data.nodes.map((n) => ({
        data: { id: n.id, label: n.label, kind: n.kind, community: n.community },
      })),
      ...data.edges.map((e) => ({
        data: {
          id: `${e.source}__${e.target}`,
          source: e.source,
          target: e.target,
          weight: 1 + 6 * (e.total_value / maxValue),
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele) => communityColor(ele.data("community")),
            label: "data(label)",
            "font-size": 8,
            color: "#334155",
            "text-valign": "bottom",
            "text-margin-y": 4,
            width: (ele: NodeSingular) => (ele.data("kind") === "agency" ? 22 : 12),
            height: (ele: NodeSingular) => (ele.data("kind") === "agency" ? 22 : 12),
            shape: (ele: NodeSingular) => (ele.data("kind") === "agency" ? "diamond" : "ellipse"),
            "border-width": 1,
            "border-color": "#ffffff",
          },
        },
        {
          selector: "edge",
          style: {
            width: "data(weight)",
            "line-color": "#cbd5e1",
            "curve-style": "haystack",
            opacity: 0.6,
          },
        },
        {
          selector: "node:selected",
          style: { "border-width": 3, "border-color": "#0f172a" },
        },
      ],
    });

    cy.on("tap", "node", (evt) => {
      const n = evt.target;
      setSelected({ label: n.data("label"), kind: n.data("kind") });
    });

    cy.on("dbltap", "node[kind = 'agency']", (evt) => {
      router.push(`/agencies/${encodeURIComponent(evt.target.data("label"))}`);
    });

    // Deferred to the next animation frame, not run inline above: at
    // the moment this effect fires, the flex container hasn't always
    // finished layout — cy.width() read 43px (a scrollbar-width-ish
    // default) instead of the real ~430px, `fit: true` then collapsed
    // the whole graph to zoom 1e-50 fitting a real bounding box into
    // that phantom width. A transparent, fully-populated, un-drawn
    // canvas with no console error — confirmed by sampling canvas
    // pixel data (alpha 0 everywhere) and cy.width() directly.
    //
    // A single deferred rAF resize wasn't enough to fix it reliably —
    // window.innerWidth read 0 at some points during testing, meaning
    // the pane/container's real size isn't just "one frame away", it
    // can become available on its own schedule. A ResizeObserver on
    // the container re-runs resize+layout every time its real size
    // actually changes, so whenever a valid size does show up — one
    // frame later or several — the graph corrects itself instead of
    // staying locked to whatever bogus width it read once.
    const runLayout = () => {
      cy.resize();
      cy.layout({
        name: "cose",
        animate: false,
        fit: true,
        // Default numIter (~1000, O(n^2) repulsion per iteration) was
        // slow enough on the ~700-node unfiltered graph to feel stuck;
        // 300 converges fast enough to stay interactive at the low end
        // of the value slider, at some cost to layout polish that
        // doesn't matter for an exploratory view.
        numIter: 300,
        nodeRepulsion: 8000,
        idealEdgeLength: 60,
      } as cytoscape.LayoutOptions).run();
    };

    const resizeObserver = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 10 && height > 10) runLayout();
    });
    resizeObserver.observe(containerRef.current);
    // Also try immediately in case the container is already sized —
    // the observer's first callback fires async, this covers the
    // common case without waiting on it.
    if (containerRef.current.clientWidth > 10) runLayout();

    cyRef.current = cy;
    return () => {
      resizeObserver.disconnect();
      cy.destroy();
      cyRef.current = null;
    };
  }, [data, router]);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-4 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-ink-muted">Minimum edge value</span>
          <input
            type="range"
            min={0}
            max={20}
            step={1}
            value={minValueCr}
            onChange={(e) => setMinValueCr(Number(e.target.value))}
            className="w-40"
          />
          <span className="tabular-nums text-ink-2">₹{minValueCr}Cr+</span>
        </label>
        {data && (
          <span className="text-ink-muted">
            {data.nodes.length.toLocaleString("en-IN")} nodes &middot; {data.edges.length.toLocaleString("en-IN")} edges
          </span>
        )}
        {loading && <span className="text-ink-muted">Loading…</span>}
      </div>

      <div className="flex gap-4">
        <div
          ref={containerRef}
          className="h-[560px] flex-1 rounded-lg border border-border bg-surface"
        />
        <aside className="w-56 shrink-0 rounded-lg border border-border bg-surface p-3 text-sm">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">Selection</h3>
          {selected ? (
            <div>
              <div className="text-xs uppercase tracking-wide text-ink-muted">{selected.kind === "agency" ? "Agency" : "MP"}</div>
              <div className="mt-1 text-ink-2">{selected.label}</div>
              {selected.kind === "agency" && (
                <p className="mt-2 text-xs text-ink-muted">Double-click a diamond node to open its detail page.</p>
              )}
            </div>
          ) : (
            <p className="text-ink-muted">Click a node to see it here. Diamonds are agencies, circles are MPs.</p>
          )}
          <div className="mt-4 border-t border-border-soft pt-3 text-xs text-ink-muted">
            Node color groups a Louvain community — MPs and agencies that cluster together, not a severity signal.
          </div>
        </aside>
      </div>

      {error && <p className="mt-3 text-sm text-rose-600">Could not load the graph: {error}</p>}
    </div>
  );
}
