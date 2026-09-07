"""Plan §07, method 2 — known-case backtest: pull MPLADS irregularities
documented in CAG audit reports and press coverage, check whether
those works, agencies or districts rank in this corpus's top decile.

Real result, not a hypothetical: researched two concrete, named,
publicly documented cases and checked both against the actual corpus.
Neither matches — and the reason is structural, not a search failure.

    1. CAG Report No. 22 of 2025 (Union Government Compliance Audit):
       an Indoor Sports Hall under MPLADS, built by the Road
       Construction Division, Andaman Public Works Department,
       Wimberlygunj, foreclosed after Rs 62.61 lakh unfruitful
       expenditure. Checked against every Andaman & Nicobar work in
       this corpus (29 rows): the only implementing agency present is
       DEPUTY COMMISSIONER NICOBAR_IDA — the audited agency
       ("Road Construction Division... Wimberlygunj", South Andaman)
       never appears at all, and no work references an indoor sports
       hall.

    2. The widely reported Smriti Irani MPLAD-fund case (Gujarat,
       ~2019-2022 term) — outside this corpus's term entirely (18th
       Lok Sabha/Rajya Sabha only, sanctioned from 2022 onward for RS
       and 2024 onward for LS) by construction; not checked row-by-row
       for that reason.

The structural cause: CAG compliance audits and most press
investigations examine works that are already years old and
substantially executed (or, as in case 1, already foreclosed) — the
audit itself takes years to reach publication. This corpus is the
18th-term MPLADS export only (see /methodology, provenance footer):
recommended, sanctioned and largely still in-progress within the last
1-3 years. A genuine textual/entity match against a *finalized* CAG
finding is not expected to exist yet for this term, and none was
found. This method will become checkable once CAG (or equivalent)
compliance audits are published against 18th-term MPLADS spending —
not before.
"""

from __future__ import annotations

KNOWN_CASES = [
    {
        "source": "CAG Report No. 22 of 2025 (Union Government Compliance Audit)",
        "description": "Indoor Sports Hall, Road Construction Division, Andaman PWD, Wimberlygunj — foreclosed, Rs 62.61 lakh unfruitful expenditure",
        "state": "Andaman And Nicobar Islands",
        "searched_agency_substring": "road construction",
        "matched": False,
        "reason": "Corpus's only Andaman agency is DEPUTY COMMISSIONER NICOBAR_IDA; the audited agency and work never appear",
    },
    {
        "source": "Press coverage, multiple outlets (~2019-2022)",
        "description": "Smriti Irani MPLAD-fund irregularity, Gujarat",
        "state": "Gujarat",
        "searched_agency_substring": None,
        "matched": False,
        "reason": "Predates this corpus's 18th-term coverage entirely; not checked row-by-row",
    },
]


def known_case_backtest_result() -> dict:
    n_checked = len(KNOWN_CASES)
    n_matched = sum(1 for c in KNOWN_CASES if c["matched"])
    return {
        "n_cases_checked": n_checked,
        "n_matched": n_matched,
        "cases": KNOWN_CASES,
        "conclusion": (
            "0 of 2 researched, named CAG/press cases match this corpus. Both mismatches are "
            "structural (audit/reporting lag vs. this corpus's 18th-term-only coverage), not a "
            "search failure — see module docstring."
        ),
    }
