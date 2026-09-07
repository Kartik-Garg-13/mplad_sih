"""Unit tests for parakh.parse — one test per edge case actually found in
the raw eSAKSHI exports during recon, not hypothetical ones."""

import polars as pl

from parakh.config import UNPARSEABLE_WORK_ID, UNSANCTIONED_WORK_ID
from parakh.parse import (
    flag_description_corruption,
    parse_amount,
    parse_date,
    split_ida,
    split_work_field,
)


def test_split_work_field_normal_case():
    df = pl.DataFrame(
        {
            "Work": [
                "WS/MP187/2023-2024/1199-Construction of rooms and halls in school and colleges"
            ]
        }
    )
    out = df.select(*split_work_field("Work"))
    assert out["work_id"][0] == "WS/MP187/2023-2024/1199"
    assert out["category_from_work_field"][0] == "Construction of rooms and halls in school and colleges"


def test_split_work_field_na_id_means_not_yet_sanctioned():
    # Confirmed in the raw Lok Sabha "Works Recommended" export: "NA"
    # work IDs have 100% correlation with an empty Sanction Date —
    # eSAKSHI only allots a real ID once a work is sanctioned. This is
    # an expected placeholder (~25% of all Recommended rows), distinct
    # from a genuine parse failure — see UNPARSEABLE_WORK_ID below.
    df = pl.DataFrame({"Work": ["NA-Construction of roads, link roads, pathways"]})
    out = df.select(*split_work_field("Work"))
    assert out["work_id"][0] == UNSANCTIONED_WORK_ID


def test_split_work_field_tab_corruption_is_normalized_not_dropped():
    # Confirmed in the raw exports (recommended AND expenditure's
    # separate "Work ID" column) for a batch of MPs, e.g. MP620, MP443:
    # a literal tab-plus-space injected between "WS/" and "MP<code>".
    df = pl.DataFrame(
        {"Work": ["WS/\t MP620/2024-2025/133166-Construction of buildings for community cultural activities"]}
    )
    out = df.select(*split_work_field("Work"))
    assert out["work_id"][0] == "WS/MP620/2024-2025/133166"


def test_split_work_field_garbage_is_flagged_not_crashing():
    df = pl.DataFrame({"Work": ["", "not a work id at all"]})
    out = df.select(*split_work_field("Work"))
    assert (out["work_id"] == UNPARSEABLE_WORK_ID).all()


def test_split_ida_normal_case():
    df = pl.DataFrame(
        {"IDA": ["SAMBHAL(DISTRICT MAGISTRAE BHIMNAGAR SAMBHAL_IDA)"]}
    )
    out = df.select(*split_ida("IDA"))
    assert out["district_raw"][0] == "SAMBHAL"
    assert out["implementing_agency"][0] == "DISTRICT MAGISTRAE BHIMNAGAR SAMBHAL_IDA"


def test_split_ida_missing_parens_degrades_to_raw_value():
    df = pl.DataFrame({"IDA": ["SOME DISTRICT WITH NO AGENCY NOTED"]})
    out = df.select(*split_ida("IDA"))
    assert out["district_raw"][0] == "SOME DISTRICT WITH NO AGENCY NOTED"
    assert out["implementing_agency"][0] is None


def test_parse_amount_blank_becomes_null():
    # Confirmed in the raw Lok Sabha "Allocated Limit" export: MP
    # "CHAVAN VASANTRAO BALWANTRAO" has an empty amount field.
    df = pl.DataFrame({"amt": ["1484933", "", "196063957.11"]})
    out = df.select(parse_amount("amt"))
    assert out["amt"][0] == 1484933.0
    assert out["amt"][1] is None
    assert out["amt"][2] == 196063957.11


def test_parse_date_esakshi_format():
    df = pl.DataFrame({"d": ["14-Jun-2023", ""]})
    out = df.select(parse_date("d"))
    assert str(out["d"][0]) == "2023-06-14"
    assert out["d"][1] is None


def test_flag_description_corruption_detects_devanagari_loss():
    # Confirmed at byte level in the raw Rajya Sabha "Works Recommended"
    # export — a real Hindi description came through as literal "?"s.
    df = pl.DataFrame(
        {
            "Work description": [
                "P.C.C ??? ?? ???????",
                "Construction of Class room Sompal Singh Memorial Public School",
            ]
        }
    )
    out = df.select(flag_description_corruption("Work description"))
    assert out["description_corrupted"][0] is True
    assert out["description_corrupted"][1] is False
