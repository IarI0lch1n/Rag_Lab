from src.db.models import Source
from src.grabber.base import (
    BaseGrabber,
    GrabbedDocument,
)


class FileGrabber(BaseGrabber):
    def grab(
        self,
        source: Source,
    ) -> list[GrabbedDocument]:

        if source.source_type != "file":
            raise ValueError(
                f"FileGrabber cannot process "
                f"source type '{source.source_type}'."
            )

        if not source.file_data:
            raise ValueError(
                f"Source {source.id} does not contain file data."
            )

        filename = (
            source.original_filename
            or source.name
            or f"source_{source.id}"
        )

        return [
            GrabbedDocument(
                name=filename,
                content=source.file_data,
                mime_type=source.mime_type,
                file_extension=source.file_extension,
                external_id=filename,
            )
        ]


file_grabber = FileGrabber()