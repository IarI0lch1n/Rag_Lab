from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GrabbedDocument:
    name: str
    content: bytes

    mime_type: str | None = None
    file_extension: str | None = None
    external_id: str | None = None

    metadata: dict = field(
        default_factory=dict
    )


class BaseGrabber(ABC):
    @abstractmethod
    def grab(
        self,
        source,
    ) -> list[GrabbedDocument]:
        raise NotImplementedError