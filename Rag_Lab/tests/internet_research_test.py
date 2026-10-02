import argparse

from src.services.internet_research_service import (
    internet_research_service,
)


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "query",
        nargs="+",
    )

    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--import-first",
        type=int,
        default=0,
    )

    args = parser.parse_args()

    query = " ".join(
        args.query
    )

    print()
    print("=" * 80)
    print(
        "THE ADVISOR - INTERNET RECON"
    )
    print("=" * 80)

    print(
        f"Query: {query}"
    )

    results = (
        internet_research_service
        .search(
            query=query,
            max_results=(
                args.max_results
            ),
        )
    )

    for index, hit in enumerate(
        results,
        start=1,
    ):

        print()
        print(
            f"[{index}] {hit.title}"
        )

        print(
            hit.url
        )

        print(
            hit.snippet[:300]
        )

    import_count = min(
        args.import_first,
        len(results),
    )

    for hit in (
        results[:import_count]
    ):

        print()
        print(
            "IMPORTING:"
        )

        print(
            hit.url
        )

        result = (
            internet_research_service
            .import_hit(
                hit
            )
        )

        print(
            result
        )


if __name__ == "__main__":
    main()