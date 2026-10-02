import argparse

from src.services.rag_service import (
    rag_service,
)


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "question",
        nargs="+",
    )

    parser.add_argument(
        "--provider",
        choices=[
            "gemini",
            "groq",
        ],
        default=None,
    )

    parser.add_argument(
        "--model",
        default=None,
    )

    args = parser.parse_args()

    question = " ".join(
        args.question
    ).strip()

    print()
    print("=" * 80)
    print(
        "RAG CHAT TEST"
    )
    print("=" * 80)

    print(
        f"Question : {question}"
    )

    print(
        f"Provider : "
        f"{args.provider or 'default'}"
    )

    print(
        f"Model    : "
        f"{args.model or 'default'}"
    )

    result = (
        rag_service.ask(
            question=question,
            llm_provider=(
                args.provider
            ),
            llm_model=(
                args.model
            ),
        )
    )

    print()
    print("=" * 80)
    print(
        "ANSWER"
    )
    print("=" * 80)
    print()

    print(
        result.answer
    )

    print()
    print("=" * 80)
    print(
        "SOURCES"
    )
    print("=" * 80)

    for source in result.sources:

        print()

        print(
            f"[{source.citation}] "
            f"{source.source_name}"
        )

        print(
            f"  Document: "
            f"{source.document_title}"
        )

        print(
            f"  Chunk: "
            f"{source.chunk_index}"
        )

        print(
            f"  Vector score: "
            f"{source.vector_score:.4f}"
        )

        if (
            source.rerank_score
            is not None
        ):
            print(
                f"  Rerank score: "
                f"{source.rerank_score:.4f}"
            )

        if source.reference:

            print(
                f"  Reference: "
                f"{source.reference}"
            )

    print()
    print("=" * 80)
    print(
        "TIMING"
    )
    print("=" * 80)

    print(
        f"Retrieval  : "
        f"{result.retrieval_seconds:.3f}s"
    )

    print(
        f"Reranking  : "
        f"{result.rerank_seconds:.3f}s"
    )

    print(
        f"Generation : "
        f"{result.generation_seconds:.3f}s"
    )

    print(
        f"Total      : "
        f"{result.total_seconds:.3f}s"
    )

    print()

    print(
        f"LLM: "
        f"{result.provider} / "
        f"{result.model}"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()