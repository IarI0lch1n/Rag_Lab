from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Source


class SourceRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def get_all(
        self,
    ) -> list[Source]:
        statement = (
            select(Source)
            .order_by(
                Source.created_at.desc()
            )
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def get_by_id(
        self,
        source_id: int,
    ) -> Source | None:
        return self.session.get(
            Source,
            source_id,
        )

    def find_by_uri(
        self,
        uri: str,
    ) -> Source | None:
        statement = (
            select(Source)
            .where(
                Source.uri == uri
            )
        )

        return self.session.scalar(
            statement
        )

    def find_by_uri_excluding_id(
        self,
        uri: str,
        source_id: int,
    ) -> Source | None:
        statement = (
            select(Source)
            .where(
                Source.uri == uri,
                Source.id != source_id,
            )
        )

        return self.session.scalar(
            statement
        )

    def find_file_by_hash(
        self,
        content_hash: str,
    ) -> Source | None:
        statement = (
            select(Source)
            .where(
                Source.source_type == "file",
                Source.content_hash == content_hash,
            )
        )

        return self.session.scalar(
            statement
        )

    def find_file_by_hash_excluding_id(
        self,
        content_hash: str,
        source_id: int,
    ) -> Source | None:
        statement = (
            select(Source)
            .where(
                Source.source_type == "file",
                Source.content_hash == content_hash,
                Source.id != source_id,
            )
        )

        return self.session.scalar(
            statement
        )

    def create(
        self,
        source: Source,
    ) -> Source:
        self.session.add(
            source
        )

        self.session.flush()
        self.session.refresh(
            source
        )

        return source

    def save(
        self,
        source: Source,
    ) -> Source:
        self.session.add(
            source
        )

        self.session.flush()

        return source

    def delete(
        self,
        source: Source,
    ) -> None:
        self.session.delete(
            source
        )

    def count(
        self,
    ) -> int:
        return len(
            self.get_all()
        )