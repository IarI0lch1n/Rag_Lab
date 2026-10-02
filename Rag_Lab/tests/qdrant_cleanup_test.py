from sqlalchemy import select

from src.db.models import (
    Chunk,
    Document,
    Source,
)

from src.db.session import (
    SessionLocal,
)

from src.vector_store.qdrant_store import (
    qdrant_store,
)


SCROLL_BATCH_SIZE = 256
DELETE_BATCH_SIZE = 500


def get_valid_chunks() -> dict[int, str]:

    with SessionLocal() as session:

        statement = (
            select(
                Chunk.id,
                Chunk.qdrant_point_id,
            )
            .join(
                Document,
                Chunk.document_id
                == Document.id,
            )
            .join(
                Source,
                Document.source_id
                == Source.id,
            )
            .where(
                Document.is_active == 1,
                Source.status == "indexed",
            )
        )

        rows = (
            session.execute(
                statement
            )
            .all()
        )

        return {
            int(chunk_id): (
                qdrant_point_id
                or ""
            )
            for (
                chunk_id,
                qdrant_point_id,
            ) in rows
        }


def delete_points(
    point_ids: list[str],
) -> None:

    for start in range(
        0,
        len(point_ids),
        DELETE_BATCH_SIZE,
    ):
        batch = (
            point_ids[
                start:
                start
                + DELETE_BATCH_SIZE
            ]
        )

        qdrant_store.delete_points(
            batch
        )

        print(
            f"Deleted "
            f"{len(batch)} "
            f"orphan points..."
        )


def main() -> None:

    print()
    print("=" * 72)
    print(
        "QDRANT ORPHAN VECTOR CLEANUP"
    )
    print("=" * 72)

    if not (
        qdrant_store
        .client
        .collection_exists(
            qdrant_store
            .collection_name
        )
    ):
        print(
            "Qdrant collection "
            "does not exist."
        )

        return

    print()
    print(
        "Loading valid SQL chunks..."
    )

    valid_chunks = (
        get_valid_chunks()
    )

    print(
        f"Valid SQL chunks: "
        f"{len(valid_chunks)}"
    )

    offset = None

    scanned = 0
    valid = 0
    orphan = 0

    orphan_point_ids = []

    print()
    print(
        "Scanning Qdrant..."
    )

    while True:

        points, next_offset = (
            qdrant_store
            .client
            .scroll(
                collection_name=(
                    qdrant_store
                    .collection_name
                ),
                limit=(
                    SCROLL_BATCH_SIZE
                ),
                offset=(
                    offset
                ),
                with_payload=True,
                with_vectors=False,
            )
        )

        if not points:
            break

        for point in points:

            scanned += 1

            payload = (
                point.payload
                or {}
            )

            chunk_id = (
                payload.get(
                    "chunk_id"
                )
            )

            is_valid = False

            if chunk_id is not None:

                try:
                    chunk_id = int(
                        chunk_id
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    chunk_id = None

            if chunk_id is not None:

                expected_point_id = (
                    valid_chunks.get(
                        chunk_id
                    )
                )

                if (
                    expected_point_id
                    and str(
                        expected_point_id
                    )
                    == str(
                        point.id
                    )
                ):
                    is_valid = True

            if is_valid:
                valid += 1

            else:
                orphan += 1

                orphan_point_ids.append(
                    str(
                        point.id
                    )
                )

        print(
            f"Scanned: {scanned} "
            f"| valid: {valid} "
            f"| orphan: {orphan}"
        )

        if next_offset is None:
            break

        offset = (
            next_offset
        )

    print()
    print("-" * 72)

    print(
        f"Total scanned : "
        f"{scanned}"
    )

    print(
        f"Valid points  : "
        f"{valid}"
    )

    print(
        f"Orphan points : "
        f"{orphan}"
    )

    if not orphan_point_ids:

        print()
        print(
            "Nothing to clean."
        )

        print("=" * 72)

        return

    print()
    print(
        "Deleting orphan "
        "Qdrant points..."
    )

    delete_points(
        orphan_point_ids
    )

    print()
    print(
        f"[OK] Deleted "
        f"{len(orphan_point_ids)} "
        f"orphan vectors."
    )

    print("=" * 72)


if __name__ == "__main__":
    main()