# PARAKH — 3-minute full walkthrough

Team DOOM (415) · SIH26102 · Every page in the header, in one pass.

~295 spoken words (~2:00 at 150 wpm) plus ~55s of switching tabs. Thirteen
stops in 180 seconds is about 14 seconds each, so this is grouped into four
movements rather than read as a list — **say the movement's framing line, then
the pages inside it go fast.**

*Italics are screen directions. Plain text is what you say.*

---

## Pre-flight

```bash
curl -s -o /dev/null -w "api %{http_code}\n" http://127.0.0.1:8020/api/stats
curl -s -o /dev/null -w "web %{http_code}\n" http://127.0.0.1:3010/
```

Both must print `200`. **Open these tabs left to right, in this order** — the
run is one pass along the header, so you never navigate backwards.

| # | Tab | Header item |
|---|---|---|
| 1 | `/` | (the wordmark) |
| 2 | `/flags` | Flags |
| 3 | `/works/WS/MP18368/2025-2026/241282` | *(opened from Flags)* |
| 4 | `/unflagged` | No flags |
| 5 | `/reviewed` | Reviewed |
| 6 | `/dashboard` | Dashboard |
| 7 | `/agencies` | Agencies |
| 8 | `/graph` | Graph |
| 9 | `/at-risk` | At-risk |
| 10 | `/constituencies` | Constituencies |
| 11 | `/datasets` | Datasets |
| 12 | `/methodology` | Methodology |
| 13 | `/validation` | Validation |

---

## 0:00–0:12 — Where you are

*Tab 1, `/`.*

PARAKH, running on the full public MPLADS corpus — **1,31,437 works**.

The workflow is one loop: **detect, show the evidence, let a human decide,
record the decision.** The header is that loop left to right — the queue first,
then everything that justifies it.

---

## Movement 1 · 0:12–0:52 — The queue, and what a flag actually is

*Tab 2, `/flags`. Point at the tier letters, then the detector chips.*

This is the queue. **37,566 works** carry at least one flag. The tier shows
before anything else — **A is arithmetic, B is peer-relative.** Thirteen
detectors, filterable here.

*Tab 3, the work detail. Slow down — this is the one screen that matters.*

₹2.85 crore of high-mast lights in Chandauli. B1 says **144 times the peer
median, across 3,223 peers** — the peer group and the count stated on screen,
not a score you have to trust.

*Point at the benign explanation, then the description.*

And this, shown **by default** rather than behind a tooltip: the plausible
innocent explanation. Now read the description — **120 different locations.** It
is a bundle being measured against a per-light median.

The tool defuses its own flag, before anyone accuses anybody. That is the whole
design in one screen.

## Movement 2 · 0:52–1:08 — The rest of the review loop

*Tab 4, `/unflagged`.*

**No flags** is the other side: **60,474 works** every detector examined and
cleared — kept separate from works never evaluated, because those are different
claims.

*Tab 5, `/reviewed`.*

And **Reviewed** is where a flag goes once a reviewer closes it with a note.
Suppressed, never deleted, always undoable.

## Movement 3 · 1:08–1:48 — Reading the corpus, and following the money

*Tab 6, `/dashboard`.*

**Dashboard** aggregates that same database — by state, year, category, tier.

*Tab 7, `/agencies`.*

**Agencies** — 761 of them, ranked by value, with two signals: thin-file
agencies, and 19 names appearing under more than one state.

*Tab 8, `/graph`.*

**Graph** is those same relationships as a network — 1,473 nodes, clustered by
Louvain community detection.

*Tab 9, `/at-risk`.*

**At-risk** is the one machine-learning model: LightGBM predicting which of
31,031 still-open works will stall, tested on a time split, never a random one.

*Tab 10, `/constituencies`.*

**Constituencies** scores 542 seats — framed as delivery performance, not
integrity. That wording is deliberate.

## Movement 4 · 1:48–2:20 — Showing our work

*Tab 11, `/datasets`.*

**Datasets** shows exactly what was ingested — Lok Sabha and Rajya Sabha, 18th
term — and lets you upload another and rebuild.

*Tab 12, `/methodology`.*

**Methodology** documents all thirteen detectors, and the three we planned and
did not build.

*Tab 13, `/validation`.*

**Validation** publishes five independent methods as they came out — including
the manual review of our own top 50, where **zero** were genuinely irregular.

## Close · 2:20–3:00 — The refusal

*Any tab. Click "Ask about this data", bottom right.*

And on every page, this. **No language model** — it answers from rows in the
database, so it works offline and cannot invent a figure.

*Type: `which MP is the most suspicious?` — wait for it.*

It refuses. Flags attach to works, never to people.

**That is not a prompt asking it to be careful. That is the code.**

---

## Pacing rules

- **Movements 3 and 4 are eight pages in 72 seconds.** One sentence each, then
  move. Do not stop to explain a chart — the framing line has already told the
  judge why the page exists.
- **The work detail is the only stop worth going over time on.** If you are
  behind, take it out of Movement 3, not out of that screen.
- **The refusal is the ending.** Leave it 20 seconds even if everything else slips.

## If you have only 2 minutes

Keep the landing page, Movement 1, and the refusal. Compress Movements 2–4 into
one line while scrolling the header: *"the rest of the header is the evidence —
the cleared works, the aggregates, the agency network, the stall model, the
datasets, the methodology, and five validation methods."*

## Numbers on this page

All read from the live corpus on the current build. If the pipeline is rebuilt,
re-check: works 1,31,437 · flagged 37,566 · cleared 60,474 · agencies 761 ·
graph nodes 1,473 · at-risk 31,031 · constituencies 542.
