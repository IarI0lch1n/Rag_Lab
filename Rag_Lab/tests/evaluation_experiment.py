import json

from datetime import (
    datetime,
)

from pathlib import Path

from src.evaluation.evaluator import (
    rag_evaluator,
)


DATASET_PATH = (
    Path("data")
    / "evaluation_questions.json"
)

EXPERIMENTS_DIRECTORY = (
    Path("experiments")
)


def main() -> None:

    print()
    print(
        "=" * 80
    )

    print(
        "RAG RETRIEVAL EVALUATION"
    )

    print(
        "=" * 80
    )

    cases = (
        rag_evaluator
        .load_dataset(
            DATASET_PATH
        )
    )

    labeled = [
        case
        for case in cases
        if (
            case.labeled
            and case.answerable
            and case
            .relevant_document_ids
        )
    ]

    print(
        f"Dataset cases : "
        f"{len(cases)}"
    )

    print(
        f"Labeled cases : "
        f"{len(labeled)}"
    )

    if not labeled:

        print()
        print(
            (
                "No labeled cases yet. "
                "Run:"
            )
        )

        print(
            (
                "python -m "
                "tests.build_evaluation_dataset"
            )
        )

        return

    timestamp = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    session_id = (
        f"evaluation-{timestamp}"
    )

    (
        results,
        summary,
    ) = (
        rag_evaluator
        .evaluate_dataset(
            cases,
            k_values=[
                3,
                5,
                10,
                20,
            ],
            langfuse_session_id=(
                session_id
            ),
        )
    )

    print()
    print(
        "=" * 80
    )

    print(
        "SUMMARY"
    )

    print(
        "=" * 80
    )

    for k in (
        summary.k_values
    ):

        baseline = (
            summary
            .baseline[
                k
            ]
        )

        reranked = (
            summary
            .reranked[
                k
            ]
        )

        print()
        print(
            f"TOP-{k}"
        )

        print(
            (
                "Vector   "
                f"| Hit Rate "
                f"{baseline['hit_rate']:.3f} "
                f"| Recall "
                f"{baseline['recall']:.3f} "
                f"| MRR "
                f"{baseline['mrr']:.3f}"
            )
        )

        print(
            (
                "Reranker "
                f"| Hit Rate "
                f"{reranked['hit_rate']:.3f} "
                f"| Recall "
                f"{reranked['recall']:.3f} "
                f"| MRR "
                f"{reranked['mrr']:.3f}"
            )
        )

    print()

    print(
        (
            "Average retrieval: "
            f"{summary.average_retrieval_seconds:.3f}s"
        )
    )

    print(
        (
            "Average rerank: "
            f"{summary.average_rerank_seconds:.3f}s"
        )
    )

    EXPERIMENTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        EXPERIMENTS_DIRECTORY
        / (
            "retrieval_evaluation_"
            f"{timestamp}.json"
        )
    )

    payload = {
        "created_at": (
            timestamp
        ),

        "langfuse_session_id": (
            session_id
        ),

        "summary": (
            summary.to_dict()
        ),

        "cases": [
            result.to_dict()
            for result in results
        ],
    }

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        (
            "Saved experiment: "
            f"{output_path}"
        )
    )

    print(
        (
            "Langfuse session: "
            f"{session_id}"
        )
    )


if __name__ == "__main__":
    main()