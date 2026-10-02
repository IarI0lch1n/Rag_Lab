import logging

from nicegui import (
    run,
    ui,
)

from src.services.internet_research_service import (
    InternetSearchHit,
    internet_research_service,
)


logger = logging.getLogger(
    "advisor.internet.ui"
)


class InternetResearchPanel:

    def __init__(self) -> None:

        self.results = []

        self.query_input = None
        self.search_button = None
        self.results_container = None
        self.status_label = None

        self.on_archive_changed = None

        self.is_busy = False

    def render(
        self,
        on_archive_changed=None,
    ) -> None:

        self.on_archive_changed = (
            on_archive_changed
        )

        with ui.expansion(
            "INTERNET RECON",
            icon="travel_explore",
            value=False,
        ).classes(
            "w-full"
        ):

            ui.label(
                (
                    "Search the open web and "
                    "import selected records "
                    "into the city archive."
                )
            ).classes(
                "text-xs advisor-muted"
            )

            with ui.row().classes(
                "w-full items-center gap-2"
            ):

                self.query_input = (
                    ui.input(
                        placeholder=(
                            "e.g. Frostpunk "
                            "Winterhome lore"
                        ),
                    )
                    .props(
                        "outlined dense"
                    )
                    .classes(
                        "col"
                    )
                )

                self.search_button = (
                    ui.button(
                        icon="search",
                        on_click=(
                            self.search
                        ),
                    )
                    .props(
                        "round"
                    )
                )

            self.query_input.on(
                "keydown.enter",
                self._on_enter,
            )

            self.status_label = (
                ui.label("")
                .classes(
                    "text-xs "
                    "advisor-muted"
                )
            )

            self.results_container = (
                ui.column()
                .classes(
                    "w-full gap-2 q-mt-sm"
                )
            )

    async def _on_enter(
        self,
        _event,
    ) -> None:

        await self.search()

    async def search(
        self,
    ) -> None:

        if self.is_busy:
            return

        query = (
            self.query_input.value
            or ""
        ).strip()

        if not query:
            return

        self.is_busy = True

        self.search_button.disable()

        self.status_label.set_text(
            "Searching open networks..."
        )

        self.results_container.clear()

        try:

            self.results = await (
                run.io_bound(
                    internet_research_service
                    .search,
                    query,
                    8,
                )
            )

            self.status_label.set_text(
                (
                    f"{len(self.results)} "
                    "records discovered."
                )
            )

            self._render_results()

        except Exception as exc:

            logger.exception(
                "Internet reconnaissance failed."
            )

            self.status_label.set_text(
                "Reconnaissance failed."
            )

            ui.notify(
                str(exc),
                color="negative",
            )

        finally:

            self.is_busy = False

            self.search_button.enable()

    def _render_results(
        self,
    ) -> None:

        self.results_container.clear()

        with self.results_container:

            for hit in self.results:

                with ui.card().classes(
                    "source-card "
                    "w-full "
                    "q-pa-sm "
                    "shadow-none"
                ):

                    ui.label(
                        hit.title
                    ).classes(
                        "text-sm "
                        "font-medium"
                    )

                    if hit.snippet:

                        ui.label(
                            hit.snippet
                        ).classes(
                            "text-xs "
                            "advisor-muted"
                        ).style(
                            (
                                "max-height: 54px; "
                                "overflow: hidden;"
                            )
                        )

                    ui.link(
                        hit.url,
                        hit.url,
                        new_tab=True,
                    ).classes(
                        "text-xs "
                        "text-primary "
                        "source-uri"
                    )

                    with ui.row().classes(
                        "w-full justify-end"
                    ):

                        ui.button(
                            "Archive",
                            icon="inventory_2",
                            on_click=(
                                lambda
                                selected=hit:
                                self.import_hit(
                                    selected
                                )
                            ),
                        ).props(
                            "flat dense"
                        )

    async def import_hit(
        self,
        hit: InternetSearchHit,
    ) -> None:

        if self.is_busy:
            return

        self.is_busy = True

        self.search_button.disable()

        self.status_label.set_text(
            (
                "Acquiring and processing "
                f"'{hit.title}'..."
            )
        )

        try:

            result = await (
                run.io_bound(
                    internet_research_service
                    .import_hit,
                    hit,
                )
            )

            if (
                result.status
                == "indexed"
            ):

                ui.notify(
                    (
                        "Internet record archived "
                        "and indexed."
                    ),
                    color="positive",
                )

            elif (
                result.status
                == "duplicate"
            ):

                ui.notify(
                    (
                        "This record already "
                        "exists in the archive."
                    ),
                    color="warning",
                )

            else:

                ui.notify(
                    (
                        "Record stored, but "
                        "processing failed: "
                        f"{result.error}"
                    ),
                    color="negative",
                )

            if (
                self.on_archive_changed
                is not None
            ):
                self.on_archive_changed()

        finally:

            self.status_label.set_text(
                ""
            )

            self.is_busy = False

            self.search_button.enable()


internet_research_panel = (
    InternetResearchPanel()
)