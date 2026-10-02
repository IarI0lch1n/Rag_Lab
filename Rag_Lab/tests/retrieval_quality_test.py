import sys
import time

from collections import Counter

from src.retrieval.retriever import (
    retriever,
)


TOP_K = 8
CANDIDATE_MULTIPLIER = 20

TEXT_PREVIEW_LENGTH = 700


def format_duration(
    seconds: float,
) -> str:
    if seconds < 1:
        return (
            f"{seconds * 1000:.0f} ms"
        )

    return (
        f"{seconds:.3f} sec"
    )


def format_reference(
    result,
) -> str:
    if (
        result.source_type == "web"
        and result.external_id
    ):
        return result.external_id

    if result.source_type == "git":
        repository = (
            result.source_uri
            or ""
        )

        path = (
            result.external_id
            or result.document_title
        )

        return (
            f"{repository} -> {path}"
        )

    return (
        result.document_title
    )


def print_result(
    index: int,
    result,
) -> None:
    print()
    print(
        f"RESULT #{index}"
    )

    print(
        "-" * 80
    )

    print(
        f"Score         : "
        f"{result.score:.4f}"
    )

    print(
        f"Source ID     : "
        f"{result.source_id}"
    )

    print(
        f"Source        : "
        f"{result.source_name}"
    )

    print(
        f"Source type   : "
        f"{result.source_type}"
    )

    print(
        f"Document ID   : "
        f"{result.document_id}"
    )

    print(
        f"Document      : "
        f"{result.document_title}"
    )

    print(
        f"Document type : "
        f"{result.document_type}"
    )

    print(
        f"Chunk ID      : "
        f"{result.chunk_id}"
    )

    print(
        f"Chunk index   : "
        f"{result.chunk_index}"
    )

    print(
        f"Reference     : "
        f"{format_reference(result)}"
    )

    print()
    print(
        "TEXT:"
    )

    text = (
        result.text
        .strip()
    )

    print(
        text[
            :TEXT_PREVIEW_LENGTH
        ]
    )

    if (
        len(text)
        > TEXT_PREVIEW_LENGTH
    ):
        print(
            "..."
        )


def run_query(
    query: str,
) -> list:
    print()
    print("=" * 80)
    print(
        f"QUERY: {query}"
    )
    print("=" * 80)

    started_at = (
        time.perf_counter()
    )

    results = (
        retriever.retrieve(
            query=query,
            top_k=TOP_K,
            candidate_multiplier=(
                CANDIDATE_MULTIPLIER
            ),
            debug=True,
        )
    )

    elapsed = (
        time.perf_counter()
        - started_at
    )

    print()
    print(
        f"Retrieval time : "
        f"{format_duration(elapsed)}"
    )

    print(
        f"Results        : "
        f"{len(results)}"
    )

    if not results:
        print()
        print(
            "[WARNING] No valid "
            "retrieval results."
        )

        return []

    #
    # Show source distribution.
    #
    source_counter = Counter(
        result.source_name
        for result in results
    )

    document_counter = Counter(
        result.document_title
        for result in results
    )

    print()
    print(
        "SOURCE DISTRIBUTION:"
    )

    for (
        source_name,
        count,
    ) in source_counter.items():

        print(
            f"  {count}x "
            f"{source_name}"
        )

    print()
    print(
        f"Unique sources   : "
        f"{len(source_counter)}"
    )

    print(
        f"Unique documents : "
        f"{len(document_counter)}"
    )

    for index, result in enumerate(
        results,
        start=1,
    ):
        print_result(
            index,
            result,
        )

    print()
    print("=" * 80)

    return results


def compare_queries(
    first_query: str,
    second_query: str,
) -> None:
    print()
    print()
    print("#" * 80)
    print(
        "CROSS-LANGUAGE COMPARISON"
    )
    print("#" * 80)

    first_results = (
        run_query(
            first_query
        )
    )

    second_results = (
        run_query(
            second_query
        )
    )

    first_documents = {
        (
            result.source_id,
            result.document_id,
        )
        for result
        in first_results
    }

    second_documents = {
        (
            result.source_id,
            result.document_id,
        )
        for result
        in second_results
    }

    common_documents = (
        first_documents
        & second_documents
    )

    all_documents = (
        first_documents
        | second_documents
    )

    print()
    print("#" * 80)
    print(
        "COMPARISON RESULT"
    )
    print("#" * 80)

    print(
        f"Query 1 results     : "
        f"{len(first_results)}"
    )

    print(
        f"Query 2 results     : "
        f"{len(second_results)}"
    )

    print(
        f"Common documents    : "
        f"{len(common_documents)}"
    )

    if all_documents:
        overlap = (
            len(common_documents)
            / len(all_documents)
            * 100
        )

        print(
            f"Document overlap    : "
            f"{overlap:.1f}%"
        )

    print(
        "#"
        * 80
    )


def interactive_mode() -> None:
    print()
    print("=" * 80)
    print(
        "RAG RETRIEVAL QUALITY TEST"
    )
    print("=" * 80)

    print()
    print(
        "Commands:"
    )

    print(
        "  Enter a question "
        "to test retrieval."
    )

    print(
        "  compare "
        "to run RU/EN comparison."
    )

    print(
        "  exit "
        "to stop."
    )

    while True:
        print()

        query = input(
            "Question: "
        ).strip()

        if not query:
            continue

        if query.lower() in {
            "exit",
            "quit",
            "q",
        }:
            break

        if query.lower() == "compare":
            print()

            first_query = input(
                "Query 1: "
            ).strip()

            second_query = input(
                "Query 2: "
            ).strip()

            if (
                not first_query
                or not second_query
            ):
                print(
                    "Both queries "
                    "are required."
                )

                continue

            compare_queries(
                first_query,
                second_query,
            )

            continue

        run_query(
            query
        )


def main() -> None:
    #
    # Command line:
    #
    # python -m tests.retrieval_quality_test "Tell me about VPN"
    #
    if len(sys.argv) > 1:
        query = " ".join(
            sys.argv[1:]
        ).strip()

        run_query(
            query
        )

        return

    interactive_mode()


if __name__ == "__main__":
    main()