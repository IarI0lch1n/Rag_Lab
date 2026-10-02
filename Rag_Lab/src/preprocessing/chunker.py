from dataclasses import dataclass

from src.config import settings


@dataclass
class TextChunk:
    index: int
    content: str


class TextChunker:
    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self.default_chunk_size = (
            chunk_size
            or settings.chunk_size
        )

        self.default_chunk_overlap = (
            chunk_overlap
            if chunk_overlap is not None
            else settings.chunk_overlap
        )

    def split(
        self,
        text: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> list[TextChunk]:

        chunk_size = (
            chunk_size
            or self.default_chunk_size
        )

        chunk_overlap = (
            chunk_overlap
            if chunk_overlap is not None
            else self.default_chunk_overlap
        )

        if chunk_size <= 0:
            raise ValueError(
                "chunk_size must be greater than 0."
            )

        if chunk_overlap < 0:
            raise ValueError(
                "chunk_overlap cannot be negative."
            )

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

        text = text.strip()

        if not text:
            return []

        if len(text) <= chunk_size:
            return [
                TextChunk(
                    index=0,
                    content=text,
                )
            ]

        chunks = []

        start = 0
        index = 0

        while start < len(text):
            desired_end = min(
                start + chunk_size,
                len(text),
            )

            end = desired_end

            if desired_end < len(text):
                end = self._find_good_boundary(
                    text=text,
                    start=start,
                    desired_end=desired_end,
                )

            chunk_text = (
                text[start:end]
                .strip()
            )

            if chunk_text:
                chunks.append(
                    TextChunk(
                        index=index,
                        content=chunk_text,
                    )
                )

                index += 1

            if end >= len(text):
                break

            next_start = (
                end
                - chunk_overlap
            )

            if next_start <= start:
                next_start = end

            start = next_start

        return chunks

    @staticmethod
    def _find_good_boundary(
        text: str,
        start: int,
        desired_end: int,
    ) -> int:

        minimum_boundary = (
            start
            + int(
                (
                    desired_end
                    - start
                )
                * 0.65
            )
        )

        candidates = [
            "\n\n",
            "\n",
            ". ",
            "! ",
            "? ",
            "; ",
            ", ",
            " ",
        ]

        for separator in candidates:
            position = text.rfind(
                separator,
                minimum_boundary,
                desired_end,
            )

            if position != -1:
                return (
                    position
                    + len(separator)
                )

        return desired_end


text_chunker = TextChunker()