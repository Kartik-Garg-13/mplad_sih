"""Detector metadata — the single source of truth for what each detector
is called, what it fires on, and its benign explanation (plan §08, rule 3:
"every detector carries a plausible innocent explanation, shown by
default").

This used to live only in the frontend (`web/src/lib/benignExplanations.ts`),
which meant the CSV export (see api/main.py's export endpoint) had no way to
put a benign explanation next to the evidence it explains — the restraint
would have been stripped on the one path data actually leaves the tool.
Moving it here makes it servable from `/api/detectors` and puts one copy of
this text in one place instead of two that could drift apart.

Curated per detector, not generated — generic boilerplate ("could be an
error") would defeat the purpose. `parakh.detectors.REGISTRY` is still the
authority on which detectors actually run; this module is descriptive
metadata about that same fixed set, checked against it below.
"""

from __future__ import annotations

from typing import NamedTuple


class DetectorMeta(NamedTuple):
    id: str
    tier: str
    title: str
    description: str
    benign_explanation: str


DETECTORS: dict[str, DetectorMeta] = {
    d.id: d
    for d in [
        DetectorMeta(
            "A1",
            "A",
            "Ledger contradiction",
            "A payment recorded against a work exceeds its sanctioned amount.",
            "Ledger mismatches like this often trace to a data-entry correction (an amount re-keyed after a "
            "typo), a placeholder sanction figure on a work that was later revised, or a legacy record migrated "
            "from an earlier reporting system with an out-of-order timestamp.",
        ),
        DetectorMeta(
            "A2",
            "A",
            "Phantom completion",
            "Marked complete, but little or nothing has actually been paid out.",
            "A work can be marked complete with little or nothing paid out yet if it drew on non-MPLADS "
            "co-funding (state or local body share), came in under budget, or has its final settlement payment "
            "queued for the next disbursement cycle.",
        ),
        DetectorMeta(
            "A3",
            "A",
            "Duplicate record",
            "The same work ID appears more than once in the source export.",
            "The same work ID can appear more than once in an export because of a portal re-submission after a "
            "data error, or a record carried over during a system migration — not necessarily a second, "
            "separate claim on funds.",
        ),
        DetectorMeta(
            "A4",
            "A",
            "Orphan sanction",
            "A sanctioned work is missing its agency, state, or category.",
            "A missing agency, state, or category is frequently a data-entry gap — a field left blank during "
            "upload, or dropped during a schema migration — rather than a work that was never really assigned "
            "to anyone.",
        ),
        DetectorMeta(
            "A5",
            "A",
            "Unverified completion",
            "Marked complete with no photo evidence on file.",
            "Photo evidence can be missing on file for older works predating the portal's image-upload "
            "requirement, or because of an upload failure at submission time, rather than because no work "
            "happened.",
        ),
        DetectorMeta(
            "B1",
            "B",
            "Peer cost outlier",
            "Sanctioned amount is a statistical outlier against its real peer group.",
            "Costs above the peer median can reflect genuine site conditions — difficult terrain, urban "
            "land-acquisition costs, a larger-than-typical clubbed work reported as a single entry — not "
            "necessarily inflated billing.",
        ),
        DetectorMeta(
            "B2",
            "B",
            "Cost-per-unit outlier",
            "Cost per physical unit departs from the category's peer median.",
            "An outlying cost-per-unit can come from a different material grade or construction spec than "
            "typical peers, a small quantity where fixed setup costs dominate the per-unit price, or a site "
            "needing extra site-preparation work bundled into the same sanction.",
        ),
        DetectorMeta(
            "B3",
            "B",
            "Stalled work",
            "Open well past the category's empirical P95 completion time.",
            "Stalled works are commonly explained by land-acquisition disputes, contractor litigation, monsoon "
            "or disaster-related delays, or an implementing agency handover — administrative friction, not "
            "abandonment.",
        ),
        DetectorMeta(
            "B4",
            "B",
            "Threshold bunching",
            "Sanctions cluster just under a round-rupee administrative tier.",
            "Clustering just under a round-rupee figure can reflect a genuine administrative approval tier (a "
            "lower rupee ceiling needs less sign-off) that agencies legitimately plan projects around, rather "
            "than deliberate under-reporting.",
        ),
        DetectorMeta(
            "B5",
            "B",
            "Work splitting",
            "Several similarly-worded works from one agency, clustered in time.",
            "A cluster of similar, comparably-sized works from one agency in a short window often reflects a "
            "legitimate area-wide rollout — the same standard item installed at several sites as one "
            "coordinated program — rather than one large work broken up to dodge scrutiny.",
        ),
        DetectorMeta(
            "B6",
            "B",
            "Agency concentration",
            "One agency handles an unusual share of an MP's sanctioned value.",
            "Heavy concentration in one agency is expected where a constituency sits entirely within a single "
            "implementing agency's jurisdiction, or where an MP has built a working relationship with one "
            "reliably-performing agency.",
        ),
        DetectorMeta(
            "B7",
            "B",
            "Year-end bunching",
            "A disproportionate share of sanctions land in the final 90 days.",
            "A surge of sanctions near financial year-end is a well-known, widespread pattern tied to when "
            "state treasuries release funds and when annual utilisation targets are reported — a budget-cycle "
            "artifact common across MPs, not unique to this one.",
        ),
        DetectorMeta(
            "B8",
            "B",
            "Near-duplicate funding",
            "Near-identical descriptions, same district, close in time.",
            "Near-identical descriptions in the same district and timeframe can be a legitimate second phase of "
            "one asset (e.g. a repair or extension following initial construction), or two genuinely different "
            "nearby assets described in the same terse, standard phrasing.",
        ),
    ]
}


def _check_covers_registry() -> None:
    """Fails loudly at import time if this metadata and the real detector
    registry ever diverge — a silent gap here is exactly the "restraint
    stripped on the way out" failure mode this module exists to prevent."""
    from parakh.detectors import REGISTRY

    missing = set(REGISTRY) - set(DETECTORS)
    if missing:
        raise RuntimeError(
            f"detector_meta.py is missing metadata for registered detector(s): {sorted(missing)}"
        )


_check_covers_registry()
