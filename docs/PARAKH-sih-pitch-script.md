# PARAKH — 4-minute SIH pitch script

Team DOOM (415) · SIH26102 · Deck: `docs/PARAKH-SIH2026-idea.pptx`

614 spoken words. At a measured pace (~150 wpm) that is **4:06**; dropping the
three *italic* sentences brings it to **3:53**, which is the version to rehearse.

Markers are cumulative clock time. If you are behind at a slide change, cut the
italic sentence in that section — each is written to come out without leaving a gap.

---

## Slide 1 — Title · 0:00–0:18

Good morning. We're team DOOM, and this is **PARAKH** — problem statement
SIH26102, anomaly detection in the MPLADS scheme.

Our entire project comes down to one line on this slide: **a review queue, not
a verdict.** Let me show you why that distinction decides everything else.

> **Delivery:** Land "not a verdict" and pause for a beat before advancing. It is
> the thesis; everything after this is evidence for it.

---

## Slide 2 — Idea · 0:18–1:22

MPLADS gives every Member of Parliament five crore rupees a year for local
works. This term alone, that is **1,31,437 works**. The data is public, but
sanctions, payments and completion sit in separate exports that are never
joined. So nobody — citizen, auditor or ministry — can see the scheme whole.
*Manual audit reaches a small sample, years after the money moved.*

Now the trap in this problem statement: the obvious build is a model that
scores every MP and names the worst ones. **That tool is a defamation engine,
not oversight** — because an MP with more sanctioned works collects more flags
for that reason alone.

So we built it the other way round. We join the exports into one corpus.
Thirteen detectors surface works that warrant a second look. Every flag states
its evidence in one plain sentence, and carries a plausible innocent
explanation beside it.

**Flags attach to works. We never rank Members of Parliament.**

> **Delivery:** "Defamation engine" is the line judges remember. Slow down for it.

---

## Slide 3 — Technical approach · 1:22–2:18

Everything is computed in advance, in a batch job. Raw CSVs go through Polars
into Parquet. Thirteen detectors run offline into DuckDB. FastAPI serves it
read-only — every endpoint is a SELECT, so the API *cannot* compute a detector
even if asked.

The detectors sit in two tiers, and the tier is always visible next to the flag.

**Tier A is arithmetic** — a payment larger than the sanction it belongs to, a
completion date before the sanction date, a work marked complete with nothing
paid. You verify those with a calculator, not statistics.

**Tier B is peer-relative** — this work costs far more than similar works in the
same category and state. Every Tier B flag states its peer group and its n. And
if a peer group has fewer than thirty members, **the detector abstains rather
than guess.**

> **Delivery:** If asked "where is the AI?" — LightGBM for stall prediction,
> TF-IDF for text similarity, Louvain for the agency network, robust statistics
> throughout.

---

## Slide 4 — Feasibility and viability · 2:18–3:13

Is it feasible? It is already running, end to end, on the full public corpus.
Batch and deterministic — no GPU, no per-query cost, no internet at run time.
Entirely open source. A hundred and seventy-two automated tests.

The risks, and how we handle each one. Naming individuals would defame — so
ranking members is **refused in code**, not by policy. Source fields are sparse
— so detectors abstain rather than infer. There is no labelled ground truth —
so we run five independent validation methods and publish all five, *including
the ones that came out badly.*

And we apply that same restraint to ourselves. We planned sixteen detectors and
shipped thirteen. The third tier — an Isolation Forest and a composite priority
score — we did not build. That is stated inside the product, not just here.

> **Delivery:** Say the 13-of-16 line with confidence, not apology. Volunteering
> it is what makes the other numbers believable.

---

## Slide 5 — Impact and benefits · 3:13–3:47

The impact. For the ministry and for districts — a worklist ordered by evidence
instead of by hunch. For auditors — a reproducible shortlist with the
arithmetic already shown. For citizens and press — the same public data,
finally joined. *And for implementing agencies, a chance to explain an ordinary
pattern before anything escalates.*

Before PARAKH: oversight by small sample, years late, surfacing as allegations
about people. After: one corpus, **37,701 works flagged with evidence
attached**, and **60,339 examined by every detector and cleared.**

---

## Slide 6 — Research, references, close · 3:47–4:06

Public data, published methods, and a repository anyone can clone and run —
two commands rebuild every number on these slides.

We don't tell anyone who is at fault. We show which records don't add up, what
would explain them, and we let a human decide.

Thank you.

> **Delivery:** Stop on "let a human decide." Do not add a summary after it.

---

## If you are cut short at 3 minutes

Drop Slide 5 entirely and go from Slide 4 straight to the closing two
sentences. The argument survives: problem → restraint → how it works → honesty
→ close. Impact is the only section that repeats what the deck already shows.

## The three numbers to never get wrong

- **1,31,437** works ingested
- **13 of 16** detectors shipped
- **0** rankings of any Member of Parliament
