import time

from dataclasses import dataclass

from src.generation.llm import (
    llm_manager,
)

from src.generation.prompts import (
    PromptSource,
    SYSTEM_PROMPT,
    build_rag_prompt,
)

from src.reranking.reranker import (
    reranker,
)

from src.retrieval.retriever import (
    RetrievedChunk,
    retriever,
)


@dataclass(frozen=True)
class RagSource:
    citation: str

    source_id: int
    document_id: int
    chunk_id: int

    source_name: str
    source_type: str

    document_title: str
    chunk_index: int

    reference: str | None

    vector_score: float
    rerank_score: float | None


@dataclass(frozen=True)
class RagAnswer:
    answer: str

    sources: list[RagSource]

    provider: str
    model: str

    retrieval_seconds: float
    rerank_seconds: float
    generation_seconds: float
    total_seconds: float


class RagService:

    CANDIDATE_COUNT = 20

    QDRANT_LIMIT = 100

    MAX_PER_DOCUMENT = 4

    FINAL_CONTEXT_COUNT = 5

    MAX_CONTEXT_CHARS = 12000

    def ask(
        self,
        question: str,
        history: list[dict[str, str]] | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> RagAnswer:

        question = question.strip()

        if not question:
            raise ValueError(
                "Question cannot be empty."
            )

        total_started = (
            time.perf_counter()
        )

        print()
        print("=" * 80)

        print(
            f"[RAG] Question: "
            f"{question}"
        )

        if llm_provider:
            print(
                f"[RAG] LLM provider: "
                f"{llm_provider}"
            )

        if llm_model:
            print(
                f"[RAG] LLM model: "
                f"{llm_model}"
            )

        print("=" * 80)

        #
        # 1. Retrieval
        #
        retrieval_started = (
            time.perf_counter()
        )

        candidates = (
            retriever.retrieve_candidates(
                query=question,
                limit=(
                    self.CANDIDATE_COUNT
                ),
                qdrant_limit=(
                    self.QDRANT_LIMIT
                ),
                max_per_document=(
                    self.MAX_PER_DOCUMENT
                ),
                debug=True,
            )
        )

        retrieval_seconds = (
            time.perf_counter()
            - retrieval_started
        )

        print(
            f"[RAG] Retrieval: "
            f"{retrieval_seconds:.3f}s"
        )

        print(
            f"[RAG] Candidates: "
            f"{len(candidates)}"
        )

        #
        # 2. Reranking
        #
        rerank_started = (
            time.perf_counter()
        )

        if candidates:

            reranked = (
                reranker.rerank(
                    query=question,
                    candidates=candidates,
                    top_k=(
                        self.FINAL_CONTEXT_COUNT
                    ),
                )
            )

        else:
            reranked = []

        rerank_seconds = (
            time.perf_counter()
            - rerank_started
        )

        print(
            f"[RAG] Rerank: "
            f"{rerank_seconds:.3f}s"
        )

        print(
            f"[RAG] Reranked results: "
            f"{len(reranked)}"
        )

        #
        # 3. Limit final context size
        #
        selected_results = (
            self._limit_context(
                reranked
            )
        )

        print(
            f"[RAG] Context chunks: "
            f"{len(selected_results)}"
        )

        #
        # 4. Convert retrieved chunks
        #    to prompt sources
        #
        prompt_sources = (
            self._build_prompt_sources(
                selected_results
            )
        )

        #
        # 5. Build final RAG prompt
        #
        prompt = (
            build_rag_prompt(
                question=question,
                sources=prompt_sources,
                history=history,
            )
        )

        #
        # 6. LLM generation
        #
        generation_started = (
            time.perf_counter()
        )

        response = (
            llm_manager.generate(
                system_prompt=(
                    SYSTEM_PROMPT
                ),
                user_prompt=prompt,
                provider=(
                    llm_provider
                ),
                model=(
                    llm_model
                ),
            )
        )

        generation_seconds = (
            time.perf_counter()
            - generation_started
        )

        total_seconds = (
            time.perf_counter()
            - total_started
        )

        print(
            f"[RAG] Generation: "
            f"{generation_seconds:.3f}s"
        )

        print(
            f"[RAG] Total: "
            f"{total_seconds:.3f}s"
        )

        print(
            f"[RAG] Used LLM: "
            f"{response.provider} / "
            f"{response.model}"
        )

        print("=" * 80)

        #
        # 7. Return answer + metadata
        #
        return RagAnswer(
            answer=(
                response.text
            ),
            sources=(
                self._build_sources(
                    selected_results
                )
            ),
            provider=(
                response.provider
            ),
            model=(
                response.model
            ),
            retrieval_seconds=(
                retrieval_seconds
            ),
            rerank_seconds=(
                rerank_seconds
            ),
            generation_seconds=(
                generation_seconds
            ),
            total_seconds=(
                total_seconds
            ),
        )

    def _limit_context(
        self,
        results: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:

        if not results:
            return []

        selected = []

        total_chars = 0

        for result in results:

            text = (
                result.text
                or ""
            ).strip()

            if not text:
                continue

            content_length = len(
                text
            )

            if (
                selected
                and (
                    total_chars
                    + content_length
                    > self.MAX_CONTEXT_CHARS
                )
            ):
                break

            selected.append(
                result
            )

            total_chars += (
                content_length
            )

        return selected

    def _build_prompt_sources(
        self,
        results: list[RetrievedChunk],
    ) -> list[PromptSource]:

        sources = []

        for index, result in enumerate(
            results,
            start=1,
        ):

            sources.append(
                PromptSource(
                    citation=(
                        f"S{index}"
                    ),
                    source_name=(
                        result.source_name
                    ),
                    document_title=(
                        result.document_title
                    ),
                    reference=(
                        self._get_reference(
                            result
                        )
                    ),
                    text=(
                        result.text
                    ),
                )
            )

        return sources

    def _build_sources(
        self,
        results: list[RetrievedChunk],
    ) -> list[RagSource]:

        sources = []

        for index, result in enumerate(
            results,
            start=1,
        ):

            sources.append(
                RagSource(
                    citation=(
                        f"S{index}"
                    ),
                    source_id=(
                        result.source_id
                    ),
                    document_id=(
                        result.document_id
                    ),
                    chunk_id=(
                        result.chunk_id
                    ),
                    source_name=(
                        result.source_name
                    ),
                    source_type=(
                        result.source_type
                    ),
                    document_title=(
                        result.document_title
                    ),
                    chunk_index=(
                        result.chunk_index
                    ),
                    reference=(
                        self._get_reference(
                            result
                        )
                    ),
                    vector_score=(
                        result.score
                    ),
                    rerank_score=(
                        result.rerank_score
                    ),
                )
            )

        return sources

    @staticmethod
    def _get_reference(
        result: RetrievedChunk,
    ) -> str | None:

        #
        # Website:
        # external_id is normally the page URL.
        #
        if (
            result.source_type
            == "web"
        ):
            return (
                result.external_id
                or result.source_uri
            )

        #
        # Git:
        #
        # source_uri:
        # https://github.com/.../repo
        #
        # external_id:
        # src/services/example.py
        #
        if (
            result.source_type
            == "git"
        ):

            if (
                result.source_uri
                and result.external_id
            ):
                return (
                    f"{result.source_uri}"
                    f" -> "
                    f"{result.external_id}"
                )

            return (
                result.external_id
                or result.source_uri
            )

        #
        # Uploaded file.
        #
        if (
            result.source_type
            == "file"
        ):
            return (
                result.document_title
                or result.external_id
            )

        #
        # Fallback.
        #
        return (
            result.external_id
            or result.source_uri
            or result.document_title
        )


rag_service = RagService()