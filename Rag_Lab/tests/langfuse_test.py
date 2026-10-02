from src.observability.langfuse_service import (
    langfuse_service,
)


def main() -> None:

    print()
    print(
        "=" * 80
    )

    print(
        "LANGFUSE API TEST"
    )

    print(
        "=" * 80
    )

    success, message = (
        langfuse_service
        .test_connection()
    )

    print(
        (
            "Connection: "
            f"{'OK' if success else 'FAILED'}"
        )
    )

    print(
        message
    )

    if not success:

        raise SystemExit(
            1
        )

    print()
    print(
        "Sending test trace..."
    )

    with (
        langfuse_service
        .trace(
            name=(
                "advisor-langfuse-smoke-test"
            ),
            input_data={
                "question": (
                    "Langfuse "
                    "integration test"
                ),
            },
            session_id=(
                "advisor-smoke-test"
            ),
            metadata={
                "test": True,
            },
            tags=[
                "advisor",
                "smoke-test",
            ],
        )
    ) as trace:

        with (
            langfuse_service
            .observation(
                name=(
                    "test-retrieval"
                ),
                as_type=(
                    "retriever"
                ),
                input_data={
                    "query": (
                        "Frostpunk"
                    ),
                },
            )
        ) as observation:

            observation.update(
                output={
                    "candidate_count": 2,
                    "documents": [
                        "New London",
                        "Winterhome",
                    ],
                }
            )

        with (
            langfuse_service
            .observation(
                name=(
                    "test-generation"
                ),
                as_type=(
                    "generation"
                ),
                input_data={
                    "prompt": (
                        "Test generation"
                    ),
                },
                model=(
                    "smoke-test-model"
                ),
            )
        ) as generation:

            generation.update(
                output=(
                    "Langfuse tracing works."
                )
            )

        trace.update(
            output={
                "status": "ok",
            }
        )

        trace_id = (
            trace.trace_id
        )

    langfuse_service.flush()

    print()
    print(
        "Trace sent successfully."
    )

    if trace_id:

        print(
            (
                f"Trace ID: "
                f"{trace_id}"
            )
        )

    print(
        (
            "Open the Langfuse project "
            "and check the "
            "Traces/Observations view."
        )
    )

    print(
        "=" * 80
    )


if __name__ == "__main__":

    main()