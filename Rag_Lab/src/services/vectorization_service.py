import hashlib
import json
import logging
import math
import time
import uuid

from dataclasses import dataclass

from qdrant_client.models import PointStruct

from src.db.models import Chunk
from src.db.session import SessionLocal
from src.embeddings.embedder import embedder
from src.preprocessing.chunker import TextChunk
from src.preprocessing.document_chunker import document_chunker
from src.preprocessing.chunking_profiles import get_chunking_profile
from src.preprocessing.cleaner import text_cleaner
from src.repositories.chunk_repository import ChunkRepository
from src.repositories.document_repository import DocumentRepository
from src.repositories.source_repository import SourceRepository
from src.vector_store.qdrant_store import qdrant_store


logger = logging.getLogger(
    "advisor.vectorization"
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

        logger.info(
            "Vectorization started | source_id=%s | force=%s",
            source_id,
            force,
        )

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

            self._print_header(
                source=source,
                all_documents=all_documents,
                active_documents=active_documents,
                profile=profile,
            )

            logger.info(
                (
                    "Vectorization source loaded | "
                    "source_id=%s | "
                    "name=%s | "
                    "type=%s | "
                    "documents=%s | "
                    "active=%s | "
                    "chunk_size=%s | "
                    "chunk_overlap=%s"
                ),
                source.id,
                source.name,
                source.source_type,
                len(all_documents),
                len(active_documents),
                profile.chunk_size,
                profile.chunk_overlap,
            )

            #
            # Make sure Qdrant is ready before
            # making any changes to SQL chunks.
            #
            qdrant_store.ensure_collection(
                embedder.dimension
            )

            existing_chunks = (
                chunk_repository.get_by_source_id(
                    source_id
                )
            )

            chunks_by_document: dict[
                int,
                list[Chunk],
            ] = {}

            for chunk in existing_chunks:
                chunks_by_document.setdefault(
                    chunk.document_id,
                    [],
                ).append(
                    chunk
                )

            #
            # Remove chunks/vectors belonging to
            # inactive documents.
            #
            inactive_document_ids = [
                document.id
                for document in all_documents
                if not document.is_active
            ]

            if inactive_document_ids:
                logger.info(
                    (
                        "Removing inactive document data | "
                        "source_id=%s | documents=%s"
                    ),
                    source.id,
                    len(inactive_document_ids),
                )

                chunk_repository.delete_by_document_ids(
                    inactive_document_ids
                )

                session.commit()

                for document_id in inactive_document_ids:
                    qdrant_store.delete_by_document_id(
                        document_id
                    )

            #
            # Work out which active documents
            # actually need to be rebuilt.
            #
            documents_to_rebuild = []

            skipped_documents = 0

            for document in active_documents:
                document_chunks = chunks_by_document.get(
                    document.id,
                    [],
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
                f"Already current   : {skipped_documents}"
            )

            print(
                (
                    "Need rebuild      : "
                    f"{len(documents_to_rebuild)}"
                )
            )

            logger.info(
                (
                    "Vectorization plan created | "
                    "source_id=%s | "
                    "current_documents=%s | "
                    "documents_to_rebuild=%s"
                ),
                source.id,
                skipped_documents,
                len(documents_to_rebuild),
            )

            #
            # Everything is already current.
            #
            if not documents_to_rebuild:
                elapsed = (
                    time.perf_counter()
                    - started_at
                )

                print(
                    "Nothing to vectorize."
                )

                print(
                    (
                        "Completed in      : "
                        f"{elapsed:.2f} sec"
                    )
                )

                print(
                    "=" * 70
                )

                logger.info(
                    (
                        "Vectorization skipped | "
                        "source_id=%s | "
                        "reason=all_documents_current | "
                        "elapsed=%.2fs"
                    ),
                    source.id,
                    elapsed,
                )

                return 0

            rebuild_document_ids = [
                document.id
                for document in documents_to_rebuild
            ]

            #
            # Remove old SQL chunks first.
            #
            chunk_repository.delete_by_document_ids(
                rebuild_document_ids
            )

            session.commit()

            #
            # Remove old Qdrant vectors.
            #
            # If every active document is being rebuilt,
            # deleting by source also removes any orphan
            # vectors from previous failed attempts.
            #
            full_rebuild = (
                skipped_documents == 0
                and len(documents_to_rebuild)
                == len(active_documents)
            )

            if full_rebuild:
                logger.info(
                    (
                        "Clearing Qdrant vectors for "
                        "full source rebuild | "
                        "source_id=%s"
                    ),
                    source.id,
                )

                qdrant_store.delete_by_source_id(
                    source.id
                )

            else:
                logger.info(
                    (
                        "Clearing Qdrant vectors for "
                        "partial source rebuild | "
                        "source_id=%s | documents=%s"
                    ),
                    source.id,
                    len(rebuild_document_ids),
                )

                for document_id in rebuild_document_ids:
                    qdrant_store.delete_by_document_id(
                        document_id
                    )

            #
            # Prepare all valid chunks.
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

            logger.info(
                (
                    "Chunk preparation started | "
                    "source_id=%s | documents=%s"
                ),
                source.id,
                len(documents_to_rebuild),
            )

            for (
                document_number,
                document,
            ) in enumerate(
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
                        source_type=source.source_type,
                        document_type=(
                            document.document_type
                        ),
                    )
                )

                if not cleaned_document:
                    print(
                        (
                            "[FILTER] "
                            f"{document.title}: "
                            "document_empty"
                        )
                    )

                    logger.warning(
                        (
                            "Document filtered as empty | "
                            "source_id=%s | "
                            "document_id=%s | "
                            "title=%s"
                        ),
                        source.id,
                        document.id,
                        document.title,
                    )

                    continue

                raw_document_chunks = (
                    document_chunker.split(
                        text=cleaned_document,
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

                valid_contents: list[str] = []

                for raw_chunk in raw_document_chunks:
                    cleaned_chunk = (
                        text_cleaner.clean_chunk(
                            text=raw_chunk.content,
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
                            (
                                "[FILTER] "
                                f"{document.title} "
                                f"chunk "
                                f"{raw_chunk.index}: "
                                f"{quality.reason}"
                            )
                        )

                        continue

                    valid_contents.append(
                        cleaned_chunk
                    )

                document_chunk_count = len(
                    valid_contents
                )

                #
                # Re-number chunks AFTER filtering:
                # 0, 1, 2, 3...
                #
                for (
                    chunk_index,
                    content,
                ) in enumerate(
                    valid_contents
                ):
                    chunk_key = (
                        document.id,
                        chunk_index,
                    )

                    if chunk_key in seen_chunk_keys:
                        raise RuntimeError(
                            (
                                "Duplicate planned chunk "
                                "detected before SQL insert: "
                                f"document_id={document.id}, "
                                f"chunk_index={chunk_index}"
                            )
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
                    == len(documents_to_rebuild)
                ):
                    print(
                        (
                            "Prepared documents: "
                            f"{document_number}/"
                            f"{len(documents_to_rebuild)} "
                            f"| raw chunks: "
                            f"{raw_chunk_count} "
                            f"| kept: "
                            f"{len(planned_chunks)} "
                            f"| filtered: "
                            f"{filtered_chunk_count}"
                        )
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
                f"Raw chunks        : {raw_chunk_count}"
            )

            print(
                (
                    "Filtered chunks   : "
                    f"{filtered_chunk_count}"
                )
            )

            print(
                f"Chunks to embed   : {total_chunks}"
            )

            if raw_chunk_count > 0:
                filtered_percent = (
                    filtered_chunk_count
                    / raw_chunk_count
                    * 100
                )

                print(
                    (
                        "Filtered          : "
                        f"{filtered_percent:.1f}%"
                    )
                )

            print(
                (
                    "Chunking time     : "
                    f"{chunking_elapsed:.2f} sec"
                )
            )

            logger.info(
                (
                    "Chunk preparation completed | "
                    "source_id=%s | "
                    "raw_chunks=%s | "
                    "kept_chunks=%s | "
                    "filtered_chunks=%s | "
                    "elapsed=%.2fs"
                ),
                source.id,
                raw_chunk_count,
                total_chunks,
                filtered_chunk_count,
                chunking_elapsed,
            )

            #
            # If this was a full rebuild and not
            # a single usable chunk survived,
            # the source must not become RAG-ready.
            #
            if (
                total_chunks == 0
                and skipped_documents == 0
            ):
                raise ValueError(
                    (
                        "No useful chunks remained "
                        "after cleaning and filtering."
                    )
                )

            if total_chunks == 0:
                return 0

            #
            # Embedding and Qdrant upload.
            #
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

            logger.info(
                (
                    "Embedding started | "
                    "source_id=%s | "
                    "chunks=%s | "
                    "batch_size=%s | "
                    "batches=%s"
                ),
                source.id,
                total_chunks,
                batch_size,
                batch_count,
            )

            try:
                for (
                    batch_number,
                    start,
                ) in enumerate(
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

                    logger.info(
                        (
                            "Embedding batch started | "
                            "source_id=%s | "
                            "batch=%s/%s | "
                            "chunks=%s"
                        ),
                        source.id,
                        batch_number,
                        batch_count,
                        len(batch),
                    )

                    print(
                        (
                            "[Embeddings] "
                            f"Batch "
                            f"{batch_number}/"
                            f"{batch_count} "
                            f"| chunks="
                            f"{len(batch)}"
                        )
                    )

                    texts = [
                        item.text_chunk.content
                        for item in batch
                    ]

                    vectors = (
                        embedder.embed_passages(
                            texts,
                            batch_size=(
                                batch_size
                            ),
                        )
                    )

                    token_counts = (
                        embedder.count_tokens_batch(
                            texts
                        )
                    )

                    if (
                        len(vectors)
                        != len(batch)
                    ):
                        raise RuntimeError(
                            (
                                "Embedding model returned "
                                "an unexpected number "
                                "of vectors: "
                                f"expected={len(batch)}, "
                                f"actual={len(vectors)}"
                            )
                        )

                    if (
                        len(token_counts)
                        != len(batch)
                    ):
                        raise RuntimeError(
                            (
                                "Token counter returned "
                                "an unexpected number "
                                "of values: "
                                f"expected={len(batch)}, "
                                f"actual="
                                f"{len(token_counts)}"
                            )
                        )

                    sql_chunks: list[
                        Chunk
                    ] = []

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
                            content=content,
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

                    #
                    # create_many performs flush(),
                    # therefore chunk.id is available
                    # before the transaction is committed.
                    #
                    chunk_repository.create_many(
                        sql_chunks
                    )

                    qdrant_points: list[
                        PointStruct
                    ] = []

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

                    #
                    # qdrant_store.upsert()
                    # has its own retry logic.
                    #
                    # SQL is committed only AFTER
                    # Qdrant confirms the write.
                    #
                    qdrant_store.upsert(
                        qdrant_points
                    )

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
                        (
                            "Embedding batch "
                            f"{batch_number}/"
                            f"{batch_count} | "
                            f"{processed_chunks}/"
                            f"{total_chunks} chunks | "
                            f"{speed:.2f} chunks/sec | "
                            f"ETA {eta:.0f} sec"
                        )
                    )

                    logger.info(
                        (
                            "Embedding batch completed | "
                            "source_id=%s | "
                            "batch=%s/%s | "
                            "processed=%s/%s"
                        ),
                        source.id,
                        batch_number,
                        batch_count,
                        processed_chunks,
                        total_chunks,
                    )

            except Exception:
                #
                # Important:
                #
                # A timeout does not guarantee that
                # Qdrant rejected the upsert.
                # It may have accepted the vectors and
                # only timed out while returning a response.
                #
                # Also, earlier batches in this rebuild
                # may already have been committed in SQL.
                #
                # Clear all data for the documents being
                # rebuilt so the next attempt starts clean.
                #
                session.rollback()

                logger.exception(
                    (
                        "Vectorization failed | "
                        "source_id=%s | "
                        "cleaning partial rebuild"
                    ),
                    source.id,
                )

                print()
                print(
                    (
                        "[Vectorization] "
                        "Vectorization failed. "
                        "Cleaning partial rebuild..."
                    )
                )

                self._cleanup_failed_rebuild(
                    session=session,
                    chunk_repository=(
                        chunk_repository
                    ),
                    source_id=(
                        source.id
                    ),
                    document_ids=(
                        rebuild_document_ids
                    ),
                )

                raise

            embedding_elapsed = (
                time.perf_counter()
                - embedding_started
            )

            total_elapsed = (
                time.perf_counter()
                - started_at
            )

            print()
            print(
                "-" * 70
            )

            print(
                (
                    "Created chunks    : "
                    f"{total_chunks}"
                )
            )

            print(
                (
                    "Chunking time     : "
                    f"{chunking_elapsed:.2f} sec"
                )
            )

            print(
                (
                    "Embedding time    : "
                    f"{embedding_elapsed:.2f} sec"
                )
            )

            print(
                (
                    "Total time        : "
                    f"{total_elapsed:.2f} sec"
                )
            )

            if embedding_elapsed > 0:
                print(
                    (
                        "Embedding speed   : "
                        f"{total_chunks / embedding_elapsed:.2f} "
                        "chunks/sec"
                    )
                )

            print(
                "=" * 70
            )

            print()

            logger.info(
                (
                    "Vectorization completed | "
                    "source_id=%s | "
                    "chunks=%s | "
                    "chunking=%.2fs | "
                    "embedding=%.2fs | "
                    "total=%.2fs"
                ),
                source.id,
                total_chunks,
                chunking_elapsed,
                embedding_elapsed,
                total_elapsed,
            )

            return total_chunks

    @staticmethod
    def _cleanup_failed_rebuild(
        session,
        chunk_repository: ChunkRepository,
        source_id: int,
        document_ids: list[int],
    ) -> None:
        logger.info(
            (
                "Cleaning partial vectorization "
                "rebuild | "
                "source_id=%s | documents=%s"
            ),
            source_id,
            len(document_ids),
        )

        #
        # Remove any vectors Qdrant may have
        # accepted during this rebuild.
        #
        for document_id in document_ids:
            try:
                qdrant_store.delete_by_document_id(
                    document_id
                )

                logger.info(
                    (
                        "Partial Qdrant data removed | "
                        "source_id=%s | "
                        "document_id=%s"
                    ),
                    source_id,
                    document_id,
                )

            except Exception:
                #
                # Do not stop SQL cleanup if Qdrant
                # itself is currently unavailable.
                #
                logger.exception(
                    (
                        "Failed to clean Qdrant "
                        "vectors after "
                        "vectorization error | "
                        "source_id=%s | "
                        "document_id=%s"
                    ),
                    source_id,
                    document_id,
                )

        #
        # Remove SQL chunks from all batches that
        # may already have been committed.
        #
        try:
            chunk_repository.delete_by_document_ids(
                document_ids
            )

            session.commit()

            logger.info(
                (
                    "Partial SQL rebuild cleaned | "
                    "source_id=%s | documents=%s"
                ),
                source_id,
                len(document_ids),
            )

        except Exception:
            session.rollback()

            logger.exception(
                (
                    "Failed to clean SQL chunks "
                    "after vectorization error | "
                    "source_id=%s"
                ),
                source_id,
            )

        logger.info(
            (
                "Partial vectorization cleanup "
                "finished | source_id=%s"
            ),
            source_id,
        )

    @staticmethod
    def _print_header(
        source,
        all_documents,
        active_documents,
        profile,
    ) -> None:
        print()
        print(
            "=" * 70
        )

        print(
            f"[Vectorization] {source.name}"
        )

        print(
            "=" * 70
        )

        print(
            (
                "Source type       : "
                f"{source.source_type}"
            )
        )

        print(
            (
                "Documents total   : "
                f"{len(all_documents)}"
            )
        )

        print(
            (
                "Documents active  : "
                f"{len(active_documents)}"
            )
        )

        print(
            (
                "Chunk size        : "
                f"{profile.chunk_size}"
            )
        )

        print(
            (
                "Chunk overlap     : "
                f"{profile.chunk_overlap}"
            )
        )

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