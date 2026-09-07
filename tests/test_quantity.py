import polars as pl

from parakh.quantity import extract_quantity


def _extract(category: str, description: str) -> tuple[float | None, str | None]:
    df = pl.DataFrame({"category": [category], "description": [description]})
    out = df.select(*extract_quantity())
    return out["quantity"][0], out["quantity_unit"][0]


def test_road_length_extracted_for_road_category():
    q, unit = _extract(
        "Construction of roads, link roads, pathways or any other road with or without drainage system",
        "developement lenght 400 meters by 7 meter",
    )
    assert q == 400.0
    assert unit == "meter"


def test_road_length_not_extracted_outside_road_category():
    # The same "N meter" text in a non-road category shouldn't be read
    # as a road length — e.g. "8 Meter LED Mini Mast Light" is a pole
    # height spec for "Lighting of public spaces", not a distance.
    q, unit = _extract("Lighting of public spaces", "Proving 8 Meter LED Mini Mast Light near Church")
    assert q is None
    assert unit is None


def test_count_extracted_from_nos_pattern():
    q, unit = _extract(
        "Installing tube-wells and borewells",
        "Installation of 10 nos. (sl.no. 1 to 10) Arsenic Free water tank",
    )
    assert q == 10.0
    assert unit == "unit"


def test_capacity_extracted_from_litres_pattern():
    q, unit = _extract(
        "Purchase of mobile water tankers",
        "Purchase of Mobile Water tanker Capacity 3000 Ltrs. at Village Chak Bur Wala",
    )
    assert q == 3000.0
    assert unit == "litre"


def test_no_match_leaves_both_null():
    q, unit = _extract(
        "Construction of rooms and halls in school and colleges",
        "Construction of MID DAY Meal Shed in Govt Primary school bajakhana main",
    )
    assert q is None
    assert unit is None


def test_road_precedence_over_count_pattern():
    # A road description that happens to also contain a "nos" mention
    # should still resolve to the road length, not the count — road
    # category takes precedence per the extractor's stated order.
    q, unit = _extract(
        "Construction of roads, link roads, pathways or any other road with or without drainage system",
        "CC road 150 meter work, 2 nos culverts included",
    )
    assert q == 150.0
    assert unit == "meter"
