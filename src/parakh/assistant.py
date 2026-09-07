"""Grounded question answering over the built corpus (plan §08).

Every answer this module returns is assembled from rows it just read out
of parakh.duckdb, or from `detector_meta`. There is no language model and
no free-text generation anywhere in the path: a question either matches a
recognised intent and gets an answer built from real values, or it
matches nothing and gets told what can be asked instead.

That is a deliberate choice rather than a limitation. A generative
assistant sitting on this corpus would be the single easiest way to undo
the restraint the rest of the project enforces — it would happily answer
"which member is the worst offender", a question this tool exists
specifically not to answer. A closed intent set cannot be talked past by
rephrasing, and `decline_mp_ranking` below turns that refusal into a
first-class, tested behaviour instead of a prompt someone can work around.

The same reason explains why nothing here matches on accusatory words:
recognising them would mean writing them, and `tests/test_vocabulary_lock`
scans this file. Intents are matched on question *shape* instead, which is
what plan §08 rule 5 is actually about — ranking people by flag count is
the problem, whichever words the question uses to ask for it.
"""

from __future__ import annotations

import re
from typing import Any, Callable, NamedTuple

import duckdb

from parakh.detector_meta import DETECTORS

SITE_LINKS = {
    "flags": ("Flag list", "/flags"),
    "unflagged": ("Works with no flags", "/unflagged"),
    "dashboard": ("Dashboard", "/dashboard"),
    "methodology": ("Methodology", "/methodology"),
    "validation": ("Validation", "/validation"),
    "agencies": ("Agencies", "/agencies"),
    "constituencies": ("Constituencies", "/constituencies"),
    "reviewed": ("Reviewed", "/reviewed"),
}


class Answer(NamedTuple):
    intent: str
    text: str
    data: dict[str, Any]
    links: list[dict[str, str]]
    suggestions: list[str]
    declined: bool


def _link(key: str, href: str | None = None, label: str | None = None) -> dict[str, str]:
    default_label, default_href = SITE_LINKS.get(key, (key, "/"))
    return {"label": label or default_label, "href": href or default_href}


def _grouped(n: int) -> str:
    """Indian digit grouping — 1,09,281 rather than 109,281.

    The rest of the app formats through `toLocaleString("en-IN")`; an
    assistant answering in a different convention next to a table using
    this one reads like it is quoting a different number.
    """
    s = str(abs(int(n)))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(?<=\d)(?=(\d\d)+$)", ",", head)
        s = f"{head},{tail}"
    return ("-" if n < 0 else "") + s


def _amount(rupees: float | None) -> str:
    if rupees is None:
        return "not recorded"
    if abs(rupees) >= 1_00_00_000:
        return f"Rs {rupees / 1_00_00_000:.2f} Cr"
    if abs(rupees) >= 1_00_000:
        return f"Rs {rupees / 1_00_000:.2f} L"
    return f"Rs {_grouped(rupees)}"


def _normalise(question: str) -> str:
    return re.sub(r"[^a-z0-9\s/-]", " ", question.lower()).strip()


def _rows(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> list[dict[str, Any]]:
    result = con.execute(sql, params or [])
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row)) for row in result.fetchall()]


def _scalar(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> Any:
    row = con.execute(sql, params or []).fetchone()
    return row[0] if row else None


# --- intent handlers -------------------------------------------------------
# Each takes the normalised question plus its regex match and returns an
# Answer. Registration order below is significant: the decline rule is
# matched before any counting intent, so a ranking question can never fall
# through into an answer that ranks.


def _decline_mp_ranking(con, q: str, m: re.Match) -> Answer:
    return Answer(
        intent="decline_mp_ranking",
        text=(
            "That is the one question this tool is built not to answer. Flags attach to individual "
            "works, never to the member who recommended them, and a count of flags is not a measure "
            "of a person — an MP with more sanctioned works will collect more flags for that reason "
            "alone, and every flag here has an ordinary explanation shown next to it. Ranking members "
            "this way would turn a review queue into a scoreboard, which is exactly the failure mode "
            "the design rules out. What can be compared instead is the work itself: by state, by "
            "implementing agency, or by constituency, where the totals are about delivery rather than "
            "about a person."
        ),
        data={"rule": "Restraint rule 5 — no ranking of members by flag count"},
        links=[_link("dashboard"), _link("agencies"), _link("constituencies"), _link("methodology")],
        suggestions=[
            "Which states have the most flagged works?",
            "Which agencies handle the most works?",
            "What is detector B3?",
        ],
        declined=True,
    )


def _detector_explain(con, q: str, m: re.Match) -> Answer:
    meta = DETECTORS[m.group(1).upper()]
    return Answer(
        intent="detector_explain",
        text=(
            f"{meta.id} — {meta.title} (Tier {meta.tier}). {meta.description} "
            f"Shown alongside every {meta.id} flag: {meta.benign_explanation}"
        ),
        data={
            "detector": meta.id,
            "tier": meta.tier,
            "title": meta.title,
            "description": meta.description,
            "benign_explanation": meta.benign_explanation,
            "n_flags": _scalar(con, "SELECT count(*) FROM flags WHERE detector = ?", [meta.id]),
        },
        links=[_link("flags", href=f"/flags?detector={meta.id}", label=f"Works flagged by {meta.id}"),
               _link("methodology")],
        suggestions=[],
        declined=False,
    )


def _detector_list(con, q: str, m: re.Match) -> Answer:
    tier_a = [d for d in DETECTORS.values() if d.tier == "A"]
    tier_b = [d for d in DETECTORS.values() if d.tier == "B"]
    return Answer(
        intent="detector_list",
        text=(
            f"{len(DETECTORS)} detectors run over the corpus. Tier A ({len(tier_a)}) are the ones "
            f"resting on a record contradicting itself: {', '.join(f'{d.id} {d.title}' for d in tier_a)}. "
            f"Tier B ({len(tier_b)}) are statistical — a work standing out from its peer group, which "
            f"is a reason to look, not a finding: {', '.join(f'{d.id} {d.title}' for d in tier_b)}."
        ),
        data={
            "detectors": [
                {"id": d.id, "tier": d.tier, "title": d.title, "description": d.description}
                for d in DETECTORS.values()
            ]
        },
        links=[_link("methodology"), _link("flags")],
        suggestions=["What is detector A2?", "What does Tier A mean?"],
        declined=False,
    )


def _tier_meaning(con, q: str, m: re.Match) -> Answer:
    return Answer(
        intent="tier_meaning",
        text=(
            "Tier A flags come from a record contradicting itself — a payment larger than the sanction "
            "it belongs to, a work marked complete with nothing paid, an ID appearing twice. The "
            "arithmetic is checkable on the record alone. Tier B flags are statistical: the work sits "
            "outside its peer group on cost, duration or timing. Tier B is a reason to look, never a "
            "finding, and the tier is shown on every flag so the difference is never lost."
        ),
        data={"tiers": ["A", "B"]},
        links=[_link("methodology"), _link("validation")],
        suggestions=["What detectors are there?", "How was this validated?"],
        declined=False,
    )


def _flags_in_state(con, state: str) -> Answer:
    row = _rows(
        con,
        """
        SELECT count(*) AS n_works,
               count(s.work_id) AS n_flagged
        FROM works w LEFT JOIN work_flag_summary s ON w.work_id = s.work_id
        WHERE lower(w.state) = ?
        """,
        [state.lower()],
    )[0]
    n_works, n_flagged = row["n_works"], row["n_flagged"]
    share = f"{n_flagged / n_works * 100:.1f}%" if n_works else "0%"
    return Answer(
        intent="flags_in_state",
        text=(
            f"{state} has {_grouped(n_flagged)} works carrying at least one flag, out of "
            f"{_grouped(n_works)} works in the corpus — {share}. Each one still needs a reviewer to "
            f"open it and read the evidence."
        ),
        data={"state": state, "n_works": n_works, "n_flagged": n_flagged},
        links=[
            _link("flags", href=f"/flags?state={state}", label=f"Flagged works in {state}"),
            _link("unflagged", href=f"/unflagged?state={state}", label=f"Works with no flags in {state}"),
        ],
        suggestions=[],
        declined=False,
    )


def _top_states(con, q: str, m: re.Match) -> Answer:
    rows = _rows(
        con,
        """
        SELECT w.state, count(*) AS n_flagged
        FROM work_flag_summary s JOIN works w ON w.work_id = s.work_id
        WHERE w.state IS NOT NULL
        GROUP BY 1 ORDER BY n_flagged DESC LIMIT 5
        """,
    )
    listed = ", ".join(f"{r['state']} ({_grouped(r['n_flagged'])})" for r in rows)
    return Answer(
        intent="top_states",
        text=(
            f"By raw count of flagged works: {listed}. Bear in mind these are counts, not rates — a "
            f"state with more MPLADS works will carry more flags for that reason alone, so the "
            f"dashboard shows them against each state's total rather than on their own."
        ),
        data={"by_state": rows},
        links=[_link("dashboard"), _link("flags")],
        suggestions=["How many flagged works in Bihar?"],
        declined=False,
    )


def _top_agencies(con, q: str, m: re.Match) -> Answer:
    rows = _rows(
        con,
        "SELECT implementing_agency, n_works, total_value FROM agency_metrics ORDER BY n_works DESC LIMIT 5",
    )
    listed = ", ".join(f"{r['implementing_agency']} ({_grouped(r['n_works'])} works)" for r in rows)
    return Answer(
        intent="top_agencies",
        text=f"By number of works handled: {listed}.",
        data={"agencies": rows},
        links=[_link("agencies")],
        suggestions=["Which states have the most flagged works?"],
        declined=False,
    )


def _unflagged_count(con, q: str, m: re.Match) -> Answer:
    evaluated = _scalar(
        con,
        """
        SELECT count(*) FROM works w
        LEFT JOIN work_flag_summary s ON w.work_id = s.work_id
        WHERE s.work_id IS NULL AND w.sanction_amount IS NOT NULL
        """,
    )
    including = _scalar(
        con,
        """
        SELECT count(*) FROM works w
        LEFT JOIN work_flag_summary s ON w.work_id = s.work_id
        WHERE s.work_id IS NULL
        """,
    )
    return Answer(
        intent="unflagged_count",
        text=(
            f"{_grouped(evaluated)} sanctioned works were examined by every detector and picked up "
            f"nothing. A further {_grouped(including - evaluated)} have no sanction amount recorded "
            f"yet, so nearly every detector skips them by construction — they are not clean so much "
            f"as not yet inspected, which is why they are counted separately."
        ),
        data={"evaluated_clean": evaluated, "including_unsanctioned": including},
        links=[_link("unflagged")],
        suggestions=["How many works are there in total?"],
        declined=False,
    )


def _corpus_stats(con, q: str, m: re.Match) -> Answer:
    n_works = _scalar(con, "SELECT count(*) FROM works")
    n_flags = _scalar(con, "SELECT count(*) FROM flags")
    n_flagged = _scalar(con, "SELECT count(*) FROM work_flag_summary")
    return Answer(
        intent="corpus_stats",
        text=(
            f"The corpus holds {_grouped(n_works)} MPLADS works. {_grouped(n_flags)} flags were "
            f"raised across {_grouped(n_flagged)} of them — {n_flagged / n_works * 100:.1f}% of works "
            f"carry at least one, and a work can carry several. The other "
            f"{_grouped(n_works - n_flagged)} were left alone."
        ),
        data={"total_works": n_works, "total_flags": n_flags, "flagged_works": n_flagged},
        links=[_link("dashboard"), _link("flags"), _link("unflagged")],
        suggestions=["Where does the data come from?"],
        declined=False,
    )


def _provenance(con, q: str, m: re.Match) -> Answer:
    rows = _rows(con, "SELECT * FROM provenance")
    if not rows:
        return _fallback(con, q, None)
    p = rows[0]
    return Answer(
        intent="provenance",
        text=(
            f"Everything here comes from {p['source_name']} ({p['houses_covered']}), downloaded by "
            f"hand rather than scraped, snapshot dated {p['snapshot_date']}. That snapshot holds "
            f"{_grouped(p['n_works'])} works and {_grouped(p['n_expenditure_records'])} payment "
            f"records across {p['n_states']} states and {p['n_agencies']} implementing agencies. "
            f"No figure in this tool is estimated or filled in — where the source is blank, the tool "
            f"shows it blank."
        ),
        data=p,
        links=[_link("datasets", href="/datasets", label="Datasets"), _link("methodology")],
        suggestions=["How many works are there in total?"],
        declined=False,
    )


def _reviewed_count(con, q: str, m: re.Match) -> Answer:
    return Answer(
        intent="reviewed_count",
        text=(
            "A reviewer can mark any flag \"reviewed — explained\", which takes the work out of the "
            "queue without deleting anything: the flag and its evidence stay on the work page, and "
            "the mark can be undone at any time. The reviewed list shows every one of them."
        ),
        data={},
        links=[_link("reviewed"), _link("flags")],
        suggestions=["How many works have no flags?"],
        declined=False,
    )


def _validation_summary(con, q: str, m: re.Match) -> Answer:
    stability = _rows(
        con,
        "SELECT detector, mean_jaccard_vs_baseline FROM validation_stability ORDER BY detector",
    )
    known = _scalar(con, "SELECT count(*) FROM validation_known_cases")
    return Answer(
        intent="validation_summary",
        text=(
            "Five independent methods, all re-runnable: synthetic injection (plant known anomalies and "
            "measure how many come back), stability under resampling, agreement with documented audit "
            f"cases ({known} on file), cross-detector adjudication of the top-ranked works, and a "
            "time-split test of the stall-risk model. Results are published in full, including where "
            "they are weak — the validation page shows the numbers rather than a claim about them."
        ),
        data={"stability": stability, "n_known_cases": known},
        links=[_link("validation"), _link("methodology")],
        suggestions=["What does Tier A mean?"],
        declined=False,
    )


def _find_works(con, q: str, m: re.Match) -> Answer:
    term = (m.group("term") or m.group("term2") or "").strip()
    needle = f"%{term}%"
    n = _scalar(
        con,
        "SELECT count(*) FROM works WHERE description ILIKE ? OR implementing_agency ILIKE ?",
        [needle, needle],
    )
    preview = _rows(
        con,
        """
        SELECT work_id, description, state, sanction_amount
        FROM works WHERE description ILIKE ? OR implementing_agency ILIKE ?
        LIMIT 5
        """,
        [needle, needle],
    )
    if not n:
        return Answer(
            intent="find_works",
            text=f"Nothing in the corpus mentions \"{term}\".",
            data={"term": term, "n_matches": 0, "preview": []},
            links=[_link("flags")],
            suggestions=["How many works are there in total?"],
            declined=False,
        )
    return Answer(
        intent="find_works",
        text=(
            f"{_grouped(n)} works mention \"{term}\" in their description or implementing agency. "
            f"The first few: "
            + "; ".join(
                f"{(r['description'] or r['work_id'])[:60]} ({r['state'] or 'state not recorded'}, "
                f"{_amount(r['sanction_amount'])})"
                for r in preview
            )
            + "."
        ),
        data={"term": term, "n_matches": n, "preview": preview},
        links=[_link("search", href=f"/search?q={term}", label=f"All matches for \"{term}\"")],
        suggestions=[],
        declined=False,
    )


DEFAULT_SUGGESTIONS = [
    "How many works are there in total?",
    "What is detector B3?",
    "How many flagged works in Bihar?",
    "How many works have no flags?",
    "How was this validated?",
    "Where does the data come from?",
]


def _fallback(con, q: str, m: re.Match | None) -> Answer:
    return Answer(
        intent="fallback",
        text=(
            "That one is outside what I can answer from the data. I only report figures I can read "
            "straight out of the corpus, so rather than guess, here is what I can be asked."
        ),
        data={},
        links=[_link("flags"), _link("methodology")],
        suggestions=DEFAULT_SUGGESTIONS,
        declined=False,
    )


class Intent(NamedTuple):
    id: str
    pattern: re.Pattern[str]
    handler: Callable[..., Answer]


# Shape-matched, in priority order. The decline comes first by design.
_MEMBER = r"(?:mp|mps|member|members|leader|leaders|politician|politicians|minister|ministers)"
_SUPERLATIVE = (
    r"(?:most|worst|highest|biggest|largest|top|rank|ranked|ranking|league|leaderboard"
    r"|table|list|listing|compare|sorted|order(?:ed)? by)"
)

INTENTS: list[Intent] = [
    Intent(
        "decline_mp_ranking",
        re.compile(
            rf"(?:{_SUPERLATIVE}\b[\w\s]{{0,30}}\b{_MEMBER}\b)"
            rf"|(?:\b{_MEMBER}\b[\w\s]{{0,30}}\b{_SUPERLATIVE}\b)"
            # "flags per MP", "broken down by member" — a per-person
            # breakdown is the same scoreboard asked for a different way.
            rf"|(?:\b(?:per|by|for each)\s+{_MEMBER}\b)"
            # A yes/no verdict sought about a member. This will
            # occasionally catch an innocent phrasing ("is there an MP
            # filter?"), and that is the right direction to err: the
            # answer explains what the tool does instead of guessing.
            rf"|(?:\b(?:is|was|are|were|has|did)\b[\w\s]{{0,20}}\b{_MEMBER}\b)"
        ),
        _decline_mp_ranking,
    ),
    Intent("detector_explain", re.compile(r"\b([ab][1-8])\b"), _detector_explain),
    Intent("detector_list", re.compile(r"\b(?:what|which|how many|list|all)\b[\w\s]{0,20}\bdetector"), _detector_list),
    Intent("tier_meaning", re.compile(r"\btier\b"), _tier_meaning),
    Intent("validation_summary", re.compile(r"\b(?:validat|accurate|accuracy|reliable|how do you know|tested|proof)"), _validation_summary),
    Intent("provenance", re.compile(r"\b(?:where.{0,20}(?:data|it) come|source of the data|data come from|snapshot|how current|up to date|updated)\b"), _provenance),
    Intent("unflagged_count", re.compile(r"\b(?:no flags|not flagged|unflagged|clean|nothing wrong|passed)\b"), _unflagged_count),
    Intent("reviewed_count", re.compile(r"\breview(?:ed|s)\b"), _reviewed_count),
    Intent("top_agencies", re.compile(rf"{_SUPERLATIVE}\b[\w\s]{{0,25}}\bagenc|\bagenc\w*\b[\w\s]{{0,25}}{_SUPERLATIVE}"), _top_agencies),
    Intent("top_states", re.compile(rf"{_SUPERLATIVE}\b[\w\s]{{0,25}}\bstates?\b|\bstates?\b[\w\s]{{0,25}}{_SUPERLATIVE}"), _top_states),
    Intent("corpus_stats", re.compile(r"\bhow (?:many|big)\b[\w\s]{0,20}\b(?:works?|records?|rows|dataset|corpus)\b|\bhow large\b|\bcorpus size\b|\btotal works?\b"), _corpus_stats),
]

# Matched after the fixed intents: needs a captured group, so it is built
# per-request against the states actually present in the corpus.
_FIND_PATTERN = re.compile(
    r"\b(?:find|search(?:\s+for)?|show\s+me|any)\s+(?:all\s+)?"
    r"(?:works?\s+(?:about|for|mentioning|matching|on|with)\s+)?(?P<term>[\w\s-]{3,40})"
    r"|\bworks?\s+(?:about|mentioning|matching)\s+(?P<term2>[\w\s-]{3,40})"
)


def _named_state(con: duckdb.DuckDBPyConnection, q: str) -> str | None:
    states = [r[0] for r in con.execute(
        "SELECT DISTINCT state FROM works WHERE state IS NOT NULL"
    ).fetchall()]
    # Longest first, so a state whose name contains another's matches as
    # the longer one rather than the fragment.
    for state in sorted(states, key=len, reverse=True):
        if re.search(rf"\b{re.escape(state.lower())}\b", q):
            return state
    return None


def ask(con: duckdb.DuckDBPyConnection, question: str) -> Answer:
    """Answer `question` from `con`, or say what can be asked instead."""
    q = _normalise(question)
    if not q:
        return _fallback(con, q, None)

    # The decline outranks everything: a ranking question must never fall
    # through into an intent that would answer it.
    decline = INTENTS[0]
    m = decline.pattern.search(q)
    if m:
        return decline.handler(con, q, m)

    # A named state beats the general counting intents — otherwise "how
    # many flagged works in Bihar" matches `corpus_stats` on "how many
    # works" and silently answers about the whole country instead.
    state = _named_state(con, q)
    if state is not None and (
        re.search(r"\b(?:flag|flagged|works?|how many|anomal)\b", q) or q == state.lower()
    ):
        return _flags_in_state(con, state)

    for intent in INTENTS[1:]:
        m = intent.pattern.search(q)
        if m:
            return intent.handler(con, q, m)

    m = _FIND_PATTERN.search(q)
    if m:
        return _find_works(con, q, m)

    return _fallback(con, q, None)
