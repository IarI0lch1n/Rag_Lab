import time

from src.db.models import (
    Chunk,
    Document,
    Source,
)

from src.db.session import (
    SessionLocal,
)

from src.embeddings.embedder import (
    embedder,
)

from src.vector_store.qdrant_store import (
    qdrant_store,
)


LIMIT = 100


def main() -> None:
    print()
    print("=" * 80)
    print(
        "DEEP RETRIEVAL TEST"
    )
    print("=" * 80)

    query = input(
        "Question: "
    ).strip()

    if not query:
        return

    started = (
        time.perf_counter()
    )

    vector = (
        embedder.embed_query(
            query
        )
    )

    points = (
        qdrant_store.search(
            vector,
            limit=LIMIT,
        )
    )

    print()
    print(
        f"Qdrant results: "
        f"{len(points)}"
    )

    valid_results = []

    with SessionLocal() as session:

        for rank, point in enumerate(
            points,
            start=1,
        ):
            payload = (
                point.payload
                or {}
            )

            chunk_id = (
                payload.get(
                    "chunk_id"
                )
            )

            if chunk_id is None:
                continue

            try:
                chunk_id = int(
                    chunk_id
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            chunk = session.get(
                Chunk,
                chunk_id,
            )

            if chunk is None:
                continue

            document = session.get(
                Document,
                chunk.document_id,
            )

            if (
                document is None
                or not document.is_active
            ):
                continue

            source = session.get(
                Source,
                document.source_id,
            )

            if (
                source is None
                or source.status
                != "indexed"
            ):
                continue

            valid_results.append(
                {
                    "rank": rank,
                    "score": float(
                        point.score
                    ),
                    "source": (
                        source.name
                    ),
                    "source_id": (
                        source.id
                    ),
                    "document": (
                        document.title
                    ),
                    "document_id": (
                        document.id
                    ),
                    "chunk_index": (
                        chunk.chunk_index
                    ),
                    "text": (
                        chunk.content
                    ),
                }
            )

    elapsed = (
        time.perf_counter()
        - started
    )

    print()
    print(
        f"Valid results: "
        f"{len(valid_results)}"
    )

    print(
        f"Time: "
        f"{elapsed:.3f} sec"
    )

    print()
    print("=" * 80)

    for result in (
        valid_results
    ):
        print(
            f"#{result['rank']:03d} "
            f"| {result['score']:.4f} "
            f"| source={result['source_id']} "
            f"{result['source']} "
            f"| {result['document']} "
            f"| chunk="
            f"{result['chunk_index']}"
        )

    print()
    print("=" * 80)

    #
    # Special diagnostic:
    # show anything containing VPN
    # in source/document/text.
    #
    matches = []

    for result in (
        valid_results
    ):
        haystack = (
            result["source"]
            + " "
            + result["document"]
            + " "
            + result["text"]
        ).casefold()

        if "vpn" in haystack:
            matches.append(
                result
            )

    print()
    print(
        "VPN-related results "
        "inside Top-100:"
    )

    if not matches:
        print(
            "NONE"
        )

    else:
        for result in matches:
            print(
                f"#{result['rank']:03d} "
                f"| {result['score']:.4f} "
                f"| {result['source']} "
                f"| {result['document']} "
                f"| chunk="
                f"{result['chunk_index']}"
            )


if __name__ == "__main__":
    main()