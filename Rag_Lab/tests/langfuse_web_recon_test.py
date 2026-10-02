from src.observability.langfuse_service import (
    langfuse_service,
)

from src.services.auto_research_service import (
    auto_research_service,
)


def main() -> None:

    question = (
        "What happened in "
        "The Arks scenario?"
    )

    print()
    print("=" * 80)
    print(
        "LANGFUSE WEB RECON TEST"
    )
    print("=" * 80)

    with (
        langfuse_service
        .trace(
            name=(
                "advisor-consultation-test"
            ),
            input_data={
                "question": question,
                "web_recon": True,
            },
            session_id=(
                "advisor-test-session"
            ),
            tags=[
                "advisor",
                "test",
            ],
        )
    ) as trace:

        trace_context = (
            trace
            .child_trace_context()
        )

        report = (
            auto_research_service
            .research(
                question,
                trace_context=(
                    trace_context
                ),
            )
        )

        trace.update(
            output={
                "web_recon": (
                    report.to_dict()
                ),
            }
        )

        print(
            f"Trace ID: "
            f"{trace.trace_id}"
        )

    print()
    print(
        f"Hits: "
        f"{report.hits_found}"
    )

    print(
        f"Indexed: "
        f"{report.indexed_count}"
    )

    print(
        f"Duplicates: "
        f"{report.duplicate_count}"
    )

    print()
    print(
        "Check Langfuse Tracing."
    )

    print("=" * 80)


if __name__ == "__main__":
    main()