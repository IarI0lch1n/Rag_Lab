from sentence_transformers import (
    SentenceTransformer,
)

from src.config import settings


class Embedder:
    def __init__(self) -> None:
        self._model = None

    @property
    def model(
        self,
    ) -> SentenceTransformer:
        if self._model is None:
            print(
                f"[Embeddings] Loading model "
                f"'{settings.embedding_model}'..."
            )

            self._model = (
                SentenceTransformer(
                    settings.embedding_model,
                    device=(
                        settings.embedding_device
                    ),
                )
            )

            print(
                "[Embeddings] Model loaded."
            )

        return self._model

    @property
    def dimension(
        self,
    ) -> int:
        model = self.model

        if hasattr(
            model,
            "get_embedding_dimension",
        ):
            dimension = (
                model.get_embedding_dimension()
            )

        else:
            dimension = (
                model
                .get_sentence_embedding_dimension()
            )

        if dimension is None:
            raise RuntimeError(
                "Could not determine "
                "embedding dimension."
            )

        return int(
            dimension
        )

    @property
    def max_sequence_length(
        self,
    ) -> int:
        return int(
            getattr(
                self.model,
                "max_seq_length",
                512,
            )
        )

    def embed_passages(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[list[float]]:
        if not texts:
            return []

        prepared = [
            f"passage: {text}"
            for text in texts
        ]

        vectors = (
            self.model.encode(
                prepared,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        )

        return (
            vectors
            .astype(float)
            .tolist()
        )

    def embed_query(
        self,
        query: str,
    ) -> list[float]:
        vector = (
            self.model.encode(
                f"query: {query}",
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
        )

        return (
            vector
            .astype(float)
            .tolist()
        )

    def count_tokens(
        self,
        text: str,
    ) -> int:
        return self.count_tokens_batch(
            [text]
        )[0]

    def count_tokens_batch(
        self,
        texts: list[str],
    ) -> list[int]:
        if not texts:
            return []

        encoded = (
            self.model.tokenizer(
                texts,
                add_special_tokens=False,
                padding=False,
                truncation=True,
                max_length=(
                    self.max_sequence_length
                ),
            )
        )

        return [
            len(token_ids)
            for token_ids
            in encoded[
                "input_ids"
            ]
        ]


embedder = Embedder()