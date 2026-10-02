import hashlib
import json

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)

from src.db.models import (
    Document,
    IngestionRun,
)

from src.db.session import (
    SessionLocal,
)

from src.grabber.file_grabber import (
    file_grabber,
)

from src.grabber.git_grabber import (
    git_grabber,
)

from src.grabber.web_grabber import (
    web_grabber,
)

from src.parsers.factory import (
    parser_factory,
)

from src.repositories.document_repository import (
    DocumentRepository,
)

from src.repositories.source_repository import (
    SourceRepository,
)


@dataclass
class IngestionResult:
    source_id: int
    source_name: str
    status: str

    documents_discovered: int
    documents_created: int
    documents_updated: int
    documents_skipped: int

    documents_failed: int = 0

    error: str | None = None


class IngestionService:

    def ingest_source(
        self,
        source_id: int,
    ) -> IngestionResult:

        with SessionLocal() as session:

            source_repository = (
                SourceRepository(
                    session
                )
            )

            document_repository = (
                DocumentRepository(
                    session
                )
            )

            source = (
                source_repository
                .get_by_id(
                    source_id
                )
            )

            if source is None:
                raise ValueError(
                    f"Source {source_id} "
                    f"was not found."
                )

            run = IngestionRun(
                source_id=source.id,
                status="running",
                run_type="manual",
            )

            session.add(
                run
            )

            source.status = (
                "processing"
            )

            source.last_error = None

            session.commit()

            run_id = run.id

            try:
                grabbed_documents = (
                    self._grab_source(
                        source
                    )
                )

                if not grabbed_documents:
                    raise ValueError(
                        "Grabber returned "
                        "no documents."
                    )

                run.documents_discovered = (
                    len(
                        grabbed_documents
                    )
                )

                created = 0
                updated = 0
                skipped = 0
                failed = 0

                failed_documents = []

                seen_external_ids: set[
                    str
                ] = set()

                successful_documents = 0

                for grabbed_document in (
                    grabbed_documents
                ):

                    external_id = (
                        grabbed_document.external_id
                        or grabbed_document.name
                    )

                    seen_external_ids.add(
                        external_id
                    )

                    try:
                        result = (
                            self._process_document(
                                source=source,
                                grabbed_document=(
                                    grabbed_document
                                ),
                                document_repository=(
                                    document_repository
                                ),
                            )
                        )

                        if result == "created":
                            created += 1

                        elif result == "updated":
                            updated += 1

                        elif result == "skipped":
                            skipped += 1

                        successful_documents += 1

                    except Exception as document_exc:

                        failed += 1

                        failed_documents.append(
                            (
                                f"{grabbed_document.name}: "
                                f"{document_exc}"
                            )
                        )

                        print(
                            "[WARNING] Could not process "
                            f"'{grabbed_document.name}': "
                            f"{document_exc}"
                        )

                        continue

                if successful_documents == 0:
                    error_details = (
                        "; ".join(
                            failed_documents[:5]
                        )
                    )

                    raise RuntimeError(
                        "None of the discovered "
                        "documents could be parsed. "
                        f"{error_details}"
                    )

                document_repository.mark_missing_inactive(
                    source_id=source.id,
                    active_external_ids=(
                        seen_external_ids
                    ),
                )

                self._update_source_metadata(
                    source=source,
                    documents=(
                        grabbed_documents
                    ),
                )

                now = datetime.now(
                    timezone.utc
                )

                source.status = (
                    "indexed"
                )

                source.last_synced_at = (
                    now
                )

                if failed_documents:
                    source.last_error = (
                        f"{failed} document(s) "
                        f"could not be parsed. "
                        f"First errors: "
                        + "; ".join(
                            failed_documents[:3]
                        )
                    )

                else:
                    source.last_error = None

                run.status = (
                    "completed"
                )

                run.documents_created = (
                    created
                )

                run.documents_updated = (
                    updated
                )

                run.documents_skipped = (
                    skipped
                )

                if failed_documents:
                    run.error_message = (
                        f"Partial indexing: "
                        f"{failed} document(s) failed. "
                        + "; ".join(
                            failed_documents[:5]
                        )
                    )

                else:
                    run.error_message = None

                run.completed_at = (
                    now
                )

                session.commit()

                return IngestionResult(
                    source_id=source.id,
                    source_name=source.name,
                    status="indexed",
                    documents_discovered=(
                        len(
                            grabbed_documents
                        )
                    ),
                    documents_created=(
                        created
                    ),
                    documents_updated=(
                        updated
                    ),
                    documents_skipped=(
                        skipped
                    ),
                    documents_failed=(
                        failed
                    ),
                )

            except Exception as exc:

                session.rollback()

                source = (
                    source_repository
                    .get_by_id(
                        source_id
                    )
                )

                run = session.get(
                    IngestionRun,
                    run_id,
                )

                now = datetime.now(
                    timezone.utc
                )

                if source is not None:

                    source.status = (
                        "failed"
                    )

                    source.last_error = (
                        str(
                            exc
                        )
                    )

                if run is not None:

                    run.status = (
                        "failed"
                    )

                    run.error_message = (
                        str(
                            exc
                        )
                    )

                    run.completed_at = (
                        now
                    )

                session.commit()

                return IngestionResult(
                    source_id=source_id,
                    source_name=(
                        source.name
                        if source
                        else "Unknown"
                    ),
                    status="failed",
                    documents_discovered=0,
                    documents_created=0,
                    documents_updated=0,
                    documents_skipped=0,
                    documents_failed=0,
                    error=str(
                        exc
                    ),
                )

    def _process_document(
        self,
        source,
        grabbed_document,
        document_repository:
        DocumentRepository,
    ) -> str:

        parser = (
            parser_factory
            .get_parser(
                grabbed_document
            )
        )

        parsed_document = (
            parser.parse(
                grabbed_document
            )
        )

        cleaned_text = (
            self.clean_text(
                parsed_document.text
            )
        )

        if not cleaned_text:
            raise ValueError(
                "Document contains "
                "no usable text."
            )

        content_hash = (
            hashlib.sha256(
                cleaned_text.encode(
                    "utf-8"
                )
            )
            .hexdigest()
        )

        external_id = (
            parsed_document.external_id
            or
            grabbed_document.external_id
            or
            parsed_document.title
        )

        metadata = {
            **(
                grabbed_document
                .metadata
            ),
            **(
                parsed_document
                .metadata
            ),
        }

        metadata_json = (
            json.dumps(
                metadata,
                ensure_ascii=False,
            )
        )

        existing_document = (
            document_repository
            .find_by_external_id(
                source_id=(
                    source.id
                ),
                external_id=(
                    external_id
                ),
            )
        )

        if existing_document is None:

            document = Document(
                source_id=(
                    source.id
                ),
                title=(
                    parsed_document.title
                ),
                external_id=(
                    external_id
                ),
                document_type=(
                    parsed_document
                    .document_type
                ),
                mime_type=(
                    parsed_document
                    .mime_type
                ),
                content_hash=(
                    content_hash
                ),
                raw_text=(
                    cleaned_text
                ),
                metadata_json=(
                    metadata_json
                ),
                version=1,
                is_active=True,
            )

            document_repository.create(
                document
            )

            return "created"

        if (
            existing_document.content_hash
            == content_hash
        ):

            existing_document.is_active = (
                True
            )

            existing_document.metadata_json = (
                metadata_json
            )

            document_repository.save(
                existing_document
            )

            return "skipped"

        existing_document.title = (
            parsed_document.title
        )

        existing_document.document_type = (
            parsed_document.document_type
        )

        existing_document.mime_type = (
            parsed_document.mime_type
        )

        existing_document.raw_text = (
            cleaned_text
        )

        existing_document.content_hash = (
            content_hash
        )

        existing_document.metadata_json = (
            metadata_json
        )

        existing_document.version += 1

        existing_document.is_active = (
            True
        )

        document_repository.save(
            existing_document
        )

        return "updated"

    @staticmethod
    def _grab_source(
        source,
    ):

        if (
            source.source_type
            == "file"
        ):
            return (
                file_grabber.grab(
                    source
                )
            )

        if (
            source.source_type
            == "web"
        ):
            return (
                web_grabber.grab(
                    source
                )
            )

        if (
            source.source_type
            == "git"
        ):
            return (
                git_grabber.grab(
                    source
                )
            )

        raise ValueError(
            f"Unsupported source type: "
            f"{source.source_type}"
        )

    @staticmethod
    def _update_source_metadata(
        source,
        documents,
    ) -> None:

        if not documents:
            return

        if (
            source.source_type
            == "git"
        ):

            metadata = (
                documents[0]
                .metadata
            )

            source.git_branch = (
                metadata.get(
                    "branch"
                )
            )

            source.git_commit_sha = (
                metadata.get(
                    "commit_sha"
                )
            )

        elif (
            source.source_type
            == "web"
        ):

            root_document = next(
                (
                    document
                    for document
                    in documents
                    if (
                        document
                        .metadata
                        .get(
                            "is_root"
                        )
                    )
                ),
                None,
            )

            if root_document:

                source.etag = (
                    root_document
                    .metadata
                    .get(
                        "etag"
                    )
                )

                source.last_modified = (
                    root_document
                    .metadata
                    .get(
                        "last_modified"
                    )
                )

    @staticmethod
    def clean_text(
        text: str,
    ) -> str:

        normalized_text = (
            text
            .replace(
                "\r\n",
                "\n",
            )
            .replace(
                "\r",
                "\n",
            )
        )

        lines = []

        for line in (
            normalized_text
            .split("\n")
        ):

            line = " ".join(
                line.split()
            )

            lines.append(
                line
            )

        cleaned_lines = []

        previous_blank = False

        for line in lines:

            is_blank = (
                not line
            )

            if (
                is_blank
                and previous_blank
            ):
                continue

            cleaned_lines.append(
                line
            )

            previous_blank = (
                is_blank
            )

        return "\n".join(
            cleaned_lines
        ).strip()


ingestion_service = (
    IngestionService()
)