import logging

from dataclasses import (
    asdict,
    dataclass,
)

from src.services.internet_research_service import (
    InternetSearchHit,
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
                asdict(source)
                for source
                in self.sources
            ],
        }


class AutoResearchService:

    SEARCH_RESULTS = 5

    MAX_IMPORT_ATTEMPTS = 3

    TARGET_INDEXED_SOURCES = 1

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
                "Research question "
                "cannot be empty."
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

        #
        # STEP 1:
        # Search open web.
        #
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

            logger.info(
                (
                    "Automatic web recon "
                    "found no sources | "
                    "query=%s"
                ),
                web_query,
            )

            return AutoResearchReport(
                query=web_query,
                hits_found=0,
                sources=[],
            )

        #
        # STEP 2:
        # Try the highest-ranked results.
        #
        attempts = 0

        indexed = 0

        for hit in hits:

            if (
                attempts
                >= self.MAX_IMPORT_ATTEMPTS
            ):
                break

            if (
                indexed
                >= self
                .TARGET_INDEXED_SOURCES
            ):
                break

            attempts += 1

            logger.info(
                (
                    "Evaluating web source | "
                    "attempt=%s | "
                    "title=%s | "
                    "url=%s"
                ),
                attempts,
                hit.title,
                hit.url,
            )

            try:

                result = (
                    internet_research_service
                    .import_hit(
                        hit
                    )
                )

            except Exception as exc:

                logger.exception(
                    (
                        "Automatic web source "
                        "processing crashed | "
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
                        result.source_id
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
                        "Web source added to "
                        "Advisor archive | "
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
                        "Web source could not "
                        "be indexed | "
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
                hits_found=len(
                    hits
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

    @staticmethod
    def _build_web_query(
        question: str,
    ) -> str:

        normalized = (
            question.lower()
        )

        #
        # Advisor is specialized for
        # the Frostpunk universe.
        #
        if (
            "frostpunk"
            in normalized
        ):

            return question

        return (
            f"Frostpunk {question}"
        )


auto_research_service = (
    AutoResearchService()
)