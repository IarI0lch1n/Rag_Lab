import logging
import re

from dataclasses import (
    asdict,
    dataclass,
)

from urllib.parse import (
    urlsplit,
)

from src.services.internet_research_service import (
    internet_research_service,
)


logger = logging.getLogger(
    "advisor.internet.auto"
)


@dataclass(frozen=True)
class AutoResearchSource:

    title: str

    url: str

    status: str

    source_id: int | None = None

    error: str | None = None


@dataclass(frozen=True)
class AutoResearchReport:

    query: str

    hits_found: int

    sources: list[
        AutoResearchSource
    ]

    @property
    def indexed_count(
        self,
    ) -> int:

        return sum(
            1
            for source
            in self.sources
            if (
                source.status
                == "indexed"
            )
        )

    @property
    def duplicate_count(
        self,
    ) -> int:

        return sum(
            1
            for source
            in self.sources
            if (
                source.status
                == "duplicate"
            )
        )

    def to_dict(
        self,
    ) -> dict:

        return {
            "query": (
                self.query
            ),

            "hits_found": (
                self.hits_found
            ),

            "indexed_count": (
                self.indexed_count
            ),

            "duplicate_count": (
                self.duplicate_count
            ),

            "sources": [
                asdict(
                    source
                )
                for source
                in self.sources
            ],
        }


class AutoResearchService:

    SEARCH_RESULTS = 5

    MAX_IMPORT_ATTEMPTS = 3

    TARGET_INDEXED_SOURCES = 1

    #
    # These sites may be useful search
    # results, but are poor candidates
    # for automatic crawling.
    #

    BLOCKED_AUTO_DOMAINS = {
        "steamcommunity.com",
    }

    SEARCH_PREFIX_PATTERNS = (
        (
            r"^\s*(?:пожалуйста\s+)?"
            r"(?:поищи|найди|посмотри)"
            r"(?:\s+тогда)?"
            r"(?:\s+мне)?"
            r"(?:\s+ответ)?"
            r"(?:\s+в\s+интернете"
            r"|\s+в\s+сети"
            r"|\s+онлайн)?"
            r"(?:\s+информацию)?"
            r"(?:\s+про|\s+о|\s+об)?"
            r"(?:\s+то)?"
            r"[\s,:;-]*"
        ),

        (
            r"^\s*(?:please\s+)?"
            r"(?:search|find|look\s+up)"
            r"(?:\s+the)?"
            r"(?:\s+answer)?"
            r"(?:\s+online"
            r"|\s+on\s+the\s+web"
            r"|\s+on\s+the\s+internet)?"
            r"(?:\s+for|\s+about)?"
            r"[\s,:;-]*"
        ),
    )

    def research(
        self,
        question: str,
    ) -> AutoResearchReport:

        question = (
            question
            or ""
        ).strip()

        if not question:

            raise ValueError(
                (
                    "Research question "
                    "cannot be empty."
                )
            )

        web_query = (
            self._build_web_query(
                question
            )
        )

        logger.info(
            (
                "Automatic web "
                "reconnaissance started | "
                "query=%s"
            ),
            web_query,
        )

        hits = (
            internet_research_service
            .search(
                query=web_query,
                max_results=(
                    self.SEARCH_RESULTS
                ),
            )
        )

        logger.info(
            (
                "Automatic web search "
                "completed | "
                "query=%s | "
                "hits=%s"
            ),
            web_query,
            len(hits),
        )

        processed_sources = []

        if not hits:

            return (
                AutoResearchReport(
                    query=web_query,
                    hits_found=0,
                    sources=[],
                )
            )

        attempts = 0

        indexed = 0

        for hit in hits:

            if (
                attempts
                >= self
                .MAX_IMPORT_ATTEMPTS
            ):

                break

            if (
                indexed
                >= self
                .TARGET_INDEXED_SOURCES
            ):

                break

            if (
                self
                ._is_blocked_domain(
                    hit.url
                )
            ):

                logger.info(
                    (
                        "Skipping automatic "
                        "acquisition for "
                        "restricted domain | "
                        "url=%s"
                    ),
                    hit.url,
                )

                processed_sources.append(
                    AutoResearchSource(
                        title=hit.title,
                        url=hit.url,
                        status="skipped",
                        error=(
                            "Source discovered, "
                            "but this domain is "
                            "not suitable for "
                            "automatic acquisition."
                        ),
                    )
                )

                continue

            attempts += 1

            logger.info(
                (
                    "Evaluating web source | "
                    "attempt=%s/%s | "
                    "title=%s | "
                    "url=%s"
                ),
                attempts,
                self
                .MAX_IMPORT_ATTEMPTS,
                hit.title,
                hit.url,
            )

            try:

                result = (
                    internet_research_service
                    .import_hit(
                        hit,
                        single_page=True,
                        cleanup_on_failure=(
                            True
                        ),
                    )
                )

            except Exception as exc:

                logger.exception(
                    (
                        "Automatic web "
                        "source processing "
                        "crashed | "
                        "url=%s"
                    ),
                    hit.url,
                )

                processed_sources.append(
                    AutoResearchSource(
                        title=hit.title,
                        url=hit.url,
                        status="failed",
                        error=str(exc),
                    )
                )

                continue

            processed_sources.append(
                AutoResearchSource(
                    title=hit.title,
                    url=hit.url,
                    source_id=(
                        result
                        .source_id
                    ),
                    status=(
                        result.status
                    ),
                    error=(
                        result.error
                    ),
                )
            )

            if (
                result.status
                == "indexed"
            ):

                indexed += 1

                logger.info(
                    (
                        "Web source added "
                        "to Advisor archive | "
                        "source_id=%s | "
                        "url=%s"
                    ),
                    result.source_id,
                    hit.url,
                )

            elif (
                result.status
                == "duplicate"
            ):

                logger.info(
                    (
                        "Web source already "
                        "exists in archive | "
                        "url=%s"
                    ),
                    hit.url,
                )

            else:

                logger.warning(
                    (
                        "Web source could "
                        "not be indexed | "
                        "status=%s | "
                        "url=%s | "
                        "error=%s"
                    ),
                    result.status,
                    hit.url,
                    result.error,
                )

        report = (
            AutoResearchReport(
                query=web_query,
                hits_found=(
                    len(hits)
                ),
                sources=(
                    processed_sources
                ),
            )
        )

        logger.info(
            (
                "Automatic web "
                "reconnaissance completed | "
                "hits=%s | "
                "processed=%s | "
                "indexed=%s | "
                "duplicates=%s"
            ),
            report.hits_found,
            len(
                report.sources
            ),
            report.indexed_count,
            report.duplicate_count,
        )

        return report

    @classmethod
    def _is_blocked_domain(
        cls,
        url: str,
    ) -> bool:

        hostname = (
            urlsplit(
                url
            ).hostname
            or ""
        ).lower()

        return any(
            (
                hostname == domain
                or hostname.endswith(
                    "."
                    + domain
                )
            )
            for domain
            in cls
            .BLOCKED_AUTO_DOMAINS
        )

    @classmethod
    def _build_web_query(
        cls,
        question: str,
    ) -> str:

        query = (
            question.strip()
        )

        for pattern in (
            cls
            .SEARCH_PREFIX_PATTERNS
        ):

            query = re.sub(
                pattern,
                "",
                query,
                count=1,
                flags=(
                    re.IGNORECASE
                ),
            )

        query = re.sub(
            r"\s+",
            " ",
            query,
        ).strip(
            " ,.;:-"
        )

        if not query:

            query = question.strip()

        #
        # Avoid sending huge conversational
        # instructions to the search engine.
        #

        if len(query) > 240:

            shortened = (
                query[:240]
                .rsplit(
                    " ",
                    1,
                )[0]
                .strip()
            )

            if shortened:

                query = shortened

        if (
            "frostpunk"
            not in query.casefold()
        ):

            query = (
                f"Frostpunk {query}"
            )

        logger.info(
            (
                "Prepared web search query | "
                "query=%s"
            ),
            query,
        )

        return query


auto_research_service = (
    AutoResearchService()
)