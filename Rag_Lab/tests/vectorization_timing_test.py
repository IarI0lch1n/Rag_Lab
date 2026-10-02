import sys
import time

from src.embeddings.embedder import embedder
from src.services.source_service import source_service
from src.services.vectorization_service import vectorization_service
from src.vector_store.qdrant_store import qdrant_store


def format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"

    if seconds < 60:
        return f"{seconds:.2f} sec"

    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60

    return (
        f"{minutes} min "
        f"{remaining_seconds:.1f} sec"
    )


def get_test_source():
    sources = source_service.get_sources()

    indexed_sources = [
        source
        for source in sources
        if source.status == "indexed"
    ]

    if not indexed_sources:
        raise RuntimeError(
            "No indexed sources found."
        )

    #
    # Optional:
    # python -m tests.vectorization_timing_test 15
    #
    if len(sys.argv) > 1:
        source_id = int(sys.argv[1])

        for source in indexed_sources:
            if source.id == source_id:
                return source

        raise RuntimeError(
            f"Indexed source with id "
            f"{source_id} was not found."
        )

    #
    # get_sources() is sorted newest first,
    # so this is normally the latest indexed source.
    #
    return indexed_sources[0]


def main() -> None:
    source = get_test_source()

    print()
    print("=" * 72)
    print("RAG Vectorization Performance Test")
    print("=" * 72)

    print()
    print(
        f"Source ID   : {source.id}"
    )
    print(
        f"Source name : {source.name}"
    )
    print(
        f"Source type : {source.source_type}"
    )

    #
    # 1. MODEL LOAD
    #

    print()
    print("-" * 72)
    print("1. Loading embedding model")
    print("-" * 72)

    model_started = time.perf_counter()

    dimension = embedder.dimension

    model_elapsed = (
        time.perf_counter()
        - model_started
    )

    print(
        f"Vector dimension : {dimension}"
    )

    print(
        f"Model load time  : "
        f"{format_duration(model_elapsed)}"
    )

    #
    # 2. VECTORIZATION
    #

    print()
    print("-" * 72)
    print("2. Vectorizing source")
    print("-" * 72)

    vectorization_started = (
        time.perf_counter()
    )

    chunk_count = (
        vectorization_service
        .vectorize_source(
            source.id
        )
    )

    vectorization_elapsed = (
        time.perf_counter()
        - vectorization_started
    )

    print(
        f"Chunks created     : "
        f"{chunk_count}"
    )

    print(
        f"Vectorization time : "
        f"{format_duration(vectorization_elapsed)}"
    )

    if vectorization_elapsed > 0:
        chunks_per_second = (
            chunk_count
            / vectorization_elapsed
        )

        print(
            f"Speed              : "
            f"{chunks_per_second:.2f} "
            f"chunks/sec"
        )

        if chunk_count > 0:
            average_ms = (
                vectorization_elapsed
                / chunk_count
                * 1000
            )

            print(
                f"Average per chunk  : "
                f"{average_ms:.1f} ms"
            )

    #
    # 3. QUERY EMBEDDING
    #

    print()
    print("-" * 72)
    print("3. Query embedding")
    print("-" * 72)

    query = (
        "Какая информация содержится "
        "в этом источнике?"
    )

    query_embedding_started = (
        time.perf_counter()
    )

    query_vector = (
        embedder.embed_query(
            query
        )
    )

    query_embedding_elapsed = (
        time.perf_counter()
        - query_embedding_started
    )

    print(
        f"Query embedding time : "
        f"{format_duration(query_embedding_elapsed)}"
    )

    #
    # 4. QDRANT SEARCH
    #

    print()
    print("-" * 72)
    print("4. Qdrant search")
    print("-" * 72)

    search_started = (
        time.perf_counter()
    )

    results = (
        qdrant_store.search(
            query_vector,
            limit=10,
        )
    )

    search_elapsed = (
        time.perf_counter()
        - search_started
    )

    print(
        f"Search time : "
        f"{format_duration(search_elapsed)}"
    )

    print(
        f"Results     : "
        f"{len(results)}"
    )

    #
    # 5. ESTIMATED RAG RETRIEVAL TIME
    #

    retrieval_elapsed = (
        query_embedding_elapsed
        + search_elapsed
    )

    print()
    print("=" * 72)
    print("RESULT")
    print("=" * 72)

    print(
        f"Model load              : "
        f"{format_duration(model_elapsed)}"
    )

    print(
        f"Full source vectorization: "
        f"{format_duration(vectorization_elapsed)}"
    )

    print(
        f"Query embedding         : "
        f"{format_duration(query_embedding_elapsed)}"
    )

    print(
        f"Qdrant search           : "
        f"{format_duration(search_elapsed)}"
    )

    print(
        f"Retrieval for one query : "
        f"{format_duration(retrieval_elapsed)}"
    )

    print()
    print(
        "Note: LLM response generation "
        "is not included in this test."
    )

    print("=" * 72)
    print()


if __name__ == "__main__":
    main()