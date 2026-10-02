import time

from src.retrieval.retriever import (
    retriever,
)

from src.reranking.reranker import (
    reranker,
)


CANDIDATE_COUNT = 30
QDRANT_LIMIT = 100
TOP_K = 8


def print_item(
    position: int,
    result,
    reranked: bool = False,
) -> None:

    if reranked:
        score_text = (
            f"rerank="
            f"{result.rerank_score:.4f} "
            f"| vector="
            f"{result.score:.4f}"
        )

    else:
        score_text = (
            f"vector="
            f"{result.score:.4f}"
        )

    print(
        f"#{position:02d} "
        f"| {score_text} "
        f"| {result.source_name} "
        f"| {result.document_title} "
        f"| chunk="
        f"{result.chunk_index}"
    )


def main() -> None:

    print()
    print("=" * 80)
    print(
        "RAG RERANKER QUALITY TEST"
    )
    print("=" * 80)

    query = input(
        "Question: "
    ).strip()

    if not query:
        return

    print()
    print(
        "Retrieving candidates..."
    )

    retrieval_started = (
        time.perf_counter()
    )

    candidates = (
        retriever.retrieve_candidates(
            query=query,
            limit=CANDIDATE_COUNT,
            qdrant_limit=(
                QDRANT_LIMIT
            ),
            max_per_document=4,
            debug=True,
        )
    )

    retrieval_time = (
        time.perf_counter()
        - retrieval_started
    )

    print()
    print("=" * 80)
    print(
        "BEFORE RERANK"
    )
    print("=" * 80)

    for position, result in enumerate(
        candidates,
        start=1,
    ):
        print_item(
            position,
            result,
        )

    print()
    print(
        f"Retrieval time: "
        f"{retrieval_time:.3f} sec"
    )

    print()
    print(
        "Reranking..."
    )

    print()
    print(
        "Warming up reranker..."
    )

    warmup_started = (
        time.perf_counter()
    )

    reranker.warmup()

    warmup_time = (
        time.perf_counter()
        - warmup_started
    )

    print(
        f"Reranker warmup: "
        f"{warmup_time:.3f} sec"
    )

    rerank_started = (
        time.perf_counter()
    )

    results = (
        reranker.rerank(
            query=query,
            candidates=candidates,
            top_k=TOP_K,
        )
    )

    rerank_time = (
        time.perf_counter()
        - rerank_started
    )

    print()
    print("=" * 80)
    print(
        "AFTER RERANK"
    )
    print("=" * 80)

    for position, result in enumerate(
        results,
        start=1,
    ):
        print_item(
            position,
            result,
            reranked=True,
        )

        print(
            f"     Source ID: "
            f"{result.source_id}"
        )

        print(
            f"     Document ID: "
            f"{result.document_id}"
        )

        print(
            f"     Preview: "
            f"{result.text[:250]}"
        )

        print()

    print("-" * 80)

    print(
        f"Candidate retrieval : "
        f"{retrieval_time:.3f} sec"
    )

    print(
        f"Reranking           : "
        f"{rerank_time:.3f} sec"
    )

    print(
        f"Total               : "
        f"{retrieval_time + rerank_time:.3f} sec"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()