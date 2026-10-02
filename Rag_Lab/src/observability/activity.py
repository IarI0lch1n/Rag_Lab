import io
import logging
import sys
import threading

from collections import deque
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ActivityEntry:
    id: int
    created_at: datetime
    level: str
    category: str
    message: str


class ActivityStore:

    MAX_ENTRIES = 500

    def __init__(self) -> None:
        self._entries = deque(
            maxlen=self.MAX_ENTRIES
        )

        self._lock = threading.Lock()

        self._counter = 0

    def add(
        self,
        message: str,
        level: str = "INFO",
        category: str = "SYSTEM",
    ) -> None:

        message = (
            message
            or ""
        ).strip()

        if not message:
            return

        with self._lock:

            self._counter += 1

            self._entries.append(
                ActivityEntry(
                    id=self._counter,
                    created_at=datetime.now(),
                    level=level.upper(),
                    category=category.upper(),
                    message=message,
                )
            )

    def recent(
        self,
        limit: int = 80,
    ) -> list[ActivityEntry]:

        with self._lock:

            items = list(
                self._entries
            )

        return items[-limit:]

    def clear(self) -> None:

        with self._lock:
            self._entries.clear()


activity_store = ActivityStore()


def detect_category(
    logger_name: str,
    message: str,
) -> str:

    value = (
        f"{logger_name} "
        f"{message}"
    ).lower()

    if (
        "internet"
        in value
        or "[web]"
        in value
        or "[fandom]"
        in value
    ):
        return "RECON"

    if (
        "index"
        in value
        or "vector"
        in value
        or "chunk"
        in value
    ):
        return "ARCHIVE"

    if (
        "embed"
        in value
    ):
        return "EMBEDDING"

    if (
        "retriev"
        in value
    ):
        return "SEARCH"

    if (
        "rerank"
        in value
    ):
        return "ANALYSIS"

    if (
        "[llm]"
        in value
        or "generation"
        in value
        or "gemini"
        in value
        or "groq"
        in value
    ):
        return "CORE"

    if (
        "chat"
        in value
        or "advisor request"
        in value
        or "consultation"
        in value
    ):
        return "CONSULTATION"

    if (
        "sql"
        in value
        or "database"
        in value
        or "persist"
        in value
    ):
        return "DATABASE"

    return "SYSTEM"


class ActivityLogHandler(
    logging.Handler
):

    def emit(
        self,
        record: logging.LogRecord,
    ) -> None:

        try:

            #
            # Only display application logs
            # in the Advisor UI.
            #
            if not (
                record.name.startswith(
                    "src."
                )
                or
                record.name.startswith(
                    "advisor."
                )
            ):
                return

            message = (
                record.getMessage()
            )

            for line in message.splitlines():

                if not line.strip():
                    continue

                activity_store.add(
                    message=line,
                    level=(
                        record.levelname
                    ),
                    category=(
                        detect_category(
                            record.name,
                            line,
                        )
                    ),
                )

        except Exception:
            pass


SYSTEM_PRINT_PREFIXES = (
    "[Indexing]",
    "[Vectorization]",
    "[Embeddings]",
    "[Retriever]",
    "[Reranker]",
    "[LLM]",
    "[Web]",
    "[Fandom]",
    "[Git]",
    "[OCR]",
)


class ConsoleMirror:

    def __init__(
        self,
        original,
    ) -> None:

        self.original = original

        self._buffer = ""

        self._lock = threading.Lock()

        self._advisor_mirror = True

    def write(
        self,
        text: str,
    ):

        result = self.original.write(
            text
        )

        self.original.flush()

        with self._lock:

            self._buffer += text

            while "\n" in self._buffer:

                line, self._buffer = (
                    self._buffer.split(
                        "\n",
                        1,
                    )
                )

                line = line.strip()

                if not line:
                    continue

                if line.startswith(
                    SYSTEM_PRINT_PREFIXES
                ):

                    activity_store.add(
                        message=line,
                        level="INFO",
                        category=(
                            detect_category(
                                "console",
                                line,
                            )
                        ),
                    )

        return result

    def flush(self) -> None:
        self.original.flush()

    def __getattr__(
        self,
        name,
    ):
        return getattr(
            self.original,
            name,
        )


def install_console_mirror() -> None:

    if not getattr(
        sys.stdout,
        "_advisor_mirror",
        False,
    ):
        sys.stdout = ConsoleMirror(
            sys.stdout
        )

    if not getattr(
        sys.stderr,
        "_advisor_mirror",
        False,
    ):
        sys.stderr = ConsoleMirror(
            sys.stderr
        )