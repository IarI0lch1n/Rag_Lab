from pathlib import Path

from src.services.source_service import (
    DuplicateSourceError,
    SourceService,
)


def print_source(source) -> None:
    print(
        f"ID={source.id} | "
        f"type={source.source_type} | "
        f"name={source.name} | "
        f"status={source.status}"
    )


def main() -> None:
    service = SourceService()

    created_source_ids = []

    print()
    print("=" * 70)
    print("Source Service Smoke Test")
    print("=" * 70)

    try:
        print()
        print("1. Adding web source...")

        web_source = service.add_url_source(
            "https://docs.python.org/3/"
        )

        created_source_ids.append(
            web_source.id
        )

        print("[OK]")
        print_source(web_source)

        print()
        print("2. Adding Git source...")

        git_source = service.add_url_source(
            "https://github.com/Randwow/PAD"
        )

        created_source_ids.append(
            git_source.id
        )

        print("[OK]")
        print_source(git_source)

        print()
        print("3. Testing URL duplicate detection...")

        try:
            service.add_url_source(
                "https://github.com/Randwow/PAD/"
            )

            print(
                "[ERROR] Duplicate was not detected."
            )

        except DuplicateSourceError as exc:
            print(
                f"[OK] Duplicate detected: {exc}"
            )

        print()
        print("4. Creating test text file...")

        test_file = Path(
            "data/temp/source_test.txt"
        )

        test_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        test_file.write_text(
            (
                "This is a test document.\n"
                "It will later be processed by "
                "the RAG ingestion pipeline."
            ),
            encoding="utf-8",
        )

        file_source = service.add_file_source(
            test_file
        )

        created_source_ids.append(
            file_source.id
        )

        print("[OK]")
        print_source(file_source)

        print(
            f"MIME: {file_source.mime_type}"
        )

        print(
            f"Extension: "
            f"{file_source.file_extension}"
        )

        print(
            f"Size: "
            f"{file_source.file_size_bytes} bytes"
        )

        print(
            f"SHA256: "
            f"{file_source.content_hash}"
        )

        print()
        print("5. Testing file duplicate detection...")

        try:
            service.add_file_source(
                test_file
            )

            print(
                "[ERROR] Duplicate file "
                "was not detected."
            )

        except DuplicateSourceError as exc:
            print(
                f"[OK] Duplicate detected: {exc}"
            )

        print()
        print("6. Listing sources...")

        sources = service.get_sources()

        for source in sources:
            print_source(source)

    finally:
        print()
        print("Cleaning test data...")

        for source_id in created_source_ids:
            try:
                service.delete_source(
                    source_id
                )

                print(
                    f"[OK] Deleted source "
                    f"{source_id}"
                )

            except Exception as exc:
                print(
                    f"[WARNING] Could not delete "
                    f"source {source_id}: {exc}"
                )

        test_file = Path(
            "data/temp/source_test.txt"
        )

        if test_file.exists():
            test_file.unlink()

    print()
    print("=" * 70)
    print("Smoke test completed.")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()