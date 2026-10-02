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
        "AUTOMATIC WEB RECON TEST"
    )
    print("=" * 80)

    report = (
        auto_research_service
        .research(
            question
        )
    )

    print(
        f"Query: {report.query}"
    )

    print(
        f"Hits: {report.hits_found}"
    )

    print(
        f"Indexed: "
        f"{report.indexed_count}"
    )

    print()

    for source in (
        report.sources
    ):

        print(
            f"{source.status.upper()}"
        )

        print(
            source.title
        )

        print(
            source.url
        )

        print(
            f"Source ID: "
            f"{source.source_id}"
        )

        if source.error:

            print(
                f"Error: "
                f"{source.error}"
            )

        print("-" * 80)


if __name__ == "__main__":
    main()