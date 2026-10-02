import time

from dataclasses import (
    dataclass,
)

from src.generation.llm import (
    llm_manager,
)

from src.generation.prompts import (
    PromptSource,
    SYSTEM_PROMPT,
    build_rag_prompt,
)

from src.observability.langfuse_service import (
    langfuse_service,
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

    reference: (
        str
        | None
    )

    vector_score: float

    rerank_score: (
        float
        | None
    )


@dataclass(frozen=True)
class RagAnswer:
    answer: str

    sources: list[
        RagSource
    ]

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
        history: (
            list[
                dict[
                    str,
                    str,
                ]
            ]
            | None
        ) = None,
        llm_provider: (
            str
            | None
        ) = None,
        llm_model: (
            str
            | None
        ) = None,
        session_id: (
            int
            | str
            | None
        ) = None,
    ) -> RagAnswer:

        question = (
            question.strip()
        )

        if not question:

            raise ValueError(
                (
                    "Question cannot "
                    "be empty."
                )
            )

        history = (
            history
            or []
        )

        langfuse_session_id = (
            f"advisor-chat-{session_id}"
            if session_id
            is not None
            else None
        )

        trace_input = {
            "question": (
                question
            ),
            "history_messages": (
                len(history)
            ),
        }

        trace_metadata = {
            "requested_provider": (
                llm_provider
                or "default"
            ),
            "requested_model": (
                llm_model
                or "default"
            ),
            "candidate_count": (
                self.CANDIDATE_COUNT
            ),
            "qdrant_limit": (
                self.QDRANT_LIMIT
            ),
            "final_context_count": (
                self.FINAL_CONTEXT_COUNT
            ),
        }

        with (
            langfuse_service
            .trace(
                name=(
                    "advisor-rag-query"
                ),
                input_data=(
                    trace_input
                ),
                session_id=(
                    langfuse_session_id
                ),
                metadata=(
                    trace_metadata
                ),
                tags=[
                    "advisor",
                    "rag",
                ],
            )
        ) as trace:

            return (
                self._ask_inside_trace(
                    question=(
                        question
                    ),
                    history=(
                        history
                    ),
                    llm_provider=(
                        llm_provider
                    ),
                    llm_model=(
                        llm_model
                    ),
                    trace=(
                        trace
                    ),
                )
            )

    def _ask_inside_trace(
        self,
        *,
        question: str,
        history: list[
            dict[
                str,
                str,
            ]
        ],
        llm_provider: (
            str
            | None
        ),
        llm_model: (
            str
            | None
        ),
        trace,
    ) -> RagAnswer:

        total_started = (
            time.perf_counter()
        )

        print()
        print(
            "=" * 80
        )

        print(
            (
                "[RAG] Question: "
                f"{question}"
            )
        )

        if llm_provider:

            print(
                (
                    "[RAG] LLM provider: "
                    f"{llm_provider}"
                )
            )

        if llm_model:

            print(
                (
                    "[RAG] LLM model: "
                    f"{llm_model}"
                )
            )

        print(
            "=" * 80
        )

        #
        # 1. RETRIEVAL
        #

        retrieval_started = (
            time.perf_counter()
        )

        with (
            langfuse_service
            .observation(
                name=(
                    "rag-retrieval"
                ),
                as_type=(
                    "retriever"
                ),
                input_data={
                    "query": (
                        question
                    ),
                    "candidate_limit": (
                        self
                        .CANDIDATE_COUNT
                    ),
                    "qdrant_limit": (
                        self
                        .QDRANT_LIMIT
                    ),
                    "max_per_document": (
                        self
                        .MAX_PER_DOCUMENT
                    ),
                },
            )
        ) as retrieval_observation:

            candidates = (
                retriever
                .retrieve_candidates(
                    query=question,
                    limit=(
                        self
                        .CANDIDATE_COUNT
                    ),
                    qdrant_limit=(
                        self
                        .QDRANT_LIMIT
                    ),
                    max_per_document=(
                        self
                        .MAX_PER_DOCUMENT
                    ),
                    debug=True,
                )
            )

            retrieval_seconds = (
                time.perf_counter()
                - retrieval_started
            )

            retrieval_observation.update(
                output={
                    "candidate_count": (
                        len(candidates)
                    ),
                    "candidates": (
                        self
                        ._trace_chunks(
                            candidates
                        )
                    ),
                },
                metadata={
                    "duration_seconds": (
                        retrieval_seconds
                    ),
                },
            )

        print(
            (
                "[RAG] Retrieval: "
                f"{retrieval_seconds:.3f}s"
            )
        )

        print(
            (
                "[RAG] Candidates: "
                f"{len(candidates)}"
            )
        )

        #
        # 2. RERANK
        #

        rerank_started = (
            time.perf_counter()
        )

        with (
            langfuse_service
            .observation(
                name=(
                    "rag-reranking"
                ),
                as_type="span",
                input_data={
                    "query": (
                        question
                    ),
                    "candidate_count": (
                        len(candidates)
                    ),
                    "top_k": (
                        self
                        .FINAL_CONTEXT_COUNT
                    ),
                },
            )
        ) as rerank_observation:

            if candidates:

                reranked = (
                    reranker.rerank(
                        query=question,
                        candidates=(
                            candidates
                        ),
                        top_k=(
                            self
                            .FINAL_CONTEXT_COUNT
                        ),
                    )
                )

            else:

                reranked = []

            rerank_seconds = (
                time.perf_counter()
                - rerank_started
            )

            rerank_observation.update(
                output={
                    "result_count": (
                        len(reranked)
                    ),
                    "results": (
                        self
                        ._trace_chunks(
                            reranked
                        )
                    ),
                },
                metadata={
                    "duration_seconds": (
                        rerank_seconds
                    ),
                },
            )

        print(
            (
                "[RAG] Rerank: "
                f"{rerank_seconds:.3f}s"
            )
        )

        print(
            (
                "[RAG] Reranked results: "
                f"{len(reranked)}"
            )
        )

        #
        # 3. LIMIT CONTEXT
        #

        selected_results = (
            self._limit_context(
                reranked
            )
        )

        print(
            (
                "[RAG] Context chunks: "
                f"{len(selected_results)}"
            )
        )

        #
        # 4. PROMPT SOURCES
        #

        prompt_sources = (
            self
            ._build_prompt_sources(
                selected_results
            )
        )

        #
        # 5. PROMPT CONSTRUCTION
        #

        with (
            langfuse_service
            .observation(
                name=(
                    "rag-prompt-construction"
                ),
                as_type="chain",
                input_data={
                    "question": (
                        question
                    ),
                    "source_count": (
                        len(
                            prompt_sources
                        )
                    ),
                    "history_messages": (
                        len(history)
                    ),
                },
            )
        ) as prompt_observation:

            prompt = (
                build_rag_prompt(
                    question=question,
                    sources=(
                        prompt_sources
                    ),
                    history=(
                        history
                    ),
                )
            )

            prompt_observation.update(
                output={
                    "prompt_chars": (
                        len(prompt)
                    ),
                    "context_chars": sum(
                        len(
                            result.text
                            or ""
                        )
                        for result
                        in selected_results
                    ),
                    "sources": (
                        self
                        ._trace_chunks(
                            selected_results
                        )
                    ),
                }
            )

        #
        # 6. LLM GENERATION
        #

        generation_started = (
            time.perf_counter()
        )

        with (
            langfuse_service
            .observation(
                name=(
                    "rag-llm-generation"
                ),
                as_type=(
                    "generation"
                ),
                input_data={
                    "system_prompt": (
                        SYSTEM_PROMPT
                    ),
                    "user_prompt": (
                        prompt
                    ),
                },
                metadata={
                    "provider": (
                        llm_provider
                        or "default"
                    ),
                },
                model=(
                    llm_model
                ),
            )
        ) as generation_observation:

            response = (
                llm_manager.generate(
                    system_prompt=(
                        SYSTEM_PROMPT
                    ),
                    user_prompt=(
                        prompt
                    ),
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

            generation_observation.update(
                output=(
                    response.text
                ),
                model=(
                    response.model
                ),
                metadata={
                    "provider": (
                        response.provider
                    ),
                    "duration_seconds": (
                        generation_seconds
                    ),
                },
            )

        total_seconds = (
            time.perf_counter()
            - total_started
        )

        print(
            (
                "[RAG] Generation: "
                f"{generation_seconds:.3f}s"
            )
        )

        print(
            (
                "[RAG] Total: "
                f"{total_seconds:.3f}s"
            )
        )

        print(
            (
                "[RAG] Used LLM: "
                f"{response.provider} / "
                f"{response.model}"
            )
        )

        print(
            "=" * 80
        )

        sources = (
            self._build_sources(
                selected_results
            )
        )

        answer = RagAnswer(
            answer=(
                response.text
            ),
            sources=(
                sources
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

        #
        # Root trace output.
        #

        trace.update(
            output={
                "answer": (
                    answer.answer
                ),
                "source_count": (
                    len(
                        answer.sources
                    )
                ),
                "sources": [
                    {
                        "citation": (
                            source.citation
                        ),
                        "source_id": (
                            source.source_id
                        ),
                        "document_id": (
                            source.document_id
                        ),
                        "chunk_id": (
                            source.chunk_id
                        ),
                        "source_name": (
                            source.source_name
                        ),
                        "document_title": (
                            source.document_title
                        ),
                        "reference": (
                            source.reference
                        ),
                    }
                    for source
                    in answer.sources
                ],
            },
            metadata={
                "provider": (
                    answer.provider
                ),
                "model": (
                    answer.model
                ),
                "retrieval_seconds": (
                    answer
                    .retrieval_seconds
                ),
                "rerank_seconds": (
                    answer
                    .rerank_seconds
                ),
                "generation_seconds": (
                    answer
                    .generation_seconds
                ),
                "total_seconds": (
                    answer.total_seconds
                ),
            },
        )

        return answer

    def _limit_context(
        self,
        results: list[
            RetrievedChunk
        ],
    ) -> list[
        RetrievedChunk
    ]:

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

            content_length = (
                len(text)
            )

            if (
                selected
                and (
                    total_chars
                    + content_length
                    > self
                    .MAX_CONTEXT_CHARS
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
        results: list[
            RetrievedChunk
        ],
    ) -> list[
        PromptSource
    ]:

        sources = []

        for (
            index,
            result,
        ) in enumerate(
            results,
            start=1,
        ):

            sources.append(
                PromptSource(
                    citation=(
                        f"S{index}"
                    ),
                    source_name=(
                        result
                        .source_name
                    ),
                    document_title=(
                        result
                        .document_title
                    ),
                    reference=(
                        self
                        ._get_reference(
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
        results: list[
            RetrievedChunk
        ],
    ) -> list[
        RagSource
    ]:

        sources = []

        for (
            index,
            result,
        ) in enumerate(
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
                        result
                        .document_title
                    ),
                    chunk_index=(
                        result.chunk_index
                    ),
                    reference=(
                        self
                        ._get_reference(
                            result
                        )
                    ),
                    vector_score=(
                        result.score
                    ),
                    rerank_score=(
                        result
                        .rerank_score
                    ),
                )
            )

        return sources

    def _trace_chunks(
        self,
        results: list[
            RetrievedChunk
        ],
    ) -> list[
        dict
    ]:

        traced = []

        for result in results:

            traced.append(
                {
                    "source_id": (
                        result.source_id
                    ),
                    "document_id": (
                        result.document_id
                    ),
                    "chunk_id": (
                        result.chunk_id
                    ),
                    "chunk_index": (
                        result.chunk_index
                    ),
                    "source_name": (
                        result.source_name
                    ),
                    "document_title": (
                        result.document_title
                    ),
                    "reference": (
                        self
                        ._get_reference(
                            result
                        )
                    ),
                    "vector_score": (
                        result.score
                    ),
                    "rerank_score": (
                        result
                        .rerank_score
                    ),
                }
            )

        return traced

    @staticmethod
    def _get_reference(
        result: RetrievedChunk,
    ) -> (
        str
        | None
    ):

        if (
            result.source_type
            == "web"
        ):

            return (
                result.external_id
                or result.source_uri
            )

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

        if (
            result.source_type
            == "file"
        ):

            return (
                result.document_title
                or result.external_id
            )

        return (
            result.external_id
            or result.source_uri
            or result.document_title
        )


rag_service = (
    RagService()
)