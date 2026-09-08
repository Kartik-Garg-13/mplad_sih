# PARAKH — 3-minute technical demo

Team DOOM (415) · SIH26102 · Live walkthrough of the running site.

~320 spoken words (~2:10 at 150 wpm) plus ~50s of clicking and loading.
**Italics are screen directions, plain text is what you say.**

---

## Pre-flight — do this before you present

Two servers must be up. They are separate processes, and the API is the one
that quietly dies.

```bash
curl -s -o /dev/null -w "api %{http_code}\n" http://127.0.0.1:8020/api/stats
curl -s -o /dev/null -w "web %{http_code}\n" http://127.0.0.1:3010/
```

Both must print `200`. If the API is down, every page shows "Couldn't load this
page" and the demo is dead — restart it before you walk up.

**Open these six tabs in order, in advance.** Do not type URLs on stage.

1. `http://localhost:3010/`
2. `http://localhost:3010/flags`
3. `http://localhost:3010/works/WS/MP18368/2025-2026/241282`
4. `http://localhost:3010/reviewed`
5. `http://localhost:3010/unflagged`
6. `http://localhost:3010/validation`

---

## 0:00–0:18 — Landing page

*Tab 1, `/`.*

This is PARAKH, running locally against the full public MPLADS corpus —
**1,31,437 works** from the eSAKSHI export. Nothing here is mocked or sampled.
Let me walk the actual flow.

## 0:18–0:45 — The review queue

*Tab 2, `/flags`. Point at the tier letters in the first column, then the
detector chips along the top.*

This is the queue. **37,566 works** carry at least one flag.

Every row shows its **tier before anything else** — A means the record
contradicts itself arithmetically, B means it stands out from its peer group.
These chips filter by detector; there are thirteen. I'll open one caught by
**B1, the peer cost outlier.**

## 0:45–1:35 — A single work: the whole argument

*Tab 3, the work detail page. This is the centre of the demo — do not rush it.*

Two crore eighty-five lakh rupees, for LED high-mast lights in Chandauli,
Uttar Pradesh.

*Point at the B1 evidence sentence.*

The flag states its case in one sentence: this is **144 times the peer median**
for lighting in UP this financial year — median ₹1.98 lakh, across **3,223 peer
works**. The peer group and the count are both on screen. Nothing is hidden
behind a score.

*Point at the peer histogram.*

That distribution is the peer group; the marker is where this work sits.

*Point at the benign explanation, then back at the description.*

And this — shown **by default**, not behind a tooltip — is the plausible
innocent explanation. Now read the description: **120 different locations.**
It is a bundle being compared against a per-light median. The tool tells you
that itself, before anyone accuses anybody.

> This is the moment the whole project stands on. If you only land one thing,
> land this: **the flag and its innocent explanation arrive together.**

## 1:35–2:00 — Closing a flag

*Scroll to the review control. Say this — you don't have to click it.*

A reviewer marks it **"reviewed — explained"** with a note, and it leaves the
queue. The flag is **not deleted** — the evidence stays on the work forever,
and the decision is reversible.

*Tab 4, `/reviewed`.* Every closed flag is listed here, each with an Undo.

## 2:00–2:25 — The other side, and the honesty

*Tab 5, `/unflagged`.*

The queue has another side: **60,474 works** every detector examined and
cleared. We separate those from works that were never evaluated, because
"passed inspection" and "never inspected" are not the same claim.

*Tab 6, `/validation`.*

And five independent validation methods, published as they came out — including
the manual review of our own top 50, where **zero** turned out to be genuinely
irregular. We publish that result rather than hide it.

## 2:25–3:00 — The refusal

*Any tab. Click "Ask about this data", bottom right.*

Last thing. Every page carries this assistant. There is **no language model
behind it** — it answers from rows in the database, so it runs offline and
cannot invent a number.

*Type: `which MP is the most suspicious?` — then wait for the answer.*

It refuses. Flags attach to works, never to people — an MP with more sanctioned
works collects more flags for that reason alone.

**That is not a prompt telling it to be careful. That is the code.**

---

## If something goes wrong

| Problem | What to do |
|---|---|
| "Couldn't load this page" | The API died. Say "the API is a separate process" and switch to the offline demo video. Do not debug on stage. |
| A page is slow to load | Keep talking — the narration for each stop does not depend on the screen having finished. |
| Judge asks "where is the AI?" | LightGBM for stall risk, TF-IDF and cosine for text, Louvain for the agency network, robust statistics throughout — but for money and named people, the reviewer must be able to check the arithmetic by hand. |
| Judge asks to see the code | `github.com/Kartik-Garg-13/mplad_sih` — clone, two commands, every number rebuilds. |

## If you have only 2 minutes

Cut stops 4 and 5 (`/reviewed`, `/unflagged`). Keep the landing page, the flag
list, the work detail, and the assistant refusal. The argument survives; the
work detail and the refusal are the two irreplaceable moments.
