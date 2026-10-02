from pathlib import Path

from src.services.ingestion_service import (
    ingestion_service,
)
from src.services.source_service import (
    source_service,
)


def main() -> None:

    test_path = Path(
        "data/temp/"
        "ingestion_test.txt"
    )

    test_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    test_path.write_text(
        """
RAG stands for Retrieval-Augmented Generation.

A RAG system retrieves relevant documents before
generating an answer.

Vector databases can be used to find semantically
similar document chunks.
        """.strip(),
        encoding="utf-8",
    )

    source = (
        source_service.add_file_source(
            test_path
        )
    )

    print()
    print(
        f"Created source: "
        f"{source.id} "
        f"{source.name}"
    )

    result = (
        ingestion_service.ingest_source(
            source.id
        )
    )

    print()
    print(
        f"Status: "
        f"{result.status}"
    )

    print(
        f"Documents discovered: "
        f"{result.documents_discovered}"
    )

    print(
        f"Created: "
        f"{result.documents_created}"
    )

    print(
        f"Updated: "
        f"{result.documents_updated}"
    )

    print(
        f"Skipped: "
        f"{result.documents_skipped}"
    )

    if result.error:
        print(
            f"ERROR: "
            f"{result.error}"
        )

    print()
    print(
        "The source is intentionally "
        "left in the database."
    )

    print(
        "Check dbo.sources, "
        "dbo.documents and "
        "dbo.ingestion_runs."
    )

    if test_path.exists():
        test_path.unlink()


if __name__ == "__main__":
    main()