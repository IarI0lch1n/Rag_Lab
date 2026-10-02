import json
import logging
import time

from dataclasses import (
    dataclass,
)

from pathlib import Path

from src.evaluation.metrics import (
    RankingMetrics,
    calculate_ranking_metrics,
    unique_ranked_ids,
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


logger = logging.getLogger(
    "advisor.evaluation"
)


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str

    question: str

    language: str

    answerable: bool

    relevant_document_ids: list[int]

    labeled: bool

    notes: str = ""


@dataclass(frozen=True)
class RankingResult:
    document_ids: list[int]

    metrics: dict[
        int,
        RankingMetrics,
    ]

    def to_dict(
        self,
    ) -> dict:

        return {
            "document_ids": (
                self.document_ids
            ),

            "metrics": {
                str(k): (
                    value.to_dict()
                )
                for k, value
                in self.metrics.items()
            },
        }


@dataclass(frozen=True)
class EvaluationCaseResult:
    case_id: str

    question: str

    language: str

    relevant_document_ids: list[int]

    retrieval_seconds: float

    rerank_seconds: float

    baseline: RankingResult

    reranked: RankingResult

    trace_id: str | None

    def to_dict(
        self,
    ) -> dict:

        return {
            "case_id": (
                self.case_id
            ),

            "question": (
                self.question
            ),

            "language": (
                self.language
            ),

            "relevant_document_ids": (
                self.relevant_document_ids
            ),

            "retrieval_seconds": (
                self.retrieval_seconds
            ),

            "rerank_seconds": (
                self.rerank_seconds
            ),

            "baseline": (
                self.baseline.to_dict()
            ),

            "reranked": (
                self.reranked.to_dict()
            ),

            "trace_id": (
                self.trace_id
            ),
        }


@dataclass(frozen=True)
class EvaluationSummary:
    case_count: int

    k_values: list[int]

    baseline: dict[
        int,
        dict[str, float],
    ]

    reranked: dict[
        int,
        dict[str, float],
    ]

    average_retrieval_seconds: float

    average_rerank_seconds: float

    def to_dict(
        self,
    ) -> dict:

        return {
            "case_count": (
                self.case_count
            ),

            "k_values": (
                self.k_values
            ),

            "baseline": {
                str(k): value
                for k, value
                in self.baseline.items()
            },

            "reranked": {
                str(k): value
                for k, value
                in self.reranked.items()
            },

            "average_retrieval_seconds": (
                self
                .average_retrieval_seconds
            ),

            "average_rerank_seconds": (
                self
                .average_rerank_seconds
            ),
        }


class RagEvaluator:

    DEFAULT_K_VALUES = [
        3,
        5,
        10,
        20,
    ]

    CANDIDATE_COUNT = 20

    QDRANT_LIMIT = 100

    MAX_PER_DOCUMENT = 4

    def load_dataset(
        self,
        path: str | Path,
    ) -> list[
        EvaluationCase
    ]:

        path = Path(
            path
        )

        if not path.exists():
            raise FileNotFoundError(
                (
                    "Evaluation dataset "
                    f"not found: {path}"
                )
            )

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            payload = json.load(
                file
            )

        raw_cases = (
            payload.get(
                "cases",
                [],
            )
        )

        cases = []

        for raw_case in raw_cases:

            case = EvaluationCase(
                case_id=str(
                    raw_case[
                        "id"
                    ]
                ),
                question=str(
                    raw_case[
                        "question"
                    ]
                ).strip(),
                language=str(
                    raw_case.get(
                        "language",
                        "en",
                    )
                ),
                answerable=bool(
                    raw_case.get(
                        "answerable",
                        True,
                    )
                ),
                relevant_document_ids=[
                    int(value)
                    for value in (
                        raw_case.get(
                            "relevant_document_ids",
                            [],
                        )
                    )
                ],
                labeled=bool(
                    raw_case.get(
                        "labeled",
                        False,
                    )
                ),
                notes=str(
                    raw_case.get(
                        "notes",
                        "",
                    )
                ),
            )

            cases.append(
                case
            )

        return cases

    def evaluate_case(
        self,
        case: EvaluationCase,
        *,
        k_values: (
            list[int]
            | None
        ) = None,
        langfuse_session_id: (
            str
            | None
        ) = None,
    ) -> EvaluationCaseResult:

        if not case.labeled:

            raise ValueError(
                (
                    f"Evaluation case "
                    f"'{case.case_id}' "
                    "has not been labeled."
                )
            )

        if not case.answerable:

            raise ValueError(
                (
                    f"Evaluation case "
                    f"'{case.case_id}' "
                    "is marked unanswerable "
                    "and cannot be used for "
                    "retrieval relevance metrics."
                )
            )

        if (
            not case
            .relevant_document_ids
        ):

            raise ValueError(
                (
                    f"Evaluation case "
                    f"'{case.case_id}' "
                    "has no relevant "
                    "document IDs."
                )
            )

        k_values = (
            sorted(
                set(
                    k_values
                    or self
                    .DEFAULT_K_VALUES
                )
            )
        )

        max_k = max(
            k_values
        )

        with (
            langfuse_service
            .trace(
                name=(
                    "retrieval-evaluation-case"
                ),
                input_data={
                    "case_id": (
                        case.case_id
                    ),
                    "question": (
                        case.question
                    ),
                    "language": (
                        case.language
                    ),
                    "relevant_document_ids": (
                        case
                        .relevant_document_ids
                    ),
                },
                session_id=(
                    langfuse_session_id
                ),
                metadata={
                    "evaluation": True,
                    "k_values": (
                        k_values
                    ),
                },
                tags=[
                    "advisor",
                    "evaluation",
                    "retrieval",
                ],
            )
        ) as trace:

            #
            # VECTOR RETRIEVAL
            #

            retrieval_started = (
                time.perf_counter()
            )

            candidates = (
                retriever
                .retrieve_candidates(
                    query=(
                        case.question
                    ),
                    limit=max(
                        self
                        .CANDIDATE_COUNT,
                        max_k,
                    ),
                    qdrant_limit=(
                        self
                        .QDRANT_LIMIT
                    ),
                    max_per_document=(
                        self
                        .MAX_PER_DOCUMENT
                    ),
                    debug=False,
                )
            )

            retrieval_seconds = (
                time.perf_counter()
                - retrieval_started
            )

            baseline_ids = (
                self
                ._document_ranking(
                    candidates
                )
            )

            baseline_metrics = (
                self
                ._calculate_metrics(
                    document_ids=(
                        baseline_ids
                    ),
                    relevant_document_ids=(
                        case
                        .relevant_document_ids
                    ),
                    k_values=(
                        k_values
                    ),
                )
            )

            #
            # RERANKING
            #

            rerank_started = (
                time.perf_counter()
            )

            if candidates:

                reranked_chunks = (
                    reranker.rerank(
                        query=(
                            case.question
                        ),
                        candidates=(
                            candidates
                        ),
                        top_k=(
                            len(candidates)
                        ),
                    )
                )

            else:

                reranked_chunks = []

            rerank_seconds = (
                time.perf_counter()
                - rerank_started
            )

            reranked_ids = (
                self
                ._document_ranking(
                    reranked_chunks
                )
            )

            reranked_metrics = (
                self
                ._calculate_metrics(
                    document_ids=(
                        reranked_ids
                    ),
                    relevant_document_ids=(
                        case
                        .relevant_document_ids
                    ),
                    k_values=(
                        k_values
                    ),
                )
            )

            result = (
                EvaluationCaseResult(
                    case_id=(
                        case.case_id
                    ),
                    question=(
                        case.question
                    ),
                    language=(
                        case.language
                    ),
                    relevant_document_ids=(
                        case
                        .relevant_document_ids
                    ),
                    retrieval_seconds=(
                        retrieval_seconds
                    ),
                    rerank_seconds=(
                        rerank_seconds
                    ),
                    baseline=(
                        RankingResult(
                            document_ids=(
                                baseline_ids
                            ),
                            metrics=(
                                baseline_metrics
                            ),
                        )
                    ),
                    reranked=(
                        RankingResult(
                            document_ids=(
                                reranked_ids
                            ),
                            metrics=(
                                reranked_metrics
                            ),
                        )
                    ),
                    trace_id=(
                        trace.trace_id
                    ),
                )
            )

            trace.update(
                output=(
                    result.to_dict()
                ),
                metadata={
                    "retrieval_seconds": (
                        retrieval_seconds
                    ),
                    "rerank_seconds": (
                        rerank_seconds
                    ),
                },
            )

            self._send_langfuse_scores(
                trace_id=(
                    trace.trace_id
                ),
                result=result,
            )

            return result

    def evaluate_dataset(
        self,
        cases: list[
            EvaluationCase
        ],
        *,
        k_values: (
            list[int]
            | None
        ) = None,
        langfuse_session_id: (
            str
            | None
        ) = None,
    ) -> tuple[
        list[
            EvaluationCaseResult
        ],
        EvaluationSummary,
    ]:

        k_values = (
            sorted(
                set(
                    k_values
                    or self
                    .DEFAULT_K_VALUES
                )
            )
        )

        usable_cases = [
            case
            for case in cases
            if (
                case.labeled
                and case.answerable
                and case
                .relevant_document_ids
            )
        ]

        if not usable_cases:

            raise ValueError(
                (
                    "Dataset contains no "
                    "labeled answerable cases."
                )
            )

        logger.info(
            (
                "Evaluation started | "
                "cases=%s | k=%s"
            ),
            len(usable_cases),
            k_values,
        )

        #
        # Load reranker once before timings
        # for individual questions.
        #

        reranker.warmup()

        results = []

        for index, case in enumerate(
            usable_cases,
            start=1,
        ):

            print()
            print(
                "=" * 80
            )

            print(
                (
                    "[Evaluation] "
                    f"{index}/"
                    f"{len(usable_cases)} "
                    f"{case.case_id}"
                )
            )

            print(
                case.question
            )

            result = (
                self.evaluate_case(
                    case,
                    k_values=(
                        k_values
                    ),
                    langfuse_session_id=(
                        langfuse_session_id
                    ),
                )
            )

            results.append(
                result
            )

            self._print_case_result(
                result
            )

        summary = (
            self._build_summary(
                results=results,
                k_values=k_values,
            )
        )

        langfuse_service.flush()

        return (
            results,
            summary,
        )

    @staticmethod
    def _document_ranking(
        chunks: list[
            RetrievedChunk
        ],
    ) -> list[int]:

        return unique_ranked_ids(
            [
                chunk.document_id
                for chunk in chunks
            ]
        )

    @staticmethod
    def _calculate_metrics(
        *,
        document_ids: list[int],
        relevant_document_ids: (
            list[int]
        ),
        k_values: list[int],
    ) -> dict[
        int,
        RankingMetrics,
    ]:

        return {
            k: calculate_ranking_metrics(
                retrieved_document_ids=(
                    document_ids
                ),
                relevant_document_ids=(
                    relevant_document_ids
                ),
                k=k,
            )
            for k in k_values
        }

    def _send_langfuse_scores(
        self,
        *,
        trace_id: str | None,
        result: EvaluationCaseResult,
    ) -> None:

        if not trace_id:
            return

        try:

            for name, ranking in [
                (
                    "baseline",
                    result.baseline,
                ),
                (
                    "reranked",
                    result.reranked,
                ),
            ]:

                metrics = (
                    ranking.metrics.get(
                        5
                    )
                )

                if metrics is None:
                    continue

                for (
                    metric_name,
                    value,
                ) in [
                    (
                        "hit_rate_at_5",
                        metrics.hit_rate,
                    ),
                    (
                        "precision_at_5",
                        metrics.precision,
                    ),
                    (
                        "recall_at_5",
                        metrics.recall,
                    ),
                    (
                        "mrr_at_5",
                        (
                            metrics
                            .reciprocal_rank
                        ),
                    ),
                ]:

                    (
                        langfuse_service
                        .client
                        .create_score(
                            name=(
                                f"{name}_"
                                f"{metric_name}"
                            ),
                            value=float(
                                value
                            ),
                            trace_id=(
                                trace_id
                            ),
                            data_type=(
                                "NUMERIC"
                            ),
                            metadata={
                                "case_id": (
                                    result.case_id
                                ),
                                "pipeline": (
                                    name
                                ),
                            },
                        )
                    )

        except Exception:

            logger.exception(
                (
                    "Could not send "
                    "evaluation scores "
                    "to Langfuse | "
                    "case_id=%s"
                ),
                result.case_id,
            )

    @staticmethod
    def _aggregate_pipeline(
        results: list[
            EvaluationCaseResult
        ],
        *,
        pipeline: str,
        k_values: list[int],
    ) -> dict[
        int,
        dict[str, float],
    ]:

        summary = {}

        for k in k_values:

            metrics = []

            for result in results:

                ranking = getattr(
                    result,
                    pipeline,
                )

                value = (
                    ranking.metrics.get(
                        k
                    )
                )

                if value is not None:
                    metrics.append(
                        value
                    )

            if not metrics:
                continue

            count = len(
                metrics
            )

            summary[k] = {
                "hit_rate": (
                    sum(
                        item.hit_rate
                        for item in metrics
                    )
                    / count
                ),

                "precision": (
                    sum(
                        item.precision
                        for item in metrics
                    )
                    / count
                ),

                "recall": (
                    sum(
                        item.recall
                        for item in metrics
                    )
                    / count
                ),

                "mrr": (
                    sum(
                        item
                        .reciprocal_rank
                        for item in metrics
                    )
                    / count
                ),
            }

        return summary

    def _build_summary(
        self,
        *,
        results: list[
            EvaluationCaseResult
        ],
        k_values: list[int],
    ) -> EvaluationSummary:

        count = len(
            results
        )

        return EvaluationSummary(
            case_count=count,
            k_values=k_values,
            baseline=(
                self
                ._aggregate_pipeline(
                    results,
                    pipeline=(
                        "baseline"
                    ),
                    k_values=(
                        k_values
                    ),
                )
            ),
            reranked=(
                self
                ._aggregate_pipeline(
                    results,
                    pipeline=(
                        "reranked"
                    ),
                    k_values=(
                        k_values
                    ),
                )
            ),
            average_retrieval_seconds=(
                sum(
                    result
                    .retrieval_seconds
                    for result in results
                )
                / count
            ),
            average_rerank_seconds=(
                sum(
                    result
                    .rerank_seconds
                    for result in results
                )
                / count
            ),
        )

    @staticmethod
    def _print_case_result(
        result: EvaluationCaseResult,
    ) -> None:

        baseline = (
            result
            .baseline
            .metrics
            .get(5)
        )

        reranked = (
            result
            .reranked
            .metrics
            .get(5)
        )

        print()

        if baseline:

            print(
                (
                    "Vector @5  "
                    f"| hit="
                    f"{baseline.hit_rate:.2f} "
                    f"| recall="
                    f"{baseline.recall:.2f} "
                    f"| mrr="
                    f"{baseline.reciprocal_rank:.2f}"
                )
            )

        if reranked:

            print(
                (
                    "Rerank @5  "
                    f"| hit="
                    f"{reranked.hit_rate:.2f} "
                    f"| recall="
                    f"{reranked.recall:.2f} "
                    f"| mrr="
                    f"{reranked.reciprocal_rank:.2f}"
                )
            )


rag_evaluator = (
    RagEvaluator()
)