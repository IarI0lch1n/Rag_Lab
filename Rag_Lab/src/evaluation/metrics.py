from dataclasses import dataclass


@dataclass(frozen=True)
class RankingMetrics:
    k: int

    hit_rate: float
    precision: float
    recall: float
    reciprocal_rank: float

    def to_dict(
        self,
    ) -> dict:
        return {
            "k": self.k,
            "hit_rate": self.hit_rate,
            "precision": self.precision,
            "recall": self.recall,
            "reciprocal_rank": (
                self.reciprocal_rank
            ),
        }


def unique_ranked_ids(
    values: list[int],
) -> list[int]:

    result = []
    seen = set()

    for value in values:

        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result


def hit_rate_at_k(
    retrieved: list[int],
    relevant: set[int],
    k: int,
) -> float:

    if not relevant:
        return 0.0

    retrieved_k = (
        retrieved[:k]
    )

    return (
        1.0
        if any(
            item in relevant
            for item in retrieved_k
        )
        else 0.0
    )


def precision_at_k(
    retrieved: list[int],
    relevant: set[int],
    k: int,
) -> float:

    if k <= 0:
        return 0.0

    retrieved_k = (
        retrieved[:k]
    )

    if not retrieved_k:
        return 0.0

    relevant_count = sum(
        1
        for item in retrieved_k
        if item in relevant
    )

    return (
        relevant_count
        / len(retrieved_k)
    )


def recall_at_k(
    retrieved: list[int],
    relevant: set[int],
    k: int,
) -> float:

    if not relevant:
        return 0.0

    retrieved_k = (
        retrieved[:k]
    )

    found = {
        item
        for item in retrieved_k
        if item in relevant
    }

    return (
        len(found)
        / len(relevant)
    )


def reciprocal_rank_at_k(
    retrieved: list[int],
    relevant: set[int],
    k: int,
) -> float:

    if not relevant:
        return 0.0

    for rank, item in enumerate(
        retrieved[:k],
        start=1,
    ):

        if item in relevant:
            return (
                1.0 / rank
            )

    return 0.0


def calculate_ranking_metrics(
    retrieved_document_ids: list[int],
    relevant_document_ids: list[int],
    k: int,
) -> RankingMetrics:

    retrieved = unique_ranked_ids(
        retrieved_document_ids
    )

    relevant = set(
        relevant_document_ids
    )

    return RankingMetrics(
        k=k,
        hit_rate=hit_rate_at_k(
            retrieved,
            relevant,
            k,
        ),
        precision=precision_at_k(
            retrieved,
            relevant,
            k,
        ),
        recall=recall_at_k(
            retrieved,
            relevant,
            k,
        ),
        reciprocal_rank=(
            reciprocal_rank_at_k(
                retrieved,
                relevant,
                k,
            )
        ),
    )