from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.orm import Session

from src.db.models import (
    Chunk,
    Document,
)


class ChunkRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def get_by_id(
        self,
        chunk_id: int,
    ) -> Chunk | None:
        return self.session.get(
            Chunk,
            chunk_id,
        )

    def get_by_document_id(
        self,
        document_id: int,
    ) -> list[Chunk]:
        statement = (
            select(Chunk)
            .where(
                Chunk.document_id
                == document_id
            )
            .order_by(
                Chunk.chunk_index.asc()
            )
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def get_by_source_id(
        self,
        source_id: int,
    ) -> list[Chunk]:
        statement = (
            select(Chunk)
            .join(
                Document,
                Chunk.document_id
                == Document.id,
            )
            .where(
                Document.source_id
                == source_id
            )
            .order_by(
                Chunk.document_id.asc(),
                Chunk.chunk_index.asc(),
            )
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def create(
        self,
        chunk: Chunk,
    ) -> Chunk:
        self.session.add(
            chunk
        )

        self.session.flush()

        return chunk

    def create_many(
        self,
        chunks: list[Chunk],
    ) -> list[Chunk]:
        if not chunks:
            return []

        self.session.add_all(
            chunks
        )

        self.session.flush()

        return chunks

    def delete_by_document_id(
        self,
        document_id: int,
    ) -> None:
        self.session.execute(
            delete(Chunk)
            .where(
                Chunk.document_id
                == document_id
            )
        )

        self.session.flush()

    def delete_by_document_ids(
        self,
        document_ids: list[int],
    ) -> None:
        if not document_ids:
            return

        self.session.execute(
            delete(Chunk)
            .where(
                Chunk.document_id.in_(
                    document_ids
                )
            )
        )

        self.session.flush()