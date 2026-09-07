from parakh.text_similarity import similar_pairs


def test_near_duplicate_texts_are_matched():
    texts = [
        "Construction of high mast light at village Ramnagar near temple",
        "Construction of high mast light at village Ramnagar close to temple",
        "Purchase of ambulance for district hospital",
    ]
    pairs = similar_pairs(texts, threshold=0.7)
    assert any(p[0] == 0 and p[1] == 1 for p in pairs)


def test_exact_duplicates_are_excluded_not_matched():
    # The A3 safeguard: near-verbatim boilerplate (the same legitimate
    # bulk-submission pattern found there) must not surface here either.
    texts = [
        "Installation of High Mast Light at Panrui Bazar",
        "Installation of High Mast Light at Panrui Bazar",
        "Purchase of ambulance for district hospital",
    ]
    pairs = similar_pairs(texts, threshold=0.7)
    assert pairs == []


def test_dissimilar_texts_are_not_matched():
    texts = [
        "Construction of CC road from house to house",
        "Purchase of mobile water tanker capacity 3000 litres",
    ]
    pairs = similar_pairs(texts, threshold=0.85)
    assert pairs == []


def test_fewer_than_two_texts_returns_empty():
    assert similar_pairs([], threshold=0.85) == []
    assert similar_pairs(["one description"], threshold=0.85) == []


def test_handles_empty_strings_without_crashing():
    pairs = similar_pairs(["", "", ""], threshold=0.85)
    assert pairs == []


def test_group_over_the_size_cap_abstains_instead_of_building_a_huge_matrix():
    """A dataset upload can add works to any district/agency group with no
    ceiling — the O(n^2) matrix must degrade to "this group abstains" past
    a bounded size, not attempt an unbounded allocation."""
    texts = [
        "Construction of high mast light at village Ramnagar near temple",
        "Construction of high mast light at village Ramnagar close to temple",
        "Purchase of ambulance for district hospital",
    ]
    assert similar_pairs(texts, threshold=0.7, max_group_size=2) == []
    # Below the cap, the same inputs behave exactly as they would with no
    # cap at all — matches test_near_duplicate_texts_are_matched.
    assert any(p[0] == 0 and p[1] == 1 for p in similar_pairs(texts, threshold=0.7, max_group_size=10))
