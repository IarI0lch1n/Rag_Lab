import re

from src.preprocessing.chunker import (
    TextChunk,
    text_chunker,
)


class DocumentChunker:
    VERSION = "2"

    STRUCTURE_PATTERN = re.compile(
        r"(?m)^\[(Page|Slide)\s+\d+\]\s*$"
    )

    MAX_PARAGRAPHS_PER_CHUNK = 8

    def split(
        self,
        text: str,
        source_type: str,
        document_type: str | None,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[TextChunk]:

        text = (
            text
            or ""
        ).strip()

        if not text:
            return []

        #
        # Web and Git:
        # every page/file is already its own
        # Document, so normal chunking is fine.
        #
        if source_type != "file":
            return text_chunker.split(
                text,
                chunk_size=(
                    chunk_size
                ),
                chunk_overlap=(
                    chunk_overlap
                ),
            )

        document_type = (
            document_type
            or ""
        ).lower()

        #
        # PDF / PPTX:
        # preserve pages/slides as meaningful
        # boundaries.
        #
        if (
            document_type
            in {
                "pdf",
                "ppt",
                "pptx",
                "presentation",
            }
            or self.STRUCTURE_PATTERN.search(
                text
            )
        ):
            sections = (
                self._split_structural_sections(
                    text
                )
            )

            if len(sections) > 1:
                return (
                    self._split_sections(
                        sections=sections,
                        chunk_size=(
                            chunk_size
                        ),
                        chunk_overlap=(
                            chunk_overlap
                        ),
                    )
                )

        #
        # DOCX / TXT / MD / other files:
        # paragraph-aware chunking.
        #
        return (
            self._split_paragraphs(
                text=text,
                chunk_size=(
                    chunk_size
                ),
                chunk_overlap=(
                    chunk_overlap
                ),
            )
        )

    def _split_structural_sections(
        self,
        text: str,
    ) -> list[str]:

        matches = list(
            self.STRUCTURE_PATTERN
            .finditer(
                text
            )
        )

        if not matches:
            return [
                text
            ]

        sections = []

        #
        # Text before the first marker.
        #
        prefix = (
            text[
                :matches[0].start()
            ]
            .strip()
        )

        if prefix:
            sections.append(
                prefix
            )

        for index, match in enumerate(
            matches
        ):
            start = (
                match.start()
            )

            if (
                index + 1
                < len(matches)
            ):
                end = (
                    matches[
                        index + 1
                    ].start()
                )

            else:
                end = len(
                    text
                )

            section = (
                text[
                    start:end
                ]
                .strip()
            )

            if section:
                sections.append(
                    section
                )

        return sections

    def _split_sections(
        self,
        sections: list[str],
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[TextChunk]:

        chunks = []

        next_index = 0

        for section in sections:

            #
            # One page/slide already fits:
            # keep it intact.
            #
            if (
                len(section)
                <= chunk_size
            ):
                chunks.append(
                    TextChunk(
                        index=(
                            next_index
                        ),
                        content=(
                            section
                        ),
                    )
                )

                next_index += 1

                continue

            #
            # Long page/slide:
            # split inside this structural unit.
            #
            section_chunks = (
                text_chunker.split(
                    section,
                    chunk_size=(
                        chunk_size
                    ),
                    chunk_overlap=(
                        chunk_overlap
                    ),
                )
            )

            for section_chunk in (
                section_chunks
            ):
                chunks.append(
                    TextChunk(
                        index=(
                            next_index
                        ),
                        content=(
                            section_chunk
                            .content
                        ),
                    )
                )

                next_index += 1

        return chunks

    def _split_paragraphs(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[TextChunk]:

        paragraphs = (
            self._extract_paragraphs(
                text
            )
        )

        if not paragraphs:
            return []

        if len(paragraphs) == 1:
            return text_chunker.split(
                paragraphs[0],
                chunk_size=(
                    chunk_size
                ),
                chunk_overlap=(
                    chunk_overlap
                ),
            )

        chunks = []

        current_paragraphs = []

        current_length = 0

        for paragraph in paragraphs:

            paragraph_length = len(
                paragraph
            )

            #
            # A single giant paragraph.
            #
            if paragraph_length > chunk_size:

                if current_paragraphs:
                    chunks.append(
                        "\n\n".join(
                            current_paragraphs
                        )
                    )

                    current_paragraphs = []
                    current_length = 0

                sub_chunks = (
                    text_chunker.split(
                        paragraph,
                        chunk_size=(
                            chunk_size
                        ),
                        chunk_overlap=(
                            chunk_overlap
                        ),
                    )
                )

                for sub_chunk in (
                    sub_chunks
                ):
                    chunks.append(
                        sub_chunk.content
                    )

                continue

            projected_length = (
                current_length
                + paragraph_length
                + (
                    2
                    if current_paragraphs
                    else 0
                )
            )

            too_large = (
                projected_length
                > chunk_size
            )

            too_many_paragraphs = (
                len(
                    current_paragraphs
                )
                >= self
                .MAX_PARAGRAPHS_PER_CHUNK
            )

            if (
                current_paragraphs
                and (
                    too_large
                    or
                    too_many_paragraphs
                )
            ):
                chunks.append(
                    "\n\n".join(
                        current_paragraphs
                    )
                )

                current_paragraphs = (
                    self
                    ._get_overlap_paragraphs(
                        current_paragraphs,
                        chunk_overlap,
                    )
                )

                current_length = len(
                    "\n\n".join(
                        current_paragraphs
                    )
                )

            current_paragraphs.append(
                paragraph
            )

            current_length = len(
                "\n\n".join(
                    current_paragraphs
                )
            )

        if current_paragraphs:
            chunks.append(
                "\n\n".join(
                    current_paragraphs
                )
            )

        return [
            TextChunk(
                index=index,
                content=content.strip(),
            )
            for index, content
            in enumerate(
                chunks
            )
            if content.strip()
        ]

    @staticmethod
    def _extract_paragraphs(
        text: str,
    ) -> list[str]:

        #
        # Prefer real blank-line paragraphs.
        #
        paragraphs = [
            paragraph.strip()
            for paragraph
            in re.split(
                r"\n\s*\n+",
                text,
            )
            if paragraph.strip()
        ]

        if len(paragraphs) > 1:
            return paragraphs

        #
        # DOCX parser can produce one
        # paragraph per line without blank lines.
        #
        lines = [
            line.strip()
            for line
            in text.splitlines()
            if line.strip()
        ]

        if len(lines) > 1:
            return lines

        return [
            text.strip()
        ]

    @staticmethod
    def _get_overlap_paragraphs(
        paragraphs: list[str],
        overlap_size: int,
    ) -> list[str]:

        if (
            overlap_size <= 0
            or not paragraphs
        ):
            return []

        selected = []

        current_size = 0

        for paragraph in reversed(
            paragraphs
        ):
            paragraph_size = len(
                paragraph
            )

            if (
                selected
                and (
                    current_size
                    + paragraph_size
                    > overlap_size
                )
            ):
                break

            selected.append(
                paragraph
            )

            current_size += (
                paragraph_size
            )

            if (
                current_size
                >= overlap_size
            ):
                break

        selected.reverse()

        return selected


document_chunker = (
    DocumentChunker()
)