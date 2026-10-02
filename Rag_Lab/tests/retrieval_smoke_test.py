import time

from src.retrieval.retriever import (
    retriever,
)


def format_reference(
    result,
) -> str:

    #
    # Website:
    # external_id is the actual page URL.
    #
    if (
        result.source_type == "web"
        and result.external_id
    ):
        return result.external_id

    #
    # Git:
    # display repository + path.
    #
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
            f"{repository} "
            f"-> {path}"
        )

    #
    # Uploaded file.
    #
    return (
        result.document_title
    )


def main() -> None:

    print()
    print("=" * 72)
    print(
        "RAG Retrieval Smoke Test"
    )
    print("=" * 72)

    print()
    print(
        "The search runs across ALL "
        "indexed sources:"
    )
    print(
        "files + websites + git."
    )

    print()

    query = input(
        "Question: "
    ).strip()

    if not query:
        print(
            "Question cannot be empty."
        )
        return

    print()
    print(
        "Searching..."
    )

    started_at = (
        time.perf_counter()
    )

    results = (
        retriever.retrieve(
            query=query,
            top_k=5,
            debug=True,
        )
    )

    elapsed = (
        time.perf_counter()
        - started_at
    )

    print()
    print("=" * 72)

    print(
        f"Results: "
        f"{len(results)}"
    )

    print(
        f"Retrieval time: "
        f"{elapsed:.3f} sec"
    )

    print("=" * 72)

    if not results:
        print()
        print(
            "No relevant chunks found."
        )
        return

    for index, result in enumerate(
        results,
        start=1,
    ):

        print()
        print(
            f"RESULT #{index}"
        )

        print(
            "-" * 72
        )

        print(
            f"Score       : "
            f"{result.score:.4f}"
        )

        print(
            f"Source      : "
            f"{result.source_name}"
        )

        print(
            f"Source type : "
            f"{result.source_type}"
        )

        print(
            f"Document    : "
            f"{result.document_title}"
        )

        print(
            f"Chunk       : "
            f"{result.chunk_index}"
        )

        print(
            f"Reference   : "
            f"{format_reference(result)}"
        )

        print()
        print(
            "Text:"
        )

        print(
            result.text[:1200]
        )

        if (
            len(result.text)
            > 1200
        ):
            print(
                "..."
            )

    print()
    print("=" * 72)


if __name__ == "__main__":
    main()