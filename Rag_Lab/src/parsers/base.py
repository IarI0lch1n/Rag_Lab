from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.grabber.base import GrabbedDocument


@dataclass
class ParsedDocument:
    title: str
    text: str
    document_type: str
    mime_type: str | None
    external_id: str | None
    metadata: dict


class BaseParser(ABC):
    @abstractmethod
    def parse(
        self,
        document: GrabbedDocument,
    ) -> ParsedDocument:
        raise NotImplementedError