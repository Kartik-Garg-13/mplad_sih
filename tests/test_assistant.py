"""The assistant's restraint guarantees, tested as behaviour.

`test_vocabulary_lock` scans files on disk, which cannot see text the
assistant assembles at runtime. The last test here closes that gap by
running every intent and applying the same word pattern to what comes out.
"""

from __future__ import annotations

import duckdb
import pytest

from parakh.assistant import DEFAULT_SUGGESTIONS, ask
from tests.test_vocabulary_lock import _WORD_PATTERN


@pytest.fixture
def con():
    """A miniature corpus — enough tables for every intent to run."""
    c = duckdb.connect(":memory:")
    c.execute(
        """
        CREATE TABLE works (
            work_id VARCHAR, state VARCHAR, implementing_agency VARCHAR,
            mp_name VARCHAR, category VARCHAR, description VARCHAR,
            sanction_amount DOUBLE, financial_year VARCHAR
        )
        """
    )
    c.execute(
        """
        INSERT INTO works VALUES
            ('W1', 'Bihar', 'PWD Patna', 'Member One', 'Roads', 'Village road repair', 500000, '2024-2025'),
            ('W2', 'Bihar', 'PWD Patna', 'Member One', 'Education', 'Library books supply', 200000, '2024-2025'),
            ('W3', 'Kerala', 'PWD Kochi', 'Member Two', 'Roads', 'Culvert construction', 800000, '2024-2025'),
            ('W4', 'Kerala', 'PWD Kochi', 'Member Two', 'Health', 'Clinic wiring', NULL, '2024-2025')
        """
    )
    c.execute("CREATE TABLE work_flag_summary (work_id VARCHAR, has_tier_a BOOLEAN, has_tier_b BOOLEAN)")
    c.execute("INSERT INTO work_flag_summary VALUES ('W1', true, false), ('W3', false, true)")
    c.execute("CREATE TABLE flags (work_id VARCHAR, detector VARCHAR, tier VARCHAR)")
    c.execute("INSERT INTO flags VALUES ('W1', 'A1', 'A'), ('W3', 'B3', 'B')")
    c.execute("CREATE TABLE agency_metrics (implementing_agency VARCHAR, n_works BIGINT, total_value DOUBLE)")
    c.execute("INSERT INTO agency_metrics VALUES ('PWD Patna', 2, 700000), ('PWD Kochi', 2, 800000)")
    c.execute(
        """
        CREATE TABLE provenance (
            source_name VARCHAR, source_url VARCHAR, houses_covered VARCHAR,
            snapshot_date VARCHAR, n_works BIGINT, n_expenditure_records BIGINT,
            n_states BIGINT, n_mps BIGINT, n_agencies BIGINT
        )
        """
    )
    c.execute("INSERT INTO provenance VALUES ('eSAKSHI', 'https://example.invalid', 'Both houses', '2026-09-01', 4, 3, 2, 2, 2)")
    c.execute(
        "CREATE TABLE validation_stability (detector VARCHAR, mean_jaccard_vs_baseline DOUBLE)"
    )
    c.execute("INSERT INTO validation_stability VALUES ('A1', 0.98), ('B3', 0.81)")
    c.execute("CREATE TABLE validation_known_cases (case_id VARCHAR)")
    c.execute("INSERT INTO validation_known_cases VALUES ('K1'), ('K2')")
    yield c
    c.close()


RANKING_QUESTIONS = [
    "which MP has the most flags?",
    "who is the worst MP",
    "rank the members by anomalies",
    "show me flags per MP",
    "list mps by flag count",
    "top 10 ministers",
    "leaderboard of members",
    "compare MPs",
]


@pytest.mark.parametrize("question", RANKING_QUESTIONS)
def test_ranking_questions_are_declined(con, question):
    """Plan §08 rule 5. The refusal is the feature, not a gap."""
    answer = ask(con, question)
    assert answer.declined is True
    assert answer.intent == "decline_mp_ranking"


@pytest.mark.parametrize("question", RANKING_QUESTIONS)
def test_declined_questions_carry_no_member_figures(con, question):
    """A refusal that still printed per-member counts would be a refusal
    in wording only."""
    answer = ask(con, question)
    assert "Member One" not in answer.text
    assert "Member Two" not in answer.text
    assert not any(key.startswith("mp") for key in answer.data)


def test_unknown_question_offers_options_rather_than_an_answer(con):
    answer = ask(con, "what is the weather today")
    assert answer.intent == "fallback"
    assert answer.suggestions == DEFAULT_SUGGESTIONS


def test_empty_question_does_not_raise(con):
    assert ask(con, "   ").intent == "fallback"


def test_detector_answer_shows_tier_and_benign_explanation(con):
    """Plan §08 rules 3 and 4 — the tier and the innocent explanation
    travel with the detector wherever it is described."""
    answer = ask(con, "what is detector B3?")
    assert answer.intent == "detector_explain"
    assert answer.data["tier"] == "B"
    assert answer.data["benign_explanation"]
    assert answer.data["benign_explanation"] in answer.text
    assert "Tier B" in answer.text


def test_state_question_counts_from_the_corpus(con):
    answer = ask(con, "how many flagged works in Bihar?")
    assert answer.intent == "flags_in_state"
    assert answer.data == {"state": "Bihar", "n_works": 2, "n_flagged": 1}


def test_state_question_beats_the_general_counting_intent(con):
    """"how many ... works" also matches `corpus_stats`; naming a state
    has to win, or the answer silently describes the whole country."""
    assert ask(con, "how many flagged works in Kerala").intent == "flags_in_state"
    assert ask(con, "how many works are there in total?").intent == "corpus_stats"


def test_unflagged_separates_evaluated_from_never_evaluated(con):
    """W2 was evaluated and clean; W4 has no sanction amount, so nearly
    every detector skips it — counting the two together would report a
    work that was never inspected as one that passed."""
    answer = ask(con, "how many works have no flags?")
    assert answer.data["evaluated_clean"] == 1
    assert answer.data["including_unsanctioned"] == 2


def test_find_works_extracts_the_search_term(con):
    answer = ask(con, "find works about library")
    assert answer.intent == "find_works"
    assert answer.data["term"] == "library"
    assert answer.data["n_matches"] == 1


def test_every_answer_links_somewhere_checkable(con):
    """Plan §08 rule 2 — an answer the reader cannot go and verify is the
    thing this project exists not to produce."""
    questions = [
        "which MP has the most flags?",
        "what is detector B3?",
        "how many flagged works in Bihar?",
        "how many works are there in total?",
        "how many works have no flags?",
        "how was this validated?",
        "where does the data come from?",
        "what detectors are there?",
        "what does tier A mean?",
        "which states have the most flagged works?",
        "which agencies handle the most works?",
        "what is the weather today",
    ]
    for question in questions:
        answer = ask(con, question)
        assert answer.links, f"no link offered for {question!r}"
        for link in answer.links:
            assert link["href"].startswith("/"), f"{question!r} -> {link}"


def test_generated_answers_obey_the_vocabulary_lock(con):
    """The file scan cannot see text assembled at runtime; this can."""
    questions = RANKING_QUESTIONS + [
        "what is detector A1?",
        "what is detector B3?",
        "what detectors are there?",
        "what does tier A mean?",
        "how many flagged works in Bihar?",
        "how many works are there in total?",
        "how many works have no flags?",
        "how many works have been reviewed?",
        "how was this validated?",
        "where does the data come from?",
        "which states have the most flagged works?",
        "which agencies handle the most works?",
        "find works about library",
        "what is the weather today",
    ]
    violations = []
    for question in questions:
        answer = ask(con, question)
        for field in [answer.text, *answer.suggestions, *(l["label"] for l in answer.links)]:
            match = _WORD_PATTERN.search(field)
            if match:
                violations.append(f"{question!r} -> {match.group(0)!r} in {field[:80]!r}")
    assert not violations, "Banned vocabulary in generated answers:\n" + "\n".join(violations)
