import hashlib
import json
import math
import time
import uuid

from dataclasses import dataclass

from qdrant_client.models import PointStruct

from src.db.models import Chunk
from src.db.session import SessionLocal

from src.embeddings.embedder import embedder

from src.preprocessing.chunker import (
    TextChunk,
)

from src.preprocessing.document_chunker import (
    document_chunker,
)

from src.preprocessing.chunking_profiles import (
    get_chunking_profile,
)

from src.preprocessing.cleaner import (
    text_cleaner,
)

from src.repositories.chunk_repository import (
    ChunkRepository,
)

from src.repositories.document_repository import (
    DocumentRepository,
)

from src.repositories.source_repository import (
    SourceRepository,
)

from src.vector_store.qdrant_store import (
    qdrant_store,
)


@dataclass
class PlannedChunk:
    document: object
    text_chunk: TextChunk
    document_chunk_count: int


class VectorizationService:
    EMBEDDING_BATCH_SIZE = 32

    def vectorize_source(
        self,
        source_id: int,
        force: bool = False,
    ) -> int:
        started_at = time.perf_counter()

        with SessionLocal() as session:
            source_repository = SourceRepository(
                session
            )

            document_repository = DocumentRepository(
                session
            )

            chunk_repository = ChunkRepository(
                session
            )

            source = source_repository.get_by_id(
                source_id
            )

            if source is None:
                raise ValueError(
                    f"Source {source_id} was not found."
                )

            all_documents = (
                document_repository.get_by_source_id(
                    source_id
                )
            )

            active_documents = [
                document
                for document in all_documents
                if document.is_active
            ]

            if not active_documents:
                raise ValueError(
                    "Source has no active parsed documents."
                )

            profile = get_chunking_profile(
                source.source_type
            )

            print()
            print("=" * 70)
            print(
                f"[Vectorization] {source.name}"
            )
            print("=" * 70)

            print(
                f"Source type       : "
                f"{source.source_type}"
            )

            print(
                f"Documents total   : "
                f"{len(all_documents)}"
            )

            print(
                f"Documents active  : "
                f"{len(active_documents)}"
            )

            print(
                f"Chunk size        : "
                f"{profile.chunk_size}"
            )

            print(
                f"Chunk overlap     : "
                f"{profile.chunk_overlap}"
            )

            qdrant_store.ensure_collection(
                embedder.dimension
            )

            existing_chunks = (
                chunk_repository.get_by_source_id(
                    source_id
                )
            )

            chunks_by_document = {}

            for chunk in existing_chunks:
                chunks_by_document.setdefault(
                    chunk.document_id,
                    [],
                ).append(
                    chunk
                )

            #
            # Remove chunks belonging to inactive
            # documents.
            #
            inactive_document_ids = [
                document.id
                for document in all_documents
                if not document.is_active
            ]

            if inactive_document_ids:
                chunk_repository.delete_by_document_ids(
                    inactive_document_ids
                )

                session.commit()

                for document_id in (
                    inactive_document_ids
                ):
                    qdrant_store.delete_by_document_id(
                        document_id
                    )

            #
            # Decide which active documents really
            # need rebuilding.
            #
            documents_to_rebuild = []
            skipped_documents = 0

            for document in active_documents:
                document_chunks = (
                    chunks_by_document.get(
                        document.id,
                        [],
                    )
                )

                if (
                    not force
                    and self._document_is_current(
                        document=document,
                        chunks=document_chunks,
                        profile=profile,
                    )
                ):
                    skipped_documents += 1
                    continue

                documents_to_rebuild.append(
                    document
                )

            print(
                f"Already current   : "
                f"{skipped_documents}"
            )

            print(
                f"Need rebuild      : "
                f"{len(documents_to_rebuild)}"
            )

            if not documents_to_rebuild:
                elapsed = (
                    time.perf_counter()
                    - started_at
                )

                print(
                    "Nothing to vectorize."
                )

                print(
                    f"Completed in      : "
                    f"{elapsed:.2f} sec"
                )

                print("=" * 70)

                return 0

            rebuild_document_ids = [
                document.id
                for document in documents_to_rebuild
            ]

            #
            # First remove old SQL chunks.
            #
            chunk_repository.delete_by_document_ids(
                rebuild_document_ids
            )

            session.commit()

            #
            # Now remove Qdrant data by payload.
            #
            # This also removes orphan vectors left by
            # previous failed indexing runs.
            #
            if (
                skipped_documents == 0
                and len(documents_to_rebuild)
                == len(active_documents)
            ):
                qdrant_store.delete_by_source_id(
                    source.id
                )

            else:
                for document_id in (
                    rebuild_document_ids
                ):
                    qdrant_store.delete_by_document_id(
                        document_id
                    )

            #
            # IMPORTANT:
            # One and only one pass through documents.
            #
            planned_chunks: list[
                PlannedChunk
            ] = []

            raw_chunk_count = 0
            filtered_chunk_count = 0

            seen_chunk_keys: set[
                tuple[int, int]
            ] = set()

            chunking_started = (
                time.perf_counter()
            )

            for document_number, document in enumerate(
                documents_to_rebuild,
                start=1,
            ):
                raw_text = (
                    document.raw_text
                    or ""
                )

                cleaned_document = (
                    text_cleaner.clean_document(
                        text=raw_text,
                        source_type=(
                            source.source_type
                        ),
                        document_type=(
                            document.document_type
                        ),
                    )
                )

                if not cleaned_document:
                    print(
                        f"[FILTER] "
                        f"{document.title}: "
                        f"document_empty"
                    )

                    continue

                raw_document_chunks = (
                    document_chunker.split(
                        text=(
                            cleaned_document
                        ),
                        source_type=(
                            source.source_type
                        ),
                        document_type=(
                            document.document_type
                        ),
                        chunk_size=(
                            profile.chunk_size
                        ),
                        chunk_overlap=(
                            profile.chunk_overlap
                        ),
                    )
                )

                raw_chunk_count += len(
                    raw_document_chunks
                )

                #
                # First build the valid chunks for
                # THIS document only.
                #
                valid_contents: list[str] = []

                for raw_chunk in (
                    raw_document_chunks
                ):
                    cleaned_chunk = (
                        text_cleaner.clean_chunk(
                            text=(
                                raw_chunk.content
                            ),
                            source_type=(
                                source.source_type
                            ),
                            document_type=(
                                document.document_type
                            ),
                        )
                    )

                    quality = (
                        text_cleaner.evaluate_chunk(
                            text=cleaned_chunk,
                            source_type=(
                                source.source_type
                            ),
                            document_type=(
                                document.document_type
                            ),
                        )
                    )

                    if not quality.useful:
                        filtered_chunk_count += 1

                        print(
                            f"[FILTER] "
                            f"{document.title} "
                            f"chunk "
                            f"{raw_chunk.index}: "
                            f"{quality.reason}"
                        )

                        continue

                    valid_contents.append(
                        cleaned_chunk
                    )

                document_chunk_count = len(
                    valid_contents
                )

                #
                # Re-index chunks after filtering:
                # 0, 1, 2, 3...
                #
                for chunk_index, content in enumerate(
                    valid_contents
                ):
                    chunk_key = (
                        document.id,
                        chunk_index,
                    )

                    #
                    # Defensive protection.
                    #
                    if chunk_key in seen_chunk_keys:
                        raise RuntimeError(
                            "Duplicate planned chunk "
                            f"detected before SQL insert: "
                            f"document_id={document.id}, "
                            f"chunk_index={chunk_index}"
                        )

                    seen_chunk_keys.add(
                        chunk_key
                    )

                    planned_chunks.append(
                        PlannedChunk(
                            document=document,
                            text_chunk=TextChunk(
                                index=chunk_index,
                                content=content,
                            ),
                            document_chunk_count=(
                                document_chunk_count
                            ),
                        )
                    )

                if (
                    document_number % 25 == 0
                    or document_number
                    == len(
                        documents_to_rebuild
                    )
                ):
                    print(
                        f"Prepared documents: "
                        f"{document_number}/"
                        f"{len(documents_to_rebuild)} "
                        f"| raw chunks: "
                        f"{raw_chunk_count} "
                        f"| kept: "
                        f"{len(planned_chunks)} "
                        f"| filtered: "
                        f"{filtered_chunk_count}"
                    )

            chunking_elapsed = (
                time.perf_counter()
                - chunking_started
            )

            total_chunks = len(
                planned_chunks
            )

            print()
            print(
                f"Raw chunks        : "
                f"{raw_chunk_count}"
            )

            print(
                f"Filtered chunks   : "
                f"{filtered_chunk_count}"
            )

            print(
                f"Chunks to embed   : "
                f"{total_chunks}"
            )

            if raw_chunk_count > 0:
                filtered_percent = (
                    filtered_chunk_count
                    / raw_chunk_count
                    * 100
                )

                print(
                    f"Filtered          : "
                    f"{filtered_percent:.1f}%"
                )

            print(
                f"Chunking time     : "
                f"{chunking_elapsed:.2f} sec"
            )

            #
            # If we had to rebuild everything and
            # nothing useful survived, this source
            # must NOT become ready for RAG.
            #
            if (
                total_chunks == 0
                and skipped_documents == 0
            ):
                raise ValueError(
                    "No useful chunks remained "
                    "after cleaning and filtering."
                )

            if total_chunks == 0:
                return 0

            batch_size = (
                self.EMBEDDING_BATCH_SIZE
            )

            batch_count = math.ceil(
                total_chunks
                / batch_size
            )

            processed_chunks = 0

            embedding_started = (
                time.perf_counter()
            )

            for batch_number, start in enumerate(
                range(
                    0,
                    total_chunks,
                    batch_size,
                ),
                start=1,
            ):
                end = min(
                    start + batch_size,
                    total_chunks,
                )

                batch = planned_chunks[
                    start:end
                ]

                texts = [
                    item.text_chunk.content
                    for item in batch
                ]

                vectors = (
                    embedder.embed_passages(
                        texts,
                        batch_size=batch_size,
                    )
                )

                token_counts = (
                    embedder.count_tokens_batch(
                        texts
                    )
                )

                sql_chunks = []
                qdrant_data = []

                for (
                    item,
                    vector,
                    token_count,
                ) in zip(
                    batch,
                    vectors,
                    token_counts,
                ):
                    document = (
                        item.document
                    )

                    content = (
                        item.text_chunk.content
                    )

                    chunk_index = (
                        item.text_chunk.index
                    )

                    content_hash = (
                        hashlib.sha256(
                            content.encode(
                                "utf-8"
                            )
                        ).hexdigest()
                    )

                    point_id = str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            (
                                f"{source.id}:"
                                f"{document.id}:"
                                f"{chunk_index}:"
                                f"{content_hash}"
                            ),
                        )
                    )

                    metadata = {
                        "source_id": (
                            source.id
                        ),
                        "source_name": (
                            source.name
                        ),
                        "source_type": (
                            source.source_type
                        ),

                        "document_id": (
                            document.id
                        ),
                        "document_title": (
                            document.title
                        ),
                        "document_type": (
                            document.document_type
                        ),
                        "document_content_hash": (
                            document.content_hash
                        ),

                        "external_id": (
                            document.external_id
                        ),

                        "chunk_index": (
                            chunk_index
                        ),

                        "document_chunk_count": (
                            item.document_chunk_count
                        ),

                        "chunk_size": (
                            profile.chunk_size
                        ),
                        "chunk_overlap": (
                            profile.chunk_overlap
                        ),

                        "cleaner_version": (
                            text_cleaner.VERSION
                        ),

                        "chunker_version": (
                            document_chunker.VERSION
                        ),
                    }

                    chunk = Chunk(
                        document_id=(
                            document.id
                        ),
                        chunk_index=(
                            chunk_index
                        ),
                        content=(
                            content
                        ),
                        content_hash=(
                            content_hash
                        ),
                        token_count=(
                            token_count
                        ),
                        char_count=(
                            len(content)
                        ),
                        metadata_json=(
                            json.dumps(
                                metadata,
                                ensure_ascii=False,
                            )
                        ),
                        qdrant_point_id=(
                            point_id
                        ),
                    )

                    sql_chunks.append(
                        chunk
                    )

                    qdrant_data.append(
                        (
                            metadata,
                            point_id,
                            vector,
                        )
                    )

                chunk_repository.create_many(
                    sql_chunks
                )

                qdrant_points = []

                for (
                    chunk,
                    qdrant_item,
                ) in zip(
                    sql_chunks,
                    qdrant_data,
                ):
                    (
                        metadata,
                        point_id,
                        vector,
                    ) = qdrant_item

                    qdrant_points.append(
                        PointStruct(
                            id=point_id,
                            vector=vector,
                            payload={
                                **metadata,
                                "chunk_id": (
                                    chunk.id
                                ),
                                "text": (
                                    chunk.content
                                ),
                            },
                        )
                    )

                qdrant_store.upsert(
                    qdrant_points
                )

                #
                # Commit every successful batch.
                #
                session.commit()

                processed_chunks += len(
                    batch
                )

                elapsed = (
                    time.perf_counter()
                    - embedding_started
                )

                speed = (
                    processed_chunks
                    / elapsed
                    if elapsed > 0
                    else 0
                )

                remaining_chunks = (
                    total_chunks
                    - processed_chunks
                )

                eta = (
                    remaining_chunks
                    / speed
                    if speed > 0
                    else 0
                )

                print(
                    f"Embedding batch "
                    f"{batch_number}/"
                    f"{batch_count} | "
                    f"{processed_chunks}/"
                    f"{total_chunks} chunks | "
                    f"{speed:.2f} chunks/sec | "
                    f"ETA {eta:.0f} sec"
                )

            embedding_elapsed = (
                time.perf_counter()
                - embedding_started
            )

            total_elapsed = (
                time.perf_counter()
                - started_at
            )

            print()
            print("-" * 70)

            print(
                f"Created chunks    : "
                f"{total_chunks}"
            )

            print(
                f"Chunking time     : "
                f"{chunking_elapsed:.2f} sec"
            )

            print(
                f"Embedding time    : "
                f"{embedding_elapsed:.2f} sec"
            )

            print(
                f"Total time        : "
                f"{total_elapsed:.2f} sec"
            )

            if embedding_elapsed > 0:
                print(
                    f"Embedding speed   : "
                    f"{total_chunks / embedding_elapsed:.2f} "
                    f"chunks/sec"
                )

            print("=" * 70)
            print()

            return total_chunks

    @staticmethod
    def _document_is_current(
        document,
        chunks: list[Chunk],
        profile,
    ) -> bool:
        if not chunks:
            return False

        expected_count = None

        indexes = sorted(
            chunk.chunk_index
            for chunk in chunks
        )

        for chunk in chunks:
            if not chunk.qdrant_point_id:
                return False

            if not chunk.metadata_json:
                return False

            try:
                metadata = json.loads(
                    chunk.metadata_json
                )

            except Exception:
                return False

            if (
                metadata.get(
                    "document_content_hash"
                )
                != document.content_hash
            ):
                return False

            if (
                metadata.get(
                    "chunk_size"
                )
                != profile.chunk_size
            ):
                return False

            if (
                metadata.get(
                    "chunk_overlap"
                )
                != profile.chunk_overlap
            ):
                return False

            if (
                metadata.get(
                    "cleaner_version"
                )
                != text_cleaner.VERSION
            ):
                return False

            if (
                metadata.get(
                    "chunker_version"
                )
                != document_chunker.VERSION
            ):
                return False

            chunk_count = metadata.get(
                "document_chunk_count"
            )

            if not isinstance(
                chunk_count,
                int,
            ):
                return False

            if expected_count is None:
                expected_count = (
                    chunk_count
                )

            elif (
                expected_count
                != chunk_count
            ):
                return False

        if expected_count is None:
            return False

        if (
            len(chunks)
            != expected_count
        ):
            return False

        if indexes != list(
            range(
                expected_count
            )
        ):
            return False

        return True


vectorization_service = (
    VectorizationService()
)