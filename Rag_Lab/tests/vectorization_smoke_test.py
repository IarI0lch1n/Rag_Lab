from src.services.vectorization_service import (
    vectorization_service,
)
from src.services.source_service import (
    source_service,
)
from src.vector_store.qdrant_store import (
    qdrant_store,
)
from src.embeddings.embedder import (
    embedder,
)


def main() -> None:
    sources = (
        source_service
        .get_sources()
    )

    indexed_sources = [
        source
        for source in sources
        if source.status == "indexed"
    ]

    if not indexed_sources:
        print(
            "No indexed sources found."
        )
        return

    print()
    print("=" * 70)
    print("Vectorizing all indexed sources")
    print("=" * 70)
    print()

    total_chunks = 0

    for source in indexed_sources:
        print(
            f"Vectorizing source "
            f"{source.id}: "
            f"{source.name}"
        )

        try:
            chunks = (
                vectorization_service
                .vectorize_source(
                    source.id
                )
            )

            total_chunks += chunks

            print(
                f"[OK] {chunks} chunks created."
            )

        except Exception as exc:
            print(
                f"[ERROR] Source "
                f"{source.id} failed: "
                f"{exc}"
            )

        print()

    print("=" * 70)
    print(
        f"Vectorization completed."
    )
    print(
        f"Sources processed: "
        f"{len(indexed_sources)}"
    )
    print(
        f"Total chunks: "
        f"{total_chunks}"
    )
    print("=" * 70)

    print()
    print(
        "Testing semantic search "
        "across ALL sources..."
    )
    print()

    query = (
        "What information is available "
        "in the knowledge base?"
    )

    vector = (
        embedder.embed_query(
            query
        )
    )

    results = (
        qdrant_store.search(
            vector,
            limit=10,
        )
    )

    for index, result in enumerate(
        results,
        start=1,
    ):
        payload = (
            result.payload
            or {}
        )

        print()
        print(
            f"Result #{index}"
        )

        print(
            f"Score: "
            f"{result.score:.4f}"
        )

        print(
            f"Source: "
            f"{payload.get('source_name')}"
        )

        print(
            f"Document: "
            f"{payload.get('document_title')}"
        )

        print(
            f"Source type: "
            f"{payload.get('source_type')}"
        )

        print(
            f"External ID: "
            f"{payload.get('external_id')}"
        )

        text = (
            payload.get(
                "text",
                "",
            )
        )

        print()
        print(
            text[:500]
        )

        print(
            "-" * 70
        )


if __name__ == "__main__":
    main()