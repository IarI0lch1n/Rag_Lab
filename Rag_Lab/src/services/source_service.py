import hashlib
import io
import json
import re
import zipfile

from pathlib import Path
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)

from src.repositories.document_repository import (
    DocumentRepository,
)

from src.db.models import Source
from src.db.session import SessionLocal
from src.repositories.source_repository import SourceRepository


class DuplicateSourceError(ValueError):
    pass


class SourceNotFoundError(ValueError):
    pass


class InvalidSourceError(ValueError):
    pass


class SourceService:
    GIT_HOSTS = {
        "github.com",
        "gitlab.com",
        "bitbucket.org",
    }

    def update_url_source(
        self,
        source_id: int,
        url: str,
        name: str | None = None,
    ) -> Source:
        normalized_url = self.normalize_url(
            url
        )

        source_type = (
            self.detect_url_source_type(
                normalized_url
            )
        )

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
                raise SourceNotFoundError(
                    f"Source with id "
                    f"{source_id} was not found."
                )

            if source.source_type == "file":
                raise InvalidSourceError(
                    "A file source cannot be "
                    "converted to a URL source."
                )

            duplicate = (
                source_repository
                .find_by_uri_excluding_id(
                    normalized_url,
                    source_id,
                )
            )

            if duplicate is not None:
                raise DuplicateSourceError(
                    f"Source already exists "
                    f"with id {duplicate.id}: "
                    f"{duplicate.uri}"
                )

            source.uri = normalized_url

            source.source_type = (
                source_type
            )

            source.name = (
                name
                or self.create_name_from_url(
                    normalized_url,
                    source_type,
                )
            )

            source.status = "pending"
            source.last_error = None
            source.last_synced_at = None

            source.etag = None
            source.last_modified = None

            source.git_branch = None
            source.git_commit_sha = None

            document_repository.mark_all_inactive(
                source.id
            )

            source_repository.save(
                source
            )

            session.commit()

            return source

    def replace_file_source(
        self,
        source_id: int,
        file_path: str | Path,
        name: str | None = None,
    ) -> Source:
        path = Path(
            file_path
        )

        if not path.exists():
            raise InvalidSourceError(
                f"File does not exist: "
                f"{path}"
            )

        if not path.is_file():
            raise InvalidSourceError(
                f"Path is not a file: "
                f"{path}"
            )

        file_data = path.read_bytes()

        if not file_data:
            raise InvalidSourceError(
                f"File is empty: "
                f"{path.name}"
            )

        content_hash = hashlib.sha256(
            file_data
        ).hexdigest()

        mime_type, detected_extension = (
            self.detect_file_type(
                file_data=file_data,
                filename=path.name,
            )
        )

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
                raise SourceNotFoundError(
                    f"Source with id "
                    f"{source_id} was not found."
                )

            if source.source_type != "file":
                raise InvalidSourceError(
                    "Only file sources can "
                    "have their file replaced."
                )

            duplicate = (
                source_repository
                .find_file_by_hash_excluding_id(
                    content_hash,
                    source_id,
                )
            )

            if duplicate is not None:
                raise DuplicateSourceError(
                    f"This file already exists "
                    f"as source {duplicate.id}: "
                    f"{duplicate.name}"
                )

            source.name = (
                name
                or path.name
            )

            source.original_filename = (
                path.name
            )

            source.mime_type = (
                mime_type
            )

            source.file_extension = (
                detected_extension
            )

            source.file_size_bytes = (
                len(file_data)
            )

            source.file_data = (
                file_data
            )

            source.content_hash = (
                content_hash
            )

            source.status = "pending"
            source.last_error = None
            source.last_synced_at = None

            document_repository.mark_all_inactive(
                source.id
            )

            source_repository.save(
                source
            )

            session.commit()

            return source

    def rename_source(
        self,
        source_id: int,
        name: str,
    ) -> Source:
        name = name.strip()

        if not name:
            raise InvalidSourceError(
                "Source name cannot be empty."
            )

        with SessionLocal() as session:
            repository = (
                SourceRepository(
                    session
                )
            )

            source = repository.get_by_id(
                source_id
            )

            if source is None:
                raise SourceNotFoundError(
                    f"Source with id "
                    f"{source_id} was not found."
                )

            source.name = name

            repository.save(
                source
            )

            session.commit()

            return source

    def get_sources(self) -> list[Source]:
        with SessionLocal() as session:
            repository = SourceRepository(session)

            return repository.get_all()

    def get_source(self, source_id: int) -> Source:
        with SessionLocal() as session:
            repository = SourceRepository(session)

            source = repository.get_by_id(source_id)

            if source is None:
                raise SourceNotFoundError(
                    f"Source with id {source_id} was not found."
                )

            return source

    def add_url_source(
        self,
        url: str,
        name: str | None = None,
    ) -> Source:
        normalized_url = self.normalize_url(url)
        source_type = self.detect_url_source_type(normalized_url)

        with SessionLocal() as session:
            repository = SourceRepository(session)

            existing_source = repository.find_by_uri(
                normalized_url
            )

            if existing_source is not None:
                raise DuplicateSourceError(
                    f"Source already exists with id "
                    f"{existing_source.id}: "
                    f"{existing_source.uri}"
                )

            source = Source(
                name=name or self.create_name_from_url(
                    normalized_url,
                    source_type,
                ),
                source_type=source_type,
                uri=normalized_url,
                status="pending",
            )

            repository.create(source)

            session.commit()

            return source

    def add_file_source(
        self,
        file_path: str | Path,
        name: str | None = None,
    ) -> Source:
        path = Path(file_path)

        if not path.exists():
            raise InvalidSourceError(
                f"File does not exist: {path}"
            )

        if not path.is_file():
            raise InvalidSourceError(
                f"Path is not a file: {path}"
            )

        file_data = path.read_bytes()

        if not file_data:
            raise InvalidSourceError(
                f"File is empty: {path.name}"
            )

        content_hash = hashlib.sha256(
            file_data
        ).hexdigest()

        mime_type, detected_extension = (
            self.detect_file_type(
                file_data=file_data,
                filename=path.name,
            )
        )

        with SessionLocal() as session:
            repository = SourceRepository(session)

            existing_source = repository.find_file_by_hash(
                content_hash
            )

            if existing_source is not None:
                raise DuplicateSourceError(
                    f"File already exists with id "
                    f"{existing_source.id}: "
                    f"{existing_source.name}"
                )

            source = Source(
                name=name or path.name,
                source_type="file",
                original_filename=path.name,
                mime_type=mime_type,
                file_extension=detected_extension,
                file_size_bytes=len(file_data),
                file_data=file_data,
                content_hash=content_hash,
                status="pending",
            )

            repository.create(source)

            session.commit()

            return source

    def delete_source(self, source_id: int) -> None:
        with SessionLocal() as session:
            repository = SourceRepository(session)

            source = repository.get_by_id(source_id)

            if source is None:
                raise SourceNotFoundError(
                    f"Source with id {source_id} was not found."
                )

            repository.delete(source)

            session.commit()

    @staticmethod
    def normalize_url(url: str) -> str:
        url = url.strip()

        if not url:
            raise InvalidSourceError(
                "URL cannot be empty."
            )

        if "://" not in url:
            url = f"https://{url}"

        parsed = urlsplit(url)

        if parsed.scheme.lower() not in {
            "http",
            "https",
        }:
            raise InvalidSourceError(
                "Only HTTP and HTTPS URLs are supported."
            )

        if not parsed.hostname:
            raise InvalidSourceError(
                f"Invalid URL: {url}"
            )

        scheme = parsed.scheme.lower()
        hostname = parsed.hostname.lower()

        port = parsed.port

        if (
            port is not None
            and not (
                scheme == "http" and port == 80
            )
            and not (
                scheme == "https" and port == 443
            )
        ):
            netloc = f"{hostname}:{port}"
        else:
            netloc = hostname

        path = re.sub(
            r"/+",
            "/",
            parsed.path,
        )

        if path != "/":
            path = path.rstrip("/")

        query_items = parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )

        query_items.sort()

        query = urlencode(
            query_items,
            doseq=True,
        )

        return urlunsplit(
            (
                scheme,
                netloc,
                path,
                query,
                "",
            )
        )

    def detect_url_source_type(
        self,
        url: str,
    ) -> str:
        parsed = urlsplit(url)

        hostname = (
            parsed.hostname or ""
        ).lower()

        path = parsed.path.lower()

        if path.endswith(".git"):
            return "git"

        if hostname in self.GIT_HOSTS:
            path_parts = [
                part
                for part in parsed.path.split("/")
                if part
            ]

            if len(path_parts) >= 2:
                return "git"

        return "web"

    @staticmethod
    def create_name_from_url(
        url: str,
        source_type: str,
    ) -> str:
        parsed = urlsplit(url)

        hostname = parsed.hostname or url

        path_parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        if (
            source_type == "git"
            and len(path_parts) >= 2
        ):
            owner = path_parts[0]

            repository = path_parts[1]

            if repository.endswith(".git"):
                repository = repository[:-4]

            return f"{owner}/{repository}"

        if path_parts:
            return (
                f"{hostname}/"
                f"{'/'.join(path_parts[:2])}"
            )

        return hostname

    @staticmethod
    def detect_file_type(
        file_data: bytes,
        filename: str,
    ) -> tuple[str, str | None]:
        original_extension = (
            Path(filename).suffix.lower() or None
        )

        if file_data.startswith(b"%PDF-"):
            return (
                "application/pdf",
                ".pdf",
            )

        if file_data.startswith(
            b"\x89PNG\r\n\x1a\n"
        ):
            return (
                "image/png",
                ".png",
            )

        if file_data.startswith(
            b"\xff\xd8\xff"
        ):
            return (
                "image/jpeg",
                ".jpg",
            )

        if file_data.startswith(
            b"GIF87a"
        ) or file_data.startswith(
            b"GIF89a"
        ):
            return (
                "image/gif",
                ".gif",
            )

        if file_data.startswith(
            b"PK\x03\x04"
        ):
            office_type = (
                SourceService.detect_office_zip_type(
                    file_data
                )
            )

            if office_type is not None:
                return office_type

            return (
                "application/zip",
                ".zip",
            )

        if file_data.startswith(
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        ):
            legacy_types = {
                ".doc": "application/msword",
                ".xls": "application/vnd.ms-excel",
                ".ppt": "application/vnd.ms-powerpoint",
            }

            return (
                legacy_types.get(
                    original_extension,
                    "application/x-ole-storage",
                ),
                original_extension,
            )

        text = SourceService.try_decode_text(
            file_data
        )

        if text is not None:
            stripped = text.lstrip()

            if SourceService.looks_like_json(
                stripped
            ):
                return (
                    "application/json",
                    ".json",
                )

            if SourceService.looks_like_html(
                stripped
            ):
                return (
                    "text/html",
                    ".html",
                )

            if original_extension in {
                ".md",
                ".markdown",
            }:
                return (
                    "text/markdown",
                    original_extension,
                )

            if original_extension == ".csv":
                return (
                    "text/csv",
                    ".csv",
                )

            if original_extension == ".xml":
                return (
                    "application/xml",
                    ".xml",
                )

            return (
                "text/plain",
                original_extension or ".txt",
            )

        return (
            "application/octet-stream",
            original_extension,
        )

    @staticmethod
    def detect_office_zip_type(
        file_data: bytes,
    ) -> tuple[str, str] | None:
        try:
            with zipfile.ZipFile(
                io.BytesIO(file_data)
            ) as archive:
                names = {
                    name.lower()
                    for name in archive.namelist()
                }

                if any(
                    name.startswith("word/")
                    for name in names
                ):
                    return (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        ".docx",
                    )

                if any(
                    name.startswith("xl/")
                    for name in names
                ):
                    return (
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ".xlsx",
                    )

                if any(
                    name.startswith("ppt/")
                    for name in names
                ):
                    return (
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        ".pptx",
                    )

        except zipfile.BadZipFile:
            return None

        return None

    @staticmethod
    def try_decode_text(
        file_data: bytes,
    ) -> str | None:
        encodings = (
            "utf-8-sig",
            "utf-16",
            "cp1251",
            "latin-1",
        )

        for encoding in encodings:
            try:
                text = file_data.decode(
                    encoding
                )

                if SourceService.looks_like_text(
                    text
                ):
                    return text

            except UnicodeDecodeError:
                continue

        return None

    @staticmethod
    def looks_like_text(text: str) -> bool:
        if not text:
            return False

        sample = text[:5000]

        printable_count = sum(
            1
            for character in sample
            if (
                character.isprintable()
                or character in "\r\n\t"
            )
        )

        return (
            printable_count
            / len(sample)
            >= 0.90
        )

    @staticmethod
    def looks_like_json(text: str) -> bool:
        if not text:
            return False

        if text[0] not in "[{":
            return False

        try:
            json.loads(text)
            return True
        except json.JSONDecodeError:
            return False

    @staticmethod
    def looks_like_html(text: str) -> bool:
        lowered = text[:2000].lower()

        return (
            "<!doctype html" in lowered
            or "<html" in lowered
            or (
                "<head" in lowered
                and "<body" in lowered
            )
        )


source_service = SourceService()