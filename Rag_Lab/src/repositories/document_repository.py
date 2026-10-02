from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Document


class DocumentRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def get_by_id(
        self,
        document_id: int,
    ) -> Document | None:
        return self.session.get(
            Document,
            document_id,
        )

    def get_by_source_id(
        self,
        source_id: int,
    ) -> list[Document]:
        statement = (
            select(Document)
            .where(
                Document.source_id == source_id
            )
            .order_by(
                Document.id.asc()
            )
        )

        return list(
            self.session.scalars(
                statement
            ).all()
        )

    def find_by_external_id(
        self,
        source_id: int,
        external_id: str | None,
    ) -> Document | None:
        statement = (
            select(Document)
            .where(
                Document.source_id == source_id,
                Document.external_id == external_id,
            )
        )

        return self.session.scalar(
            statement
        )

    def create(
        self,
        document: Document,
    ) -> Document:
        self.session.add(
            document
        )

        self.session.flush()
        self.session.refresh(
            document
        )

        return document

    def save(
        self,
        document: Document,
    ) -> Document:
        self.session.add(
            document
        )

        self.session.flush()

        return document

    def delete(
        self,
        document: Document,
    ) -> None:
        self.session.delete(
            document
        )

    def mark_missing_inactive(
        self,
        source_id: int,
        active_external_ids: set[str],
    ) -> int:
        documents = self.get_by_source_id(
            source_id
        )

        count = 0

        for document in documents:
            if (
                document.external_id
                and document.external_id
                not in active_external_ids
                and document.is_active
            ):
                document.is_active = False

                self.session.add(
                    document
                )

                count += 1

        self.session.flush()

        return count

    def mark_all_inactive(
        self,
        source_id: int,
    ) -> int:
        documents = self.get_by_source_id(
            source_id
        )

        count = 0

        for document in documents:
            if not document.is_active:
                continue

            document.is_active = False

            self.session.add(
                document
            )

            count += 1

        self.session.flush()

        return count