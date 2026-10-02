from src.repositories.chat_repository import (
    chat_repository,
)


def main() -> None:

    print()
    print("=" * 80)
    print(
        "CHAT REPOSITORY TEST"
    )
    print("=" * 80)

    session = (
        chat_repository
        .create_session(
            title=(
                "Frostpunk persistence test"
            )
        )
    )

    print(
        f"Created session: "
        f"{session.id}"
    )

    chat_repository.add_message(
        session_id=(
            session.id
        ),
        role="user",
        content=(
            "Why was New London founded?"
        ),
    )

    chat_repository.add_message(
        session_id=(
            session.id
        ),
        role="assistant",
        content=(
            "This is a persistence test."
        ),
        metadata={
            "version": 1,
            "provider": "test",
            "model": "test-model",
            "citations": [
                {
                    "citation": "S1",
                    "source_name": (
                        "Frostpunk Wiki"
                    ),
                    "document_title": (
                        "New London"
                    ),
                    "chunk_index": 0,
                    "reference": (
                        "https://example.com"
                    ),
                    "vector_score": (
                        0.9
                    ),
                    "rerank_score": (
                        1.2
                    ),
                }
            ],
            "timing": {
                "retrieval": 0.1,
                "rerank": 0.2,
                "generation": 0.3,
                "total": 0.6,
            },
        },
    )

    messages = (
        chat_repository
        .get_messages(
            session.id
        )
    )

    print()
    print(
        f"Messages: "
        f"{len(messages)}"
    )

    for message in messages:

        print()
        print(
            f"{message.role}: "
            f"{message.content}"
        )

        metadata = (
            chat_repository
            .decode_metadata(
                message
            )
        )

        if metadata:

            print(
                f"metadata: "
                f"{metadata}"
            )

    history = (
        chat_repository
        .get_history(
            session.id
        )
    )

    print()
    print(
        "RAG history:"
    )

    print(
        history
    )

    latest = (
        chat_repository
        .get_latest_session()
    )

    print()
    print(
        f"Latest session: "
        f"{latest.id} / "
        f"{latest.title}"
    )

    deleted = (
        chat_repository
        .delete_session(
            session.id
        )
    )

    print()
    print(
        f"Test session deleted: "
        f"{deleted}"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()