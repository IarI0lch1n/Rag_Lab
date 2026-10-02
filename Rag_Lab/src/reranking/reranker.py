from dataclasses import replace

import torch

from sentence_transformers import (
    CrossEncoder,
)

from FlagEmbedding import (
    FlagReranker,
)

from src.retrieval.retriever import (
    RetrievedChunk,
)


class Reranker:

    GPU_MODEL = (
        "BAAI/bge-reranker-v2-m3"
    )

    CPU_MODEL = (
        "cross-encoder/"
        "mmarco-mMiniLMv2-L12-H384-v1"
    )

    def __init__(self) -> None:
        self._model = None
        self._backend = None

    @property
    def has_cuda(
        self,
    ) -> bool:
        return torch.cuda.is_available()

    @property
    def model(
        self,
    ):
        if self._model is not None:
            return self._model

        if self.has_cuda:
            print(
                f"[Reranker] CUDA detected."
            )

            print(
                f"[Reranker] Loading "
                f"'{self.GPU_MODEL}'..."
            )

            self._model = (
                FlagReranker(
                    self.GPU_MODEL,
                    use_fp16=True,
                )
            )

            self._backend = "flag"

        else:
            print(
                "[Reranker] CUDA not detected."
            )

            print(
                f"[Reranker] Loading "
                f"'{self.CPU_MODEL}'..."
            )

            self._model = (
                CrossEncoder(
                    self.CPU_MODEL,
                    max_length=512,
                    device="cpu",
                )
            )

            self._backend = "cross_encoder"

        print(
            "[Reranker] Model loaded."
        )

        return self._model

    def warmup(
        self,
    ) -> None:
        _ = self.model

    def rerank(
        self,
        query: str,
        candidates: list[
            RetrievedChunk
        ],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:

        query = query.strip()

        if not query:
            return []

        if not candidates:
            return []

        pairs = [
            (
                query,
                candidate.text,
            )
            for candidate
            in candidates
        ]

        model = self.model

        if self._backend == "flag":

            scores = (
                model.compute_score(
                    pairs,
                    batch_size=8,
                    max_length=512,
                    normalize=True,
                )
            )

        else:

            scores = (
                model.predict(
                    pairs,
                    batch_size=16,
                    show_progress_bar=False,
                )
            )

        if len(candidates) == 1:
            scores = [
                float(scores)
            ]

        reranked = []

        for (
            candidate,
            score,
        ) in zip(
            candidates,
            scores,
        ):
            reranked.append(
                replace(
                    candidate,
                    rerank_score=(
                        float(score)
                    ),
                )
            )

        reranked.sort(
            key=lambda result: (
                result.rerank_score
                if (
                    result.rerank_score
                    is not None
                )
                else float("-inf")
            ),
            reverse=True,
        )

        return (
            reranked[
                :top_k
            ]
        )


reranker = Reranker()