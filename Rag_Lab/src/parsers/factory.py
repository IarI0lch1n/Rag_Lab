from src.grabber.base import (
    GrabbedDocument,
)

from src.parsers.base import (
    BaseParser,
)

from src.parsers.docx_parser import (
    docx_parser,
)

from src.parsers.pdf_parser import (
    pdf_parser,
)

from src.parsers.pptx_parser import (
    pptx_parser,
)

from src.parsers.text_parser import (
    text_parser,
)


class UnsupportedFileTypeError(
    ValueError
):
    pass


class ParserFactory:

    TEXT_EXTENSIONS = {
        ".txt",

        ".md",
        ".markdown",
        ".rst",

        ".csv",

        ".json",

        ".xml",

        ".html",
        ".htm",

        ".yaml",
        ".yml",

        ".toml",
        ".ini",
        ".cfg",
    }

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

    TEXT_MIME_TYPES = {
        "text/plain",
        "text/markdown",
        "text/csv",
        "text/html",
        "text/yaml",

        "application/json",
        "application/xml",
        "text/xml",
    }

    def get_parser(
        self,
        document: GrabbedDocument,
    ) -> BaseParser:

        extension = (
            document.file_extension
            or ""
        ).lower()

        mime_type = (
            document.mime_type
            or ""
        ).lower()

        if (
            extension == ".pdf"
            or mime_type
            == "application/pdf"
        ):
            return pdf_parser

        if (
            extension == ".docx"
            or mime_type
            == (
                "application/vnd.openxmlformats-"
                "officedocument.wordprocessingml."
                "document"
            )
        ):
            return docx_parser

        if (
            extension == ".pptx"
            or mime_type
            == (
                "application/vnd.openxmlformats-"
                "officedocument.presentationml."
                "presentation"
            )
        ):
            return pptx_parser

        if (
            extension
            in self.TEXT_EXTENSIONS

            or extension
            in self.CODE_EXTENSIONS

            or mime_type
            in self.TEXT_MIME_TYPES

            or mime_type.startswith(
                "text/"
            )
        ):
            return text_parser

        raise UnsupportedFileTypeError(
            f"Unsupported file type: "
            f"{extension or 'unknown'} "
            f"({mime_type or 'unknown MIME type'})"
        )


parser_factory = ParserFactory()