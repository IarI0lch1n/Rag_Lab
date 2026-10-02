import logging
import time

from collections.abc import (
    Callable,
)

from typing import (
    TypeVar,
)

from qdrant_client import (
    QdrantClient,
)

from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from src.config import settings


logger = logging.getLogger(
    "advisor.qdrant"
)


T = TypeVar("T")


class QdrantStore:

    def __init__(self) -> None:

        self.collection_name = (
            settings.qdrant_collection
        )

        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=(
                settings.qdrant_api_key
            ),
            timeout=(
                settings
                .qdrant_timeout_seconds
            ),
        )

    #
    # RETRY
    #

    def _with_retry(
        self,
        operation_name: str,
        operation: Callable[[], T],
    ) -> T:

        max_attempts = max(
            1,
            int(
                settings
                .qdrant_max_attempts
            ),
        )

        base_delay = max(
            0.1,
            float(
                settings
                .qdrant_retry_base_delay_seconds
            ),
        )

        for attempt in range(
            1,
            max_attempts + 1,
        ):

            try:

                return operation()

            except Exception as exc:

                transient = (
                    self._is_transient_error(
                        exc
                    )
                )

                if (
                    not transient
                    or attempt
                    >= max_attempts
                ):

                    logger.exception(
                        (
                            "Qdrant operation "
                            "failed | "
                            "operation=%s | "
                            "attempt=%s/%s"
                        ),
                        operation_name,
                        attempt,
                        max_attempts,
                    )

                    raise

                delay = (
                    base_delay
                    * (
                        2
                        ** (
                            attempt - 1
                        )
                    )
                )

                logger.warning(
                    (
                        "Temporary Qdrant "
                        "failure | "
                        "operation=%s | "
                        "attempt=%s/%s | "
                        "retry_in=%.1fs | "
                        "error=%s"
                    ),
                    operation_name,
                    attempt,
                    max_attempts,
                    delay,
                    exc,
                )

                print(
                    f"[Qdrant] Temporary failure "
                    f"during {operation_name}. "
                    f"Retry {attempt + 1}/"
                    f"{max_attempts} "
                    f"in {delay:.1f}s..."
                )

                time.sleep(
                    delay
                )

        raise RuntimeError(
            (
                "Unexpected Qdrant "
                "retry state."
            )
        )

    @staticmethod
    def _is_transient_error(
        exc: Exception,
    ) -> bool:

        message = str(
            exc
        ).lower()

        markers = (
            "timed out",
            "timeout",
            "read timeout",
            "write timeout",
            "read operation timed out",
            "write operation timed out",
            "connection reset",
            "connection aborted",
            "connection refused",
            "temporarily unavailable",
            "service unavailable",
            "502",
            "503",
            "504",
            "429",
        )

        return any(
            marker in message
            for marker in markers
        )

    #
    # CONNECTION
    #

    def test_connection(
        self,
    ) -> tuple[bool, str]:

        try:

            collections = (
                self._with_retry(
                    (
                        "connection test"
                    ),
                    lambda:
                    self.client
                    .get_collections(),
                )
            )

            collection_names = [
                collection.name
                for collection
                in collections.collections
            ]

            if collection_names:

                return (
                    True,
                    (
                        "Connected to Qdrant. "
                        f"Collections: "
                        f"{', '.join(collection_names)}"
                    ),
                )

            return (
                True,
                (
                    "Connected to Qdrant. "
                    "No collections yet."
                ),
            )

        except Exception as exc:

            return (
                False,
                str(exc),
            )

    #
    # COLLECTION
    #

    def ensure_collection(
        self,
        vector_size: int,
    ) -> None:

        exists = (
            self._with_retry(
                (
                    "collection existence "
                    "check"
                ),
                lambda:
                self.client
                .collection_exists(
                    self.collection_name
                ),
            )
        )

        if not exists:

            self._with_retry(
                "create collection",
                lambda:
                self.client
                .create_collection(
                    collection_name=(
                        self.collection_name
                    ),
                    vectors_config=(
                        VectorParams(
                            size=vector_size,
                            distance=(
                                Distance.COSINE
                            ),
                        )
                    ),
                ),
            )

            print(
                (
                    "[Qdrant] Created "
                    f"collection "
                    f"'{self.collection_name}' "
                    f"with vector size "
                    f"{vector_size}."
                )
            )

        self._ensure_payload_indexes()

    def _ensure_payload_indexes(
        self,
    ) -> None:

        collection_info = (
            self._with_retry(
                "read collection metadata",
                lambda:
                self.client
                .get_collection(
                    self.collection_name
                ),
            )
        )

        payload_schema = (
            collection_info
            .payload_schema
            or {}
        )

        required_indexes = {
            "source_id": (
                PayloadSchemaType.INTEGER
            ),
            "document_id": (
                PayloadSchemaType.INTEGER
            ),
        }

        for (
            field_name,
            field_schema,
        ) in required_indexes.items():

            if (
                field_name
                in payload_schema
            ):
                continue

            print(
                (
                    "[Qdrant] Creating "
                    "payload index: "
                    f"{field_name}"
                )
            )

            try:

                self._with_retry(
                    (
                        "create payload "
                        f"index {field_name}"
                    ),
                    lambda
                    field_name=field_name,
                    field_schema=field_schema:
                    self.client
                    .create_payload_index(
                        collection_name=(
                            self
                            .collection_name
                        ),
                        field_name=(
                            field_name
                        ),
                        field_schema=(
                            field_schema
                        ),
                        wait=True,
                    ),
                )

            except Exception as exc:

                message = str(
                    exc
                ).lower()

                if (
                    "already exists"
                    not in message
                    and
                    "already indexed"
                    not in message
                ):
                    raise

        print(
            "[Qdrant] Payload indexes ready."
        )

    #
    # UPSERT
    #

    def upsert(
        self,
        points: list[
            PointStruct
        ],
    ) -> None:

        if not points:
            return

        batch_size = max(
            1,
            int(
                settings
                .qdrant_upsert_batch_size
            ),
        )

        total = len(
            points
        )

        for start in range(
            0,
            total,
            batch_size,
        ):

            batch = points[
                start:
                start + batch_size
            ]

            batch_number = (
                start
                // batch_size
                + 1
            )

            batch_count = (
                (
                    total
                    + batch_size
                    - 1
                )
                // batch_size
            )

            self._with_retry(
                (
                    "upsert vectors "
                    f"{batch_number}/"
                    f"{batch_count}"
                ),
                lambda
                batch=batch:
                self.client.upsert(
                    collection_name=(
                        self.collection_name
                    ),
                    points=batch,
                    wait=True,
                ),
            )

    #
    # DELETE
    #

    def delete_points(
        self,
        point_ids: list[str],
    ) -> None:

        if not point_ids:
            return

        exists = (
            self._with_retry(
                (
                    "collection existence "
                    "check"
                ),
                lambda:
                self.client
                .collection_exists(
                    self.collection_name
                ),
            )
        )

        if not exists:
            return

        self._with_retry(
            "delete points",
            lambda:
            self.client.delete(
                collection_name=(
                    self.collection_name
                ),
                points_selector=(
                    point_ids
                ),
                wait=True,
            ),
        )

    def delete_by_source_id(
        self,
        source_id: int,
    ) -> None:

        exists = (
            self._with_retry(
                (
                    "collection existence "
                    "check"
                ),
                lambda:
                self.client
                .collection_exists(
                    self.collection_name
                ),
            )
        )

        if not exists:
            return

        self._ensure_payload_indexes()

        self._with_retry(
            (
                "delete vectors "
                f"for source {source_id}"
            ),
            lambda:
            self.client.delete(
                collection_name=(
                    self.collection_name
                ),
                points_selector=(
                    FilterSelector(
                        filter=Filter(
                            must=[
                                FieldCondition(
                                    key=(
                                        "source_id"
                                    ),
                                    match=(
                                        MatchValue(
                                            value=(
                                                source_id
                                            )
                                        )
                                    ),
                                )
                            ]
                        )
                    )
                ),
                wait=True,
            ),
        )

        print(
            (
                "[Qdrant] Deleted vectors "
                f"for source_id="
                f"{source_id}"
            )
        )

    def delete_by_document_id(
        self,
        document_id: int,
    ) -> None:

        exists = (
            self._with_retry(
                (
                    "collection existence "
                    "check"
                ),
                lambda:
                self.client
                .collection_exists(
                    self.collection_name
                ),
            )
        )

        if not exists:
            return

        self._ensure_payload_indexes()

        self._with_retry(
            (
                "delete vectors "
                f"for document "
                f"{document_id}"
            ),
            lambda:
            self.client.delete(
                collection_name=(
                    self.collection_name
                ),
                points_selector=(
                    FilterSelector(
                        filter=Filter(
                            must=[
                                FieldCondition(
                                    key=(
                                        "document_id"
                                    ),
                                    match=(
                                        MatchValue(
                                            value=(
                                                document_id
                                            )
                                        )
                                    ),
                                )
                            ]
                        )
                    )
                ),
                wait=True,
            ),
        )

    #
    # SEARCH
    #

    def search(
        self,
        vector: list[float],
        limit: int = 10,
    ):

        response = (
            self._with_retry(
                "vector search",
                lambda:
                self.client
                .query_points(
                    collection_name=(
                        self.collection_name
                    ),
                    query=vector,
                    limit=limit,
                    with_payload=True,
                ),
            )
        )

        return response.points


qdrant_store = QdrantStore()