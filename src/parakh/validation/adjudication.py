"""Plan §07, method 3 — manual adjudication: review the top 50 flags by
hand, classify each as plausibly-irregular, benign-explained, or
undecided, and report the full three-way split.

Reviewed by hand against the real, ranked top 50 (the flag list's own
default ordering: has_tier_a desc, then n_flags desc) from the actual
built database. The result is a genuine finding, not a placeholder:
every one of the top 50 belongs to one of eight batch-procurement
clusters — one MP/agency sanctioning many near-identical, similarly-
priced works (streetlights, water tankers, library books, multi-gym
sets, a CC-road-and-drainage pair) across many sites within a short
window. That is exactly B5/B8's documented benign-explanation pattern,
not a novel one invented for this review, plus the corpus-wide "no
photo evidence on file" (A5) — expected on 76.2% of all works (see
provenance), not distinguishing for these 50 specifically.

The honest denominator, per the plan: 0 of 50 plausibly-irregular, 1
undecided, 49 benign-explained. This is itself a useful result about
the *ranking heuristic*, not just the detectors — see the module
docstring on evaluate.py for the same finding from a different angle
(precision@50 and @100 on synthetic injections were both 0%, for the
same underlying reason: large legitimate batches out-rank rarer,
single-flag anomalies under a plain has_tier_a/n_flags sort).
"""

from __future__ import annotations

CLUSTERS = [
    {
        "cluster": "Gaya library books",
        "state": "Bihar",
        "mp_name": "ABHAY KUMAR SINHA",
        "implementing_agency": "DISTRICT PLANNING OFFICER GAYA_IDA",
        "category": "Purchase of books and periodicals for libraries/digitization of library books",
        "n_works_in_top50": 4,
        "classification": "benign_explained",
        "note": "Same standard library-book purchase (~Rs 4.74L-4.99L each) across many schools, one MP, 30-day recommendation window — the documented B5/B8 batch-rollout pattern.",
    },
    {
        "cluster": "Fazilka mobile water tankers",
        "state": "Punjab",
        "mp_name": "SHER SINGH GHUBAYA",
        "implementing_agency": "DEPUTY COMMISSIONER FAZILKA_IDA",
        "category": "Purchase of mobile water tankers",
        "n_works_in_top50": 15,
        "classification": "benign_explained",
        "note": "47 near-identical 3000L steel water-tanker purchases (~Rs 2.40L-2.41L each) across the district — the single largest cluster in the top 50.",
    },
    {
        "cluster": "Bangalore Urban Machohalli village CC-road + drainage",
        "state": "Karnataka",
        "mp_name": "Shri Jaggesh (2022-28) (2022-2028)",
        "implementing_agency": "DEPUTY COMMISSIONER BANGALORE URBAN_IDA",
        "category": "Construction of roads / Providing drains and gutters",
        "n_works_in_top50": 9,
        "classification": "benign_explained",
        "note": "A paired road-and-drainage upgrade programme across one village's several stretches — CC-road and CC-drainage works interleaved, same panchayat, same ~Rs 4.9-5.0L band.",
    },
    {
        "cluster": "Patna PCC road and underground drain",
        "state": "Bihar",
        "mp_name": "Dr. Bhim Singh (2024-30) (2024-2030)",
        "implementing_agency": "DISTRICT PLANNING OFFICER PATNA_IDA",
        "category": "Construction of roads, link roads, pathways or any other road with or without drainage system",
        "n_works_in_top50": 3,
        "classification": "benign_explained",
        "note": "Same PCC-road-and-drain template at 9 sites district-wide; amounts vary with each stretch's real length (Rs 11.9L-14.9L), not uniform — consistent with genuine site-specific road works, not padding.",
    },
    {
        "cluster": "Hamirpur LED semi-high-mast lights",
        "state": "Uttar Pradesh",
        "mp_name": "Shri Baburam Nishad (2022-28) (2022-2028)",
        "implementing_agency": "DISTRICT MAGISTRATE HAMIRPUR_2",
        "category": "Lighting of public spaces",
        "n_works_in_top50": 7,
        "classification": "benign_explained",
        "note": "22-site LED semi-high-mast-light rollout, ~Rs 2.39-2.41L each — same fixture spec repeated across the district.",
    },
    {
        "cluster": "Pilibhit high-mast street lights",
        "state": "Uttar Pradesh",
        "mp_name": "Shri Javed Ali Khan (2022-28) (2022-2028)",
        "implementing_agency": "DISTRICT MAGISTRAE PILIBHIT_IDA",
        "category": "Street lights",
        "n_works_in_top50": 2,
        "classification": "benign_explained",
        "note": "105-site street-light rollout. Also carries a mild B1 flag (1.2x peer median, Rs 2.83L vs Rs 2.43L) — a real but small departure, consistent with a slightly larger fixture spec, not a distinguishing signal on its own.",
    },
    {
        "cluster": "Pratapgarh mobile water tanker",
        "state": "Uttar Pradesh",
        "mp_name": "Shri Amar Pal Maurya (2024-30) (2024-2030)",
        "implementing_agency": "DISTRICT MAGISTRAE PRATAPGARH_IDA",
        "category": "Purchase of mobile water tankers",
        "n_works_in_top50": 1,
        "classification": "undecided",
        "note": "Part of an 11-work batch (same benign shape as the others), but this single unit is sanctioned at Rs 5.31L against a Rs 2.49L state peer median (2.1x, n=33) — a real, not-explained-by-batch-shape cost departure worth a second look, not resolved by this review alone.",
    },
    {
        "cluster": "Darbhanga multi-gym equipment",
        "state": "Bihar",
        "mp_name": "Shri Shambhu Sharan Patel (2022-28) (2022-2028)",
        "implementing_agency": "DISTRICT PLANNING OFFICER DARBANGA_IDA",
        "category": "Installation of multi-gym equipment",
        "n_works_in_top50": 9,
        "classification": "benign_explained",
        "note": "Identical Rs 9.83L multi-gym equipment set installed at 9 different named schools across one block — same vendor spec text repeated verbatim per site, one MP, one 30-day window.",
    },
]


def adjudication_result() -> dict:
    n_total = sum(c["n_works_in_top50"] for c in CLUSTERS)
    by_class: dict[str, int] = {}
    for c in CLUSTERS:
        by_class[c["classification"]] = by_class.get(c["classification"], 0) + c["n_works_in_top50"]
    return {
        "n_reviewed": n_total,
        "n_clusters": len(CLUSTERS),
        "by_classification": by_class,
        "clusters": CLUSTERS,
        "conclusion": (
            f"{by_class.get('plausibly_irregular', 0)} of {n_total} plausibly irregular, "
            f"{by_class.get('undecided', 0)} undecided, {by_class.get('benign_explained', 0)} benign-explained. "
            "All 50 reduce to 8 real batch-procurement programmes — the ranking heuristic (has_tier_a desc, "
            "n_flags desc) surfaces large legitimate rollouts ahead of rarer single-instance anomalies; see "
            "evaluate.py's precision@k finding for the same effect from the synthetic-injection side."
        ),
    }
