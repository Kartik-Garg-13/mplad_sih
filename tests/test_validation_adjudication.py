from parakh.validation.adjudication import CLUSTERS, adjudication_result


def test_cluster_counts_sum_to_fifty():
    assert sum(c["n_works_in_top50"] for c in CLUSTERS) == 50


def test_every_cluster_has_a_valid_classification():
    valid = {"plausibly_irregular", "benign_explained", "undecided"}
    for c in CLUSTERS:
        assert c["classification"] in valid


def test_adjudication_result_totals_match_clusters():
    result = adjudication_result()

    assert result["n_reviewed"] == 50
    assert result["n_clusters"] == len(CLUSTERS)
    assert sum(result["by_classification"].values()) == 50
