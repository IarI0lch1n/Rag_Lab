from qdrant_client import QdrantClient

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


class QdrantStore:
    def __init__(self) -> None:
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=30,
        )

        self.collection_name = (
            settings.qdrant_collection
        )

    def test_connection(
        self,
    ) -> tuple[bool, str]:
        try:
            collections = (
                self.client.get_collections()
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

    def ensure_collection(
        self,
        vector_size: int,
    ) -> None:

        exists = (
            self.client.collection_exists(
                self.collection_name
            )
        )

        if not exists:
            self.client.create_collection(
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
            )

            print(
                f"[Qdrant] Created collection "
                f"'{self.collection_name}' "
                f"with vector size "
                f"{vector_size}."
            )

        #
        # IMPORTANT:
        # Even when collection already exists,
        # make sure required payload indexes exist.
        #
        self._ensure_payload_indexes()

    def _ensure_payload_indexes(
        self,
    ) -> None:

        collection_info = (
            self.client.get_collection(
                self.collection_name
            )
        )

        payload_schema = (
            collection_info.payload_schema
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
                f"[Qdrant] Creating payload "
                f"index: {field_name}"
            )

            try:
                self.client.create_payload_index(
                    collection_name=(
                        self.collection_name
                    ),
                    field_name=(
                        field_name
                    ),
                    field_schema=(
                        field_schema
                    ),
                    wait=True,
                )

            except Exception as exc:
                #
                # Defensive protection in case
                # another process created it
                # between get_collection()
                # and create_payload_index().
                #
                message = str(
                    exc
                ).lower()

                if (
                    "already exists"
                    not in message
                    and "already indexed"
                    not in message
                ):
                    raise

        print(
            "[Qdrant] Payload indexes ready."
        )

    def upsert(
        self,
        points: list[PointStruct],
    ) -> None:

        if not points:
            return

        self.client.upsert(
            collection_name=(
                self.collection_name
            ),
            points=points,
            wait=True,
        )

    def delete_points(
        self,
        point_ids: list[str],
    ) -> None:

        if not point_ids:
            return

        if not self.client.collection_exists(
            self.collection_name
        ):
            return

        self.client.delete(
            collection_name=(
                self.collection_name
            ),
            points_selector=(
                point_ids
            ),
            wait=True,
        )

    def delete_by_source_id(
        self,
        source_id: int,
    ) -> None:

        if not self.client.collection_exists(
            self.collection_name
        ):
            return

        self._ensure_payload_indexes()

        self.client.delete(
            collection_name=(
                self.collection_name
            ),
            points_selector=(
                FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="source_id",
                                match=MatchValue(
                                    value=(
                                        source_id
                                    )
                                ),
                            )
                        ]
                    )
                )
            ),
            wait=True,
        )

        print(
            f"[Qdrant] Deleted vectors "
            f"for source_id={source_id}"
        )

    def delete_by_document_id(
        self,
        document_id: int,
    ) -> None:

        if not self.client.collection_exists(
            self.collection_name
        ):
            return

        self._ensure_payload_indexes()

        self.client.delete(
            collection_name=(
                self.collection_name
            ),
            points_selector=(
                FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="document_id",
                                match=MatchValue(
                                    value=(
                                        document_id
                                    )
                                ),
                            )
                        ]
                    )
                )
            ),
            wait=True,
        )

    def search(
        self,
        vector: list[float],
        limit: int = 10,
    ):
        response = (
            self.client.query_points(
                collection_name=(
                    self.collection_name
                ),
                query=vector,
                limit=limit,
                with_payload=True,
            )
        )

        return (
            response.points
        )


qdrant_store = QdrantStore()