# PARAKH — 5-minute demo script (SIH26102)

Timed for ~300s at ~135 wpm (~675 words of narration). Screen
directions in *italics*; narration in plain text. Every number below
is pulled live from the built database — re-check before presenting
if the data has been rebuilt since.

---

## 0:00–0:25 — The problem

*On screen: title slide, then the eSAKSHI portal or raw MPLADS data.*

"MPLADS puts &#8377;5 crore a year in every MP's hands for local
infrastructure. Across the 18th Lok Sabha and Rajya Sabha, that's
1.3 lakh sanctioned works and 1.09 lakh payments, through 761 district
agencies — no way to see it as a whole.

Real irregularities exist. But an AI that decides which MP is at
fault is a defamation engine, not a tool. That's the trap this problem
statement warns about, and it's what we designed against first."

## 0:25–0:50 — What PARAKH is

*On screen: homepage, `/` — the flag list.*

"PARAKH is a review queue, not a verdict. 13 detectors — 5
deterministic, 8 peer-relative statistical — each producing a flag
that says 'this warrants a look,' states its evidence in one
sentence, and states a plausible innocent explanation right beside it.
Works and agencies get ranked here. MPs never do."

## 0:50–2:20 — Live walkthrough

*On screen: scroll the flag list, click into a Tier A work.*

"131,437 real works, 38,934 flagged — about 30 percent. Rose is
Tier A: a deterministic contradiction, like a payment exceeding its
sanction. Amber is Tier B: a statistical outlier against a stated
peer group, abstaining below 30 peers so it never flags on noise.

*Click a work with an A5 flag.*

This one's marked complete with no photo on file — and right below
it, the benign explanation: that predates the portal's photo
requirement for many older works. Shown by default, every detector.

*Click 'mark reviewed — explained.'*

A reviewer who's satisfied can mark it 'reviewed — explained.' That
suppresses it from the queue — it doesn't delete the flag, and it's
reversible.

*Navigate to `/graph`.*

The agency network, Louvain-clustered. 27 thin-file agencies; 19
whose name spans more than one state — mostly the 2014 Telangana
split, one real UP/J&amp;K mismatch worth a look.

*Navigate to `/at-risk`.*

A LightGBM model flags on-track works likely to stall — time-split,
never random, so it's tested on the future. PR-AUC 0.54 against a
0.38 base rate.

*Navigate to `/constituencies`.*

And a scorecard for all 542 Lok Sabha seats — completion, fund use —
framed explicitly as district performance, not integrity. That line
is on the page itself."

## 2:20–3:20 — How we know it's honest

*On screen: `/validation`.*

"How do you validate anomaly detection with no labels? Five real
checks, not a slide. We injected 182 synthetic anomalies of five
types — four hit 100% recall. We checked two real, named CAG and
press cases by hand — zero matched, and we say why: this corpus is
the 18th term only; CAG audits review works years later.

We reviewed the real top 50 ourselves: zero plausibly irregular, one
undecided, forty-nine legitimate batch programmes — the same water
tanker or streetlight bought at a dozen sites at once. That's the
detectors working, and us reporting it straight."

## 3:20–4:00 — What we didn't build

*On screen: `/methodology`, the Tier C note.*

"The plan scoped a third tier — an Isolation Forest, an LOF, a
composite priority score. We didn't build it. Thirteen of sixteen
planned detectors shipped, and we say so on the methodology page — a
tool built on restraint has to apply that restraint to its own
claims."

## 4:00–4:35 — Enforcement, not intention

*On screen: quick flash of the vocabulary-lock test.*

"Every rule here is enforced, not written down. A CI test greps the
whole codebase for six banned words before every build. It's caught
real violations — even code that tried to explain the ban by quoting
the words it bans. We rewrote those instead of carving an exception."

## 4:35–5:00 — Close

"PARAKH: 131K works, 13 real detectors, five validation methods, and
a framing contract enforced by code. It doesn't hand down a verdict.
It tells you where to look, and why — and just as plainly,
where it can't tell you anything yet."

---

## Timing checkpoints for dry runs

| Checkpoint | Target elapsed |
|---|---|
| Finish "the problem" | 0:25 |
| Finish "what PARAKH is" | 0:50 |
| Finish live walkthrough | 2:20 |
| Finish "how we know it's honest" | 3:20 |
| Finish "what we didn't build" | 4:00 |
| Finish enforcement | 4:35 |
| Hard stop | 5:00 |

Run it three times against a real clock. If a section runs long, cut
from the live walkthrough first (it has five page transitions to
compress). Never cut the validation or "what we didn't build"
sections — those are the differentiator, per the plan's own cut
order.
