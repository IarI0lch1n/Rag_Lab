import threading

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)

from src.db.session import (
    SessionLocal,
)

from src.repositories.source_repository import (
    SourceRepository,
)

from src.services.ingestion_service import (
    ingestion_service,
)

from src.services.vectorization_service import (
    vectorization_service,
)


@dataclass
class IndexingResult:
    source_id: int
    source_name: str
    status: str

    documents_discovered: int = 0
    documents_created: int = 0
    documents_updated: int = 0
    documents_skipped: int = 0
    documents_failed: int = 0

    chunks_created: int = 0

    error: str | None = None


class IndexingService:
    def __init__(self) -> None:
        self._lock = (
            threading.Lock()
        )

        self._active_sources: set[
            int
        ] = set()

    def index_source(
        self,
        source_id: int,
    ) -> IndexingResult:

        if not self._acquire_source(
            source_id
        ):
            return IndexingResult(
                source_id=source_id,
                source_name=(
                    self._get_source_name(
                        source_id
                    )
                ),
                status="busy",
                error=(
                    "This source is already "
                    "being indexed."
                ),
            )

        try:
            return self._index_source(
                source_id
            )

        finally:
            self._release_source(
                source_id
            )

    def _index_source(
        self,
        source_id: int,
    ) -> IndexingResult:

        print()
        print("=" * 70)
        print(
            f"[Indexing] Starting source "
            f"{source_id}"
        )
        print("=" * 70)

        ingestion_result = (
            ingestion_service.ingest_source(
                source_id
            )
        )

        if (
            ingestion_result.status
            != "indexed"
        ):
            return IndexingResult(
                source_id=source_id,
                source_name=(
                    ingestion_result.source_name
                ),
                status="failed",
                documents_discovered=(
                    ingestion_result
                    .documents_discovered
                ),
                documents_created=(
                    ingestion_result
                    .documents_created
                ),
                documents_updated=(
                    ingestion_result
                    .documents_updated
                ),
                documents_skipped=(
                    ingestion_result
                    .documents_skipped
                ),
                documents_failed=(
                    getattr(
                        ingestion_result,
                        "documents_failed",
                        0,
                    )
                ),
                error=(
                    ingestion_result.error
                ),
            )

        print()
        print(
            "[Indexing] Parsing completed."
        )

        print(
            "[Indexing] Starting "
            "vectorization..."
        )

        try:
            chunks_created = (
                vectorization_service
                .vectorize_source(
                    source_id
                )
            )

        except Exception as exc:
            self._mark_source_failed(
                source_id=source_id,
                error=str(exc),
            )

            print()
            print(
                f"[Indexing] Vectorization "
                f"failed: {exc}"
            )

            return IndexingResult(
                source_id=source_id,
                source_name=(
                    ingestion_result.source_name
                ),
                status="failed",
                documents_discovered=(
                    ingestion_result
                    .documents_discovered
                ),
                documents_created=(
                    ingestion_result
                    .documents_created
                ),
                documents_updated=(
                    ingestion_result
                    .documents_updated
                ),
                documents_skipped=(
                    ingestion_result
                    .documents_skipped
                ),
                documents_failed=(
                    getattr(
                        ingestion_result,
                        "documents_failed",
                        0,
                    )
                ),
                error=(
                    "Documents were parsed, "
                    "but vectorization failed: "
                    f"{exc}"
                ),
            )

        self._mark_source_indexed(
            source_id
        )

        print()
        print(
            "[Indexing] Source is ready "
            "for RAG."
        )
        print("=" * 70)
        print()

        return IndexingResult(
            source_id=source_id,
            source_name=(
                ingestion_result.source_name
            ),
            status="indexed",
            documents_discovered=(
                ingestion_result
                .documents_discovered
            ),
            documents_created=(
                ingestion_result
                .documents_created
            ),
            documents_updated=(
                ingestion_result
                .documents_updated
            ),
            documents_skipped=(
                ingestion_result
                .documents_skipped
            ),
            documents_failed=(
                getattr(
                    ingestion_result,
                    "documents_failed",
                    0,
                )
            ),
            chunks_created=(
                chunks_created
            ),
        )

    def _acquire_source(
        self,
        source_id: int,
    ) -> bool:
        with self._lock:
            if (
                source_id
                in self._active_sources
            ):
                return False

            self._active_sources.add(
                source_id
            )

            return True

    def _release_source(
        self,
        source_id: int,
    ) -> None:
        with self._lock:
            self._active_sources.discard(
                source_id
            )

    @staticmethod
    def _get_source_name(
        source_id: int,
    ) -> str:
        with SessionLocal() as session:
            repository = (
                SourceRepository(
                    session
                )
            )

            source = (
                repository.get_by_id(
                    source_id
                )
            )

            if source is None:
                return "Unknown"

            return source.name

    @staticmethod
    def _mark_source_failed(
        source_id: int,
        error: str,
    ) -> None:
        with SessionLocal() as session:
            repository = (
                SourceRepository(
                    session
                )
            )

            source = (
                repository.get_by_id(
                    source_id
                )
            )

            if source is None:
                return

            source.status = "failed"
            source.last_error = error

            repository.save(
                source
            )

            session.commit()

    @staticmethod
    def _mark_source_indexed(
        source_id: int,
    ) -> None:
        with SessionLocal() as session:
            repository = (
                SourceRepository(
                    session
                )
            )

            source = (
                repository.get_by_id(
                    source_id
                )
            )

            if source is None:
                return

            source.status = "indexed"
            source.last_error = None

            source.last_synced_at = (
                datetime.now(
                    timezone.utc
                )
            )

            repository.save(
                source
            )

            session.commit()


indexing_service = IndexingService()