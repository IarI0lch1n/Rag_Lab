import json

import trafilatura

from bs4 import BeautifulSoup

from src.grabber.base import (
    GrabbedDocument,
)
from src.parsers.base import (
    BaseParser,
    ParsedDocument,
)


class TextParser(BaseParser):

    CODE_EXTENSIONS = {
        ".py",

        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".vue",

        ".php",

        ".java",
        ".cs",

        ".c",
        ".cpp",
        ".cc",
        ".h",
        ".hpp",

        ".go",
        ".rs",
        ".rb",

        ".swift",
        ".kt",
        ".kts",

        ".sql",

        ".css",
        ".scss",
        ".sass",
        ".less",

        ".sh",
        ".ps1",
        ".bat",
    }

    def parse(
        self,
        document: GrabbedDocument,
    ) -> ParsedDocument:

        text = self._decode(
            document.content
        )

        extension = (
            document.file_extension
            or ""
        ).lower()

        mime_type = (
            document.mime_type
            or "text/plain"
        )

        metadata = {
            "parser": "text",
            "encoding": "auto",
        }

        if (
            mime_type
            == "text/html"
            or extension
            in {
                ".html",
                ".htm",
            }
        ):
            text = (
                self._parse_html(
                    text
                )
            )

            document_type = (
                "html"
            )

        elif (
            mime_type
            == "application/json"
            or extension
            == ".json"
        ):
            text = (
                self._format_json(
                    text
                )
            )

            document_type = (
                "json"
            )

        elif extension in {
            ".md",
            ".markdown",
        }:
            document_type = (
                "markdown"
            )

        elif extension == ".csv":
            document_type = (
                "csv"
            )

        elif extension == ".xml":
            document_type = (
                "xml"
            )

        elif (
            extension
            in self.CODE_EXTENSIONS
        ):
            document_type = (
                "code"
            )

        else:
            document_type = (
                "text"
            )

        text = (
            text.strip()
        )

        if not text:
            raise ValueError(
                f"No text could be extracted "
                f"from '{document.name}'."
            )

        return ParsedDocument(
            title=document.name,
            text=text,
            document_type=(
                document_type
            ),
            mime_type=(
                mime_type
            ),
            external_id=(
                document.external_id
            ),
            metadata=(
                metadata
            ),
        )

    @staticmethod
    def _decode(
        data: bytes,
    ) -> str:

        encodings = [
            "utf-8-sig",
            "utf-8",
            "utf-16",
            "cp1251",
            "windows-1252",
            "latin-1",
        ]

        for encoding in encodings:
            try:
                return data.decode(
                    encoding
                )

            except UnicodeDecodeError:
                continue

        raise ValueError(
            "Unable to decode text file."
        )

    @staticmethod
    def _parse_html(
        html: str,
    ) -> str:

        extracted = (
            trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                include_links=False,
                favor_precision=True,
            )
        )

        if extracted:
            return (
                extracted.strip()
            )

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        for tag in soup(
            [
                "script",
                "style",
                "noscript",
                "nav",
                "footer",
            ]
        ):
            tag.decompose()

        return soup.get_text(
            separator="\n",
            strip=True,
        )

    @staticmethod
    def _format_json(
        text: str,
    ) -> str:

        try:
            data = json.loads(
                text
            )

            return json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )

        except json.JSONDecodeError:
            return text


text_parser = TextParser()