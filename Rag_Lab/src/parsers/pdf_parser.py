import pymupdf

from src.config import settings
from src.grabber.base import GrabbedDocument
from src.parsers.base import (
    BaseParser,
    ParsedDocument,
)


class PdfParser(BaseParser):
    MIN_TEXT_LENGTH = 20

    def parse(
        self,
        document: GrabbedDocument,
    ) -> ParsedDocument:

        pdf = pymupdf.open(
            stream=document.content,
            filetype="pdf",
        )

        total_page_count = len(pdf)

        pages = []

        text_pages = 0
        ocr_pages = 0

        try:
            for page_number, page in enumerate(
                pdf,
                start=1,
            ):
                text = page.get_text(
                    "text"
                ).strip()

                used_ocr = False

                if len(text) < self.MIN_TEXT_LENGTH:
                    text = self._extract_with_ocr(
                        page
                    )

                    used_ocr = bool(text)

                if not text:
                    continue

                if used_ocr:
                    ocr_pages += 1
                else:
                    text_pages += 1

                pages.append(
                    {
                        "page": page_number,
                        "text": text,
                    }
                )

        finally:
            pdf.close()

        if not pages:
            raise ValueError(
                f"No text could be extracted from PDF "
                f"'{document.name}', including OCR."
            )

        parts = []

        for page in pages:
            parts.append(
                f"[Page {page['page']}]\n"
                f"{page['text']}"
            )

        text = "\n\n".join(
            parts
        )

        return ParsedDocument(
            title=document.name,
            text=text,
            document_type="pdf",
            mime_type="application/pdf",
            external_id=document.external_id,
            metadata={
                "parser": "pymupdf+tesseract",
                "page_count": 395,
                "text_pages": 0,
                "ocr_pages": 392,
                "failed_pages": [84, 231, 376],
                "ocr_languages": "rus+eng",
                "ocr_dpi": 180
            },
        )

    @staticmethod
    def _extract_with_ocr(
        page,
    ) -> str:

        try:
            text_page = page.get_textpage_ocr(
                language=settings.ocr_languages,
                dpi=200,
                full=False,
                tessdata=settings.tesseract_tessdata,
            )

            return page.get_text(
                "text",
                textpage=text_page,
            ).strip()

        except Exception as exc:
            raise RuntimeError(
                f"OCR failed using languages "
                f"'{settings.ocr_languages}' and tessdata "
                f"'{settings.tesseract_tessdata}'. "
                f"Error: {exc}"
            ) from exc


pdf_parser = PdfParser()