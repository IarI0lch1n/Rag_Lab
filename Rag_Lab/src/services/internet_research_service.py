import logging

from dataclasses import (
    asdict,
    dataclass,
)

from urllib.parse import (
    urlsplit,
)

from ddgs import DDGS

from src.grabber.web_grabber import (
    web_grabber,
)

from src.observability.langfuse_service import (
    langfuse_service,
)

from src.services.indexing_service import (
    indexing_service,
)

from src.services.source_service import (
    DuplicateSourceError,
    InvalidSourceError,
    SourceNotFoundError,
    source_service,
)

from src.vector_store.qdrant_store import (
    qdrant_store,
)


logger = logging.getLogger(
    "advisor.internet"
)


@dataclass(frozen=True)
class InternetSearchHit:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class InternetImportResult:
    title: str
    url: str
    source_id: int | None
    status: str
    error: str | None = None


class InternetResearchService:

    DEFAULT_RESULTS = 8

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_RESULTS,
    ) -> list[
        InternetSearchHit
    ]:

        query = (
            query
            or ""
        ).strip()

        if not query:
            raise ValueError(
                (
                    "Internet search query "
                    "cannot be empty."
                )
            )

        max_results = max(
            1,
            min(
                int(max_results),
                20,
            ),
        )

        with (
            langfuse_service
            .observation(
                name="internet-search",
                as_type="tool",
                input_data={
                    "query": query,
                    "max_results": (
                        max_results
                    ),
                    "engine": "ddgs",
                },
            )
        ) as observation:

            logger.info(
                (
                    "Internet reconnaissance "
                    "started | query=%s | "
                    "max_results=%s"
                ),
                query,
                max_results,
            )

            raw_results = (
                DDGS(
                    timeout=15
                )
                .text(
                    query=query,
                    region="us-en",
                    safesearch="moderate",
                    max_results=(
                        max_results
                    ),
                    backend="auto",
                )
            )

            hits: list[
                InternetSearchHit
            ] = []

            seen_urls: set[str] = set()

            for result in raw_results:

                url = str(
                    result.get(
                        "href",
                        "",
                    )
                    or ""
                ).strip()

                if not url:
                    continue

                parsed = urlsplit(
                    url
                )

                if parsed.scheme not in {
                    "http",
                    "https",
                }:
                    continue

                normalized_url = (
                    parsed
                    ._replace(
                        fragment=""
                    )
                    .geturl()
                )

                if (
                    normalized_url
                    in seen_urls
                ):
                    continue

                seen_urls.add(
                    normalized_url
                )

                title = str(
                    result.get(
                        "title",
                        "",
                    )
                    or ""
                ).strip()

                snippet = str(
                    result.get(
                        "body",
                        "",
                    )
                    or ""
                ).strip()

                if not title:
                    title = (
                        parsed.hostname
                        or
                        "Internet source"
                    )

                hits.append(
                    InternetSearchHit(
                        title=title,
                        url=(
                            normalized_url
                        ),
                        snippet=snippet,
                    )
                )

            observation.update(
                output={
                    "result_count": (
                        len(hits)
                    ),
                    "results": [
                        {
                            "title": (
                                hit.title
                            ),
                            "url": hit.url,
                            "snippet": (
                                hit.snippet[
                                    :300
                                ]
                            ),
                        }
                        for hit in hits
                    ],
                }
            )

            logger.info(
                (
                    "Internet reconnaissance "
                    "completed | query=%s | "
                    "results=%s"
                ),
                query,
                len(hits),
            )

            return hits

    def import_hit(
        self,
        hit: InternetSearchHit,
        *,
        single_page: bool = False,
        cleanup_on_failure: bool = False,
    ) -> InternetImportResult:

        with (
            langfuse_service
            .observation(
                name=(
                    "internet-source-import"
                ),
                as_type="chain",
                input_data={
                    "title": (
                        hit.title
                    ),
                    "url": hit.url,
                    "single_page": (
                        single_page
                    ),
                    "cleanup_on_failure": (
                        cleanup_on_failure
                    ),
                },
            )
        ) as observation:

            result = (
                self._import_hit(
                    hit=hit,
                    single_page=(
                        single_page
                    ),
                    cleanup_on_failure=(
                        cleanup_on_failure
                    ),
                )
            )

            observation.update(
                output=(
                    asdict(result)
                ),
                metadata={
                    "status": (
                        result.status
                    ),
                    "source_id": (
                        result.source_id
                    ),
                },
            )

            return result

    def _import_hit(
        self,
        *,
        hit: InternetSearchHit,
        single_page: bool,
        cleanup_on_failure: bool,
    ) -> InternetImportResult:

        logger.info(
            (
                "Importing internet source | "
                "title=%s | url=%s | "
                "single_page=%s | "
                "cleanup_on_failure=%s"
            ),
            hit.title,
            hit.url,
            single_page,
            cleanup_on_failure,
        )

        try:
            source = (
                source_service
                .add_url_source(
                    url=hit.url,
                    name=(
                        hit.title[:255]
                    ),
                )
            )

        except DuplicateSourceError as exc:
            logger.info(
                (
                    "Internet source already "
                    "exists in archive | "
                    "url=%s"
                ),
                hit.url,
            )

            return InternetImportResult(
                title=hit.title,
                url=hit.url,
                source_id=None,
                status="duplicate",
                error=str(exc),
            )

        except InvalidSourceError as exc:
            logger.warning(
                (
                    "Internet source "
                    "rejected | "
                    "url=%s | error=%s"
                ),
                hit.url,
                exc,
            )

            return InternetImportResult(
                title=hit.title,
                url=hit.url,
                source_id=None,
                status="failed",
                error=str(exc),
            )

        source_id = source.id

        logger.info(
            (
                "Internet source stored "
                "in SQL | "
                "source_id=%s | url=%s"
            ),
            source_id,
            hit.url,
        )

        try:
            if single_page:
                logger.info(
                    (
                        "Single-page acquisition "
                        "enabled | source_id=%s"
                    ),
                    source_id,
                )

                with (
                    web_grabber
                    .crawl_limits(
                        max_pages=1,
                        max_depth=0,
                    )
                ):
                    result = (
                        indexing_service
                        .index_source(
                            source_id
                        )
                    )

            else:
                result = (
                    indexing_service
                    .index_source(
                        source_id
                    )
                )

        except Exception as exc:
            logger.exception(
                (
                    "Internet source "
                    "indexing crashed | "
                    "source_id=%s"
                ),
                source_id,
            )

            cleaned = False

            if cleanup_on_failure:
                cleaned = (
                    self
                    ._cleanup_failed_source(
                        source_id
                    )
                )

            return InternetImportResult(
                title=hit.title,
                url=hit.url,
                source_id=(
                    None
                    if cleaned
                    else source_id
                ),
                status="failed",
                error=str(exc),
            )

        if (
            result.status
            == "indexed"
        ):
            logger.info(
                (
                    "Internet source indexed | "
                    "source_id=%s | "
                    "documents_created=%s | "
                    "documents_updated=%s | "
                    "documents_skipped=%s | "
                    "chunks_created=%s"
                ),
                source_id,
                result.documents_created,
                result.documents_updated,
                result.documents_skipped,
                result.chunks_created,
            )

            return InternetImportResult(
                title=hit.title,
                url=hit.url,
                source_id=source_id,
                status="indexed",
            )

        if (
            result.status
            == "busy"
        ):
            return InternetImportResult(
                title=hit.title,
                url=hit.url,
                source_id=source_id,
                status="busy",
                error=(
                    result.error
                    or
                    (
                        "Source is already "
                        "being indexed."
                    )
                ),
            )

        logger.warning(
            (
                "Internet source "
                "indexing failed | "
                "source_id=%s | "
                "status=%s | error=%s"
            ),
            source_id,
            result.status,
            result.error,
        )

        cleaned = False

        if cleanup_on_failure:
            cleaned = (
                self
                ._cleanup_failed_source(
                    source_id
                )
            )

        return InternetImportResult(
            title=hit.title,
            url=hit.url,
            source_id=(
                None
                if cleaned
                else source_id
            ),
            status=result.status,
            error=result.error,
        )

    def _cleanup_failed_source(
        self,
        source_id: int,
    ) -> bool:

        with (
            langfuse_service
            .observation(
                name=(
                    "failed-source-cleanup"
                ),
                as_type="span",
                input_data={
                    "source_id": (
                        source_id
                    ),
                },
            )
        ) as observation:

            logger.info(
                (
                    "Cleaning failed "
                    "automatic source | "
                    "source_id=%s"
                ),
                source_id,
            )

            qdrant_cleaned = False
            sql_cleaned = False

            try:
                qdrant_store.delete_by_source_id(
                    source_id
                )

                qdrant_cleaned = True

            except Exception:
                logger.exception(
                    (
                        "Could not remove "
                        "failed source from "
                        "Qdrant | source_id=%s"
                    ),
                    source_id,
                )

            try:
                source_service.delete_source(
                    source_id
                )

                sql_cleaned = True

            except SourceNotFoundError:
                sql_cleaned = True

            except Exception:
                logger.exception(
                    (
                        "Could not remove "
                        "failed source from SQL | "
                        "source_id=%s"
                    ),
                    source_id,
                )

            observation.update(
                output={
                    "sql_cleaned": (
                        sql_cleaned
                    ),
                    "qdrant_cleaned": (
                        qdrant_cleaned
                    ),
                }
            )

            logger.info(
                (
                    "Failed source cleanup "
                    "completed | "
                    "source_id=%s | "
                    "sql=%s | qdrant=%s"
                ),
                source_id,
                sql_cleaned,
                qdrant_cleaned,
            )

            return sql_cleaned


internet_research_service = (
    InternetResearchService()
)