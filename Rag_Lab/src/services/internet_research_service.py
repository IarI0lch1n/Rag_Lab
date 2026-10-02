import logging

from dataclasses import (
    dataclass,
)

from urllib.parse import (
    urlsplit,
)

from ddgs import DDGS


from src.services.indexing_service import (
    indexing_service,
)

from src.services.source_service import (
    DuplicateSourceError,
    InvalidSourceError,
    source_service,
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
        max_results: int = (
            DEFAULT_RESULTS
        ),
    ) -> list[InternetSearchHit]:

        query = (
            query
            or ""
        ).strip()

        if not query:

            raise ValueError(
                "Internet search query "
                "cannot be empty."
            )

        max_results = max(
            1,
            min(
                int(max_results),
                20,
            ),
        )

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

        hits = []

        seen_urls = set()

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

            parsed = (
                urlsplit(
                    url
                )
            )

            if (
                parsed.scheme
                not in {
                    "http",
                    "https",
                }
            ):
                continue

            #
            # Strip fragment.
            #
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

            title = (
                str(
                    result.get(
                        "title",
                        "",
                    )
                    or ""
                )
                .strip()
            )

            snippet = (
                str(
                    result.get(
                        "body",
                        "",
                    )
                    or ""
                )
                .strip()
            )

            if not title:

                title = (
                    parsed.hostname
                    or "Internet source"
                )

            hits.append(
                InternetSearchHit(
                    title=title,
                    url=normalized_url,
                    snippet=snippet,
                )
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
    ) -> InternetImportResult:

        logger.info(
            (
                "Importing internet source | "
                "title=%s | url=%s"
            ),
            hit.title,
            hit.url,
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

        except DuplicateSourceError:

            logger.warning(
                (
                    "Internet source already "
                    "exists in archive | "
                    "url=%s"
                ),
                hit.url,
            )

            return (
                InternetImportResult(
                    title=hit.title,
                    url=hit.url,
                    source_id=None,
                    status="duplicate",
                    error=(
                        "Source already exists."
                    ),
                )
            )

        except InvalidSourceError as exc:

            logger.error(
                (
                    "Internet source rejected | "
                    "url=%s | error=%s"
                ),
                hit.url,
                exc,
            )

            return (
                InternetImportResult(
                    title=hit.title,
                    url=hit.url,
                    source_id=None,
                    status="failed",
                    error=str(exc),
                )
            )

        logger.info(
            (
                "Internet source stored in SQL | "
                "source_id=%s | url=%s"
            ),
            source.id,
            hit.url,
        )

        try:

            result = (
                indexing_service
                .index_source(
                    source.id
                )
            )

        except Exception as exc:

            logger.exception(
                (
                    "Internet source indexing "
                    "crashed | source_id=%s"
                ),
                source.id,
            )

            return (
                InternetImportResult(
                    title=hit.title,
                    url=hit.url,
                    source_id=source.id,
                    status="failed",
                    error=str(exc),
                )
            )

        if result.status == "indexed":

            logger.info(
                (
                    "Internet source indexed | "
                    "source_id=%s | "
                    "documents_created=%s | "
                    "chunks_created=%s"
                ),
                source.id,
                result.documents_created,
                result.chunks_created,
            )

            return (
                InternetImportResult(
                    title=hit.title,
                    url=hit.url,
                    source_id=source.id,
                    status="indexed",
                )
            )

        logger.error(
            (
                "Internet source indexing "
                "failed | source_id=%s | "
                "error=%s"
            ),
            source.id,
            result.error,
        )

        return (
            InternetImportResult(
                title=hit.title,
                url=hit.url,
                source_id=source.id,
                status=(
                    result.status
                ),
                error=(
                    result.error
                ),
            )
        )


internet_research_service = (
    InternetResearchService()
)