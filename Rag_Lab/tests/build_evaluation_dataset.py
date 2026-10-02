import json
from pathlib import Path

from src.retrieval.retriever import (
    retriever,
)


DATASET_PATH = (
    Path("data")
    / "evaluation_questions.json"
)

CANDIDATE_COUNT = 30
QDRANT_LIMIT = 100
MAX_PER_DOCUMENT = 4

MAX_DOCUMENTS_TO_SHOW = 15

PREVIEW_LENGTH = 350


def load_dataset() -> dict:

    if not DATASET_PATH.exists():

        raise FileNotFoundError(
            (
                "Dataset not found: "
                f"{DATASET_PATH}"
            )
        )

    with DATASET_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def save_dataset(
    dataset: dict,
) -> None:

    DATASET_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with DATASET_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            dataset,
            file,
            ensure_ascii=False,
            indent=2,
        )


def unique_documents(
    results,
):

    documents = []

    seen = set()

    for result in results:

        if result.document_id in seen:
            continue

        seen.add(
            result.document_id
        )

        documents.append(
            result
        )

        if (
            len(documents)
            >= MAX_DOCUMENTS_TO_SHOW
        ):
            break

    return documents


def format_reference(
    result,
) -> str:

    if (
        result.source_type
        == "web"
    ):

        return (
            result.external_id
            or result.source_uri
            or ""
        )

    if (
        result.source_type
        == "git"
    ):

        return (
            (
                f"{result.source_uri} -> "
                f"{result.external_id}"
            )
            if result.source_uri
            else (
                result.external_id
                or ""
            )
        )

    return (
        result.document_title
        or result.external_id
        or ""
    )


def print_candidate(
    number: int,
    result,
) -> None:

    print()
    print(
        "-" * 80
    )

    print(
        (
            f"[{number}] "
            f"Document ID: "
            f"{result.document_id}"
        )
    )

    print(
        (
            f"Source      : "
            f"{result.source_name}"
        )
    )

    print(
        (
            f"Document    : "
            f"{result.document_title}"
        )
    )

    print(
        (
            f"Vector score: "
            f"{result.score:.4f}"
        )
    )

    print(
        (
            "Reference   : "
            f"{format_reference(result)}"
        )
    )

    preview = (
        result.text
        or ""
    ).strip()

    print()
    print(
        preview[
            :PREVIEW_LENGTH
        ]
    )

    if (
        len(preview)
        > PREVIEW_LENGTH
    ):

        print(
            "..."
        )


def parse_selection(
    value: str,
    documents,
):

    value = (
        value.strip()
        .lower()
    )

    if not value:

        return None

    if value == "s":

        return "skip"

    if value == "u":

        return "unanswerable"

    if value == "q":

        return "quit"

    #
    # Manual DB IDs:
    #
    # id:123,456
    #

    if value.startswith(
        "id:"
    ):

        raw_ids = (
            value[
                3:
            ]
        )

        result = []

        for part in (
            raw_ids.split(",")
        ):

            part = (
                part.strip()
            )

            if not part:
                continue

            result.append(
                int(part)
            )

        if not result:

            raise ValueError(
                (
                    "No document IDs "
                    "were provided."
                )
            )

        return result

    #
    # Candidate numbers:
    #
    # 1,3,5
    #

    numbers = []

    for part in (
        value.split(",")
    ):

        part = (
            part.strip()
        )

        if not part:
            continue

        number = int(
            part
        )

        if (
            number < 1
            or number
            > len(documents)
        ):

            raise ValueError(
                (
                    "Candidate number "
                    f"{number} is out "
                    "of range."
                )
            )

        numbers.append(
            number
        )

    if not numbers:

        raise ValueError(
            "No documents selected."
        )

    document_ids = []

    for number in numbers:

        document_id = (
            documents[
                number - 1
            ]
            .document_id
        )

        if (
            document_id
            not in document_ids
        ):

            document_ids.append(
                document_id
            )

    return document_ids


def main() -> None:

    dataset = load_dataset()

    cases = (
        dataset.get(
            "cases",
            []
        )
    )

    pending = [
        case
        for case in cases
        if (
            case.get(
                "answerable",
                True,
            )
            and not case.get(
                "labeled",
                False,
            )
        )
    ]

    print()
    print(
        "=" * 80
    )

    print(
        "RAG EVALUATION DATASET BUILDER"
    )

    print(
        "=" * 80
    )

    print()
    print(
        f"Total cases   : "
        f"{len(cases)}"
    )

    print(
        f"Need labeling : "
        f"{len(pending)}"
    )

    print()
    print(
        "Commands:"
    )

    print(
        (
            "  1,3       "
            "select candidate documents"
        )
    )

    print(
        (
            "  id:12,15  "
            "enter document IDs manually"
        )
    )

    print(
        (
            "  s         "
            "skip this question"
        )
    )

    print(
        (
            "  u         "
            "mark question unanswerable"
        )
    )

    print(
        (
            "  q         "
            "save and quit"
        )
    )

    if not pending:

        print()
        print(
            (
                "All answerable cases "
                "are already labeled."
            )
        )

        return

    total = len(
        pending
    )

    for index, case in enumerate(
        pending,
        start=1,
    ):

        question = (
            case[
                "question"
            ]
        )

        print()
        print()
        print(
            "#" * 80
        )

        print(
            (
                f"QUESTION "
                f"{index}/{total}"
            )
        )

        print(
            (
                f"ID       : "
                f"{case['id']}"
            )
        )

        print(
            (
                f"Language : "
                f"{case.get('language')}"
            )
        )

        print()
        print(
            question
        )

        print(
            "#" * 80
        )

        print()
        print(
            "Retrieving candidates..."
        )

        try:

            results = (
                retriever
                .retrieve_candidates(
                    query=question,
                    limit=(
                        CANDIDATE_COUNT
                    ),
                    qdrant_limit=(
                        QDRANT_LIMIT
                    ),
                    max_per_document=(
                        MAX_PER_DOCUMENT
                    ),
                    debug=False,
                )
            )

        except Exception as exc:

            print()
            print(
                (
                    "[ERROR] Retrieval "
                    f"failed: {exc}"
                )
            )

            continue

        documents = (
            unique_documents(
                results
            )
        )

        if not documents:

            print()
            print(
                "No candidate documents."
            )

            case[
                "answerable"
            ] = False

            case[
                "labeled"
            ] = True

            case[
                "notes"
            ] = (
                str(
                    case.get(
                        "notes",
                        "",
                    )
                )
                + " No documents found "
                "during manual labeling."
            ).strip()

            save_dataset(
                dataset
            )

            continue

        for (
            candidate_number,
            result,
        ) in enumerate(
            documents,
            start=1,
        ):

            print_candidate(
                candidate_number,
                result,
            )

        while True:

            print()
            print(
                "-" * 80
            )

            value = input(
                (
                    "Relevant documents "
                    "[1,3 / id:123 / "
                    "s / u / q]: "
                )
            )

            try:

                selection = (
                    parse_selection(
                        value,
                        documents,
                    )
                )

            except (
                ValueError,
                TypeError,
            ) as exc:

                print(
                    (
                        "[ERROR] "
                        f"{exc}"
                    )
                )

                continue

            if selection is None:

                continue

            if (
                selection
                == "quit"
            ):

                save_dataset(
                    dataset
                )

                print()
                print(
                    (
                        "Progress saved to "
                        f"{DATASET_PATH}"
                    )
                )

                return

            if (
                selection
                == "skip"
            ):

                print(
                    (
                        "Skipped. "
                        "Question remains "
                        "unlabeled."
                    )
                )

                break

            if (
                selection
                == "unanswerable"
            ):

                case[
                    "answerable"
                ] = False

                case[
                    "relevant_document_ids"
                ] = []

                case[
                    "labeled"
                ] = True

                save_dataset(
                    dataset
                )

                print(
                    (
                        "Marked as "
                        "unanswerable."
                    )
                )

                break

            #
            # Store actual SQL document IDs.
            #

            case[
                "relevant_document_ids"
            ] = selection

            case[
                "labeled"
            ] = True

            save_dataset(
                dataset
            )

            print()
            print(
                (
                    "Saved relevant IDs: "
                    + ", ".join(
                        str(value)
                        for value
                        in selection
                    )
                )
            )

            break

    print()
    print(
        "=" * 80
    )

    print(
        "LABELING COMPLETED"
    )

    print(
        "=" * 80
    )

    print(
        (
            "Dataset saved: "
            f"{DATASET_PATH}"
        )
    )


if __name__ == "__main__":

    main()