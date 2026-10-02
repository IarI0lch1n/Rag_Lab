import json
import logging

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    select,
)

from src.db.models import (
    ChatMessage,
    ChatSession,
)

from src.db.session import (
    SessionLocal,
)


logger = logging.getLogger(
    __name__
)


class ChatSessionNotFoundError(
    ValueError
):
    pass


class ChatRepository:

    VALID_ROLES = {
        "user",
        "assistant",
    }

    DEFAULT_TITLE = (
        "New consultation"
    )

    TITLE_MAX_LENGTH = 120

    def create_session(
        self,
        title: str | None = None,
    ) -> ChatSession:

        normalized_title = (
            self._normalize_title(
                title
            )
        )

        try:

            with SessionLocal() as db:

                session = ChatSession(
                    title=normalized_title,
                )

                db.add(
                    session
                )

                db.commit()

                db.refresh(
                    session
                )

                logger.info(
                    (
                        "Chat session created | "
                        "session_id=%s | "
                        "title=%s"
                    ),
                    session.id,
                    session.title,
                )

                return session

        except Exception:

            logger.exception(
                (
                    "Failed to create "
                    "chat session | "
                    "title=%s"
                ),
                normalized_title,
            )

            raise

    def get_session(
        self,
        session_id: int,
    ) -> ChatSession | None:

        with SessionLocal() as db:

            return db.get(
                ChatSession,
                session_id,
            )

    def get_latest_session(
        self,
    ) -> ChatSession | None:

        try:

            with SessionLocal() as db:

                statement = (
                    select(
                        ChatSession
                    )
                    .order_by(
                        ChatSession
                        .updated_at
                        .desc(),
                        ChatSession
                        .id
                        .desc(),
                    )
                    .limit(1)
                )

                session = (
                    db.scalars(
                        statement
                    )
                    .first()
                )

                if session:

                    logger.info(
                        (
                            "Latest chat "
                            "session loaded | "
                            "session_id=%s"
                        ),
                        session.id,
                    )

                return session

        except Exception:

            logger.exception(
                "Failed to load latest "
                "chat session."
            )

            raise

    def list_sessions(
        self,
        limit: int = 50,
    ) -> list[ChatSession]:

        limit = max(
            1,
            min(
                int(limit),
                200,
            ),
        )

        with SessionLocal() as db:

            statement = (
                select(
                    ChatSession
                )
                .order_by(
                    ChatSession
                    .updated_at
                    .desc(),
                    ChatSession
                    .id
                    .desc(),
                )
                .limit(
                    limit
                )
            )

            return list(
                db.scalars(
                    statement
                ).all()
            )

    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        metadata: (
            dict
            | list
            | None
        ) = None,
    ) -> ChatMessage:

        role = (
            role
            .strip()
            .lower()
        )

        if (
            role
            not in self.VALID_ROLES
        ):

            raise ValueError(
                (
                    "Unsupported "
                    "chat role: "
                    f"{role}"
                )
            )

        content = (
            content
            or ""
        ).strip()

        if not content:

            raise ValueError(
                (
                    "Chat message content "
                    "cannot be empty."
                )
            )

        citations_json = (
            self._serialize_metadata(
                metadata
            )
        )

        try:

            with SessionLocal() as db:

                session = db.get(
                    ChatSession,
                    session_id,
                )

                if session is None:

                    raise (
                        ChatSessionNotFoundError(
                            (
                                "Chat session "
                                f"{session_id} "
                                "was not found."
                            )
                        )
                    )

                message = (
                    ChatMessage(
                        session_id=(
                            session_id
                        ),
                        role=role,
                        content=content,
                        citations_json=(
                            citations_json
                        ),
                    )
                )

                db.add(
                    message
                )

                session.updated_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

                db.commit()

                db.refresh(
                    message
                )

                logger.info(
                    (
                        "Chat message saved | "
                        "session_id=%s | "
                        "message_id=%s | "
                        "role=%s | "
                        "chars=%s"
                    ),
                    session_id,
                    message.id,
                    role,
                    len(content),
                )

                return message

        except Exception:

            logger.exception(
                (
                    "Failed to save "
                    "chat message | "
                    "session_id=%s | "
                    "role=%s"
                ),
                session_id,
                role,
            )

            raise

    def get_messages(
        self,
        session_id: int,
        limit: int | None = None,
    ) -> list[ChatMessage]:

        with SessionLocal() as db:

            statement = (
                select(
                    ChatMessage
                )
                .where(
                    ChatMessage
                    .session_id
                    == session_id
                )
            )

            if limit is None:

                statement = (
                    statement
                    .order_by(
                        ChatMessage
                        .id
                        .asc()
                    )
                )

                messages = list(
                    db.scalars(
                        statement
                    ).all()
                )

            else:

                limit = max(
                    1,
                    int(limit),
                )

                statement = (
                    statement
                    .order_by(
                        ChatMessage
                        .id
                        .desc()
                    )
                    .limit(
                        limit
                    )
                )

                messages = list(
                    db.scalars(
                        statement
                    ).all()
                )

                messages.reverse()

            logger.info(
                (
                    "Chat messages loaded | "
                    "session_id=%s | "
                    "count=%s"
                ),
                session_id,
                len(messages),
            )

            return messages

    def get_history(
        self,
        session_id: int,
        limit: int = 10,
    ) -> list[
        dict[str, str]
    ]:

        messages = (
            self.get_messages(
                session_id=(
                    session_id
                ),
                limit=limit,
            )
        )

        history = []

        for message in messages:

            if (
                message.role
                not in self.VALID_ROLES
            ):
                continue

            history.append(
                {
                    "role": (
                        message.role
                    ),
                    "content": (
                        message.content
                    ),
                }
            )

        return history

    def delete_session(
        self,
        session_id: int,
    ) -> bool:

        with SessionLocal() as db:

            session = db.get(
                ChatSession,
                session_id,
            )

            if session is None:
                return False

            db.delete(
                session
            )

            db.commit()

            logger.info(
                (
                    "Chat session deleted | "
                    "session_id=%s"
                ),
                session_id,
            )

            return True

    def build_title(
        self,
        text: str,
    ) -> str:

        text = (
            " ".join(
                (
                    text
                    or ""
                ).split()
            )
        )

        if not text:

            return (
                self.DEFAULT_TITLE
            )

        if (
            len(text)
            <= self.TITLE_MAX_LENGTH
        ):

            return text

        return (
            text[
                :(
                    self
                    .TITLE_MAX_LENGTH
                    - 1
                )
            ]
            .rstrip()
            + "…"
        )

    @staticmethod
    def decode_metadata(
        message: ChatMessage,
    ) -> dict:

        raw = (
            message
            .citations_json
        )

        if not raw:
            return {}

        try:

            data = json.loads(
                raw
            )

        except (
            TypeError,
            json.JSONDecodeError,
        ):

            logger.warning(
                (
                    "Invalid chat message "
                    "metadata JSON | "
                    "message_id=%s"
                ),
                message.id,
            )

            return {}

        if isinstance(
            data,
            dict,
        ):

            return data

        if isinstance(
            data,
            list,
        ):

            return {
                "citations": data,
            }

        return {}

    def _normalize_title(
        self,
        title: str | None,
    ) -> str:

        title = (
            " ".join(
                (
                    title
                    or self.DEFAULT_TITLE
                ).split()
            )
        )

        if not title:

            title = (
                self.DEFAULT_TITLE
            )

        return (
            title[
                :self
                .TITLE_MAX_LENGTH
            ]
        )

    @staticmethod
    def _serialize_metadata(
        metadata: (
            dict
            | list
            | None
        ),
    ) -> str | None:

        if metadata is None:
            return None

        return json.dumps(
            metadata,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )


chat_repository = (
    ChatRepository()
)