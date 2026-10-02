from collections import defaultdict
from dataclasses import dataclass

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


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    source_id: int

    score: float
    rerank_score: float | None

    text: str
    chunk_index: int

    document_title: str
    document_type: str | None

    source_name: str
    source_type: str

    external_id: str | None
    source_uri: str | None

    git_branch: str | None


class Retriever:

    def retrieve_candidates(
        self,
        query: str,
        limit: int = 30,
        qdrant_limit: int = 100,
        max_per_document: int = 4,
        debug: bool = False,
    ) -> list[RetrievedChunk]:

        query = query.strip()

        if not query:
            return []

        if limit <= 0:
            raise ValueError(
                "limit must be greater than 0."
            )

        qdrant_limit = max(
            qdrant_limit,
            limit,
        )

        query_vector = (
            embedder.embed_query(
                query
            )
        )

        points = (
            qdrant_store.search(
                query_vector,
                limit=qdrant_limit,
            )
        )

        if debug:
            print()
            print(
                f"[Retriever] Query: {query}"
            )
            print(
                f"[Retriever] Qdrant candidates: "
                f"{len(points)}"
            )

        if not points:
            return []

        results: list[
            RetrievedChunk
        ] = []

        document_counts = defaultdict(
            int
        )

        skipped_missing_chunk = 0
        skipped_missing_document = 0
        skipped_inactive_document = 0
        skipped_missing_source = 0
        skipped_source_status = 0
        skipped_document_limit = 0

        with SessionLocal() as session:

            for point in points:

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
                    skipped_missing_chunk += 1
                    continue

                try:
                    chunk_id = int(
                        chunk_id
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    skipped_missing_chunk += 1
                    continue

                chunk = session.get(
                    Chunk,
                    chunk_id,
                )

                if chunk is None:
                    skipped_missing_chunk += 1
                    continue

                document = session.get(
                    Document,
                    chunk.document_id,
                )

                if document is None:
                    skipped_missing_document += 1
                    continue

                if not document.is_active:
                    skipped_inactive_document += 1
                    continue

                source = session.get(
                    Source,
                    document.source_id,
                )

                if source is None:
                    skipped_missing_source += 1
                    continue

                if source.status != "indexed":
                    skipped_source_status += 1
                    continue

                if (
                    max_per_document > 0
                    and document_counts[
                        document.id
                    ]
                    >= max_per_document
                ):
                    skipped_document_limit += 1
                    continue

                document_counts[
                    document.id
                ] += 1

                results.append(
                    RetrievedChunk(
                        chunk_id=(
                            chunk.id
                        ),
                        document_id=(
                            document.id
                        ),
                        source_id=(
                            source.id
                        ),
                        score=float(
                            point.score
                        ),
                        rerank_score=None,
                        text=(
                            chunk.content
                        ),
                        chunk_index=(
                            chunk.chunk_index
                        ),
                        document_title=(
                            document.title
                        ),
                        document_type=(
                            document.document_type
                        ),
                        source_name=(
                            source.name
                        ),
                        source_type=(
                            source.source_type
                        ),
                        external_id=(
                            document.external_id
                        ),
                        source_uri=(
                            source.uri
                        ),
                        git_branch=(
                            source.git_branch
                        ),
                    )
                )

                if len(results) >= limit:
                    break

        if debug:
            print(
                f"[Retriever] Valid candidates: "
                f"{len(results)}"
            )

            print(
                f"[Retriever] Missing chunks: "
                f"{skipped_missing_chunk}"
            )

            print(
                f"[Retriever] Missing documents: "
                f"{skipped_missing_document}"
            )

            print(
                f"[Retriever] Inactive documents: "
                f"{skipped_inactive_document}"
            )

            print(
                f"[Retriever] Missing sources: "
                f"{skipped_missing_source}"
            )

            print(
                f"[Retriever] Non-indexed sources: "
                f"{skipped_source_status}"
            )

            print(
                f"[Retriever] Document duplicates "
                f"skipped: "
                f"{skipped_document_limit}"
            )

            print()

        return results

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        candidate_multiplier: int = 20,
        debug: bool = False,
    ) -> list[RetrievedChunk]:

        qdrant_limit = max(
            top_k
            * candidate_multiplier,
            top_k,
        )

        return self.retrieve_candidates(
            query=query,
            limit=top_k,
            qdrant_limit=qdrant_limit,
            max_per_document=3,
            debug=debug,
        )


retriever = Retriever()