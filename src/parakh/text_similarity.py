"""TF-IDF cosine similarity between work descriptions, shared by B5
(work splitting) and B8 (near-duplicate funding).

One safeguard applies to both callers, baked in here rather than left
to each detector to remember: pairs at or above `exact_ceiling`
(near-verbatim text) are excluded from the result, not just the
high-similarity band below it. Confirmed during A3 (see tier_a.py):
MPLADS routinely has one MP recommending the same standard item at
many sites with one copy-pasted description — the largest real
example is 118 identical "high-mast light" entries from a single MP.
That pattern produces near-1.0 cosine similarity for entirely
legitimate reasons and would otherwise flood any text-similarity
detector the same way it flooded A3's original design. A genuine
near-duplicate entry of the same real-world asset, typed independently
by two different people, is far more likely to land just under a
perfect match than to be copy-pasted verbatim — so the useful signal
lives in the band between the detector's own threshold and the exact
ceiling, not above it.
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

EXACT_CEILING = 0.999

# The dense cosine-similarity matrix below is O(n^2) in both memory and
# compute — tractable at the largest real group in this corpus today
# (~2,400 works in one district, a ~46MB matrix), but a dataset upload
# (see uploads.py) can add works to any district or agency and there is no
# ceiling on how large a group could grow. At n=20,000 the matrix alone is
# ~3.2GB; this cap keeps the worst case bounded (~8,000^2 * 8 bytes =
# ~512MB) and degrades to "this group abstains" rather than exhausting
# memory or hanging the rebuild.
MAX_GROUP_SIZE = 8_000


def similar_pairs(
    texts: list[str],
    threshold: float,
    exact_ceiling: float = EXACT_CEILING,
    max_group_size: int = MAX_GROUP_SIZE,
) -> list[tuple[int, int, float]]:
    """Index pairs (i, j, similarity) with threshold <= similarity < exact_ceiling.

    Returns an empty list for fewer than 2 texts, or for a group larger
    than `max_group_size` (printed, not silent — B5/B8 abstaining on one
    oversized group should be visible, the same way Tier B's peer-group
    detectors report when they abstain below the minimum). Vectorized end
    to end otherwise (no Python-level double loop).
    """
    n = len(texts)
    if n < 2:
        return []
    if n > max_group_size:
        print(
            f"text_similarity.similar_pairs: skipping a group of {n:,} texts "
            f"(over the {max_group_size:,} cap) — B5/B8 abstain on this group "
            "rather than build an O(n^2) matrix for it."
        )
        return []

    vectorizer = TfidfVectorizer()
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        # All-empty/whitespace-only vocabulary for this group.
        return []
    sims = cosine_similarity(matrix)

    iu = np.triu_indices(n, k=1)
    pair_sims = sims[iu]
    mask = (pair_sims >= threshold) & (pair_sims < exact_ceiling)
    return list(zip(iu[0][mask].tolist(), iu[1][mask].tolist(), pair_sims[mask].tolist()))
