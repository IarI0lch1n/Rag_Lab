import time

from src.generation.llm import (
    llm,
)


def main() -> None:

    print()
    print("=" * 80)
    print(
        "LLM SMOKE TEST"
    )
    print("=" * 80)

    question = input(
        "Question: "
    ).strip()

    if not question:
        return

    started = (
        time.perf_counter()
    )

    response = (
        llm.generate(
            system_prompt=(
                "You are a concise helpful "
                "assistant. Answer in the same "
                "language as the user."
            ),
            user_prompt=(
                question
            ),
        )
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print()
    print(
        f"Provider: "
        f"{response.provider}"
    )

    print(
        f"Model: "
        f"{response.model}"
    )

    print(
        f"Time: "
        f"{elapsed:.3f} sec"
    )

    print()
    print(
        "ANSWER:"
    )

    print(
        response.text
    )

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()