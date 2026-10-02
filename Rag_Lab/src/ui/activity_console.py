from nicegui import ui

from src.observability.activity import (
    activity_store,
)


class ActivityConsole:

    MAX_VISIBLE = 60

    def __init__(self) -> None:

        self.container = None
        self.status_label = None

        self._last_event_id = None

    def render(self) -> None:

        with ui.expansion(
            "CITY OPERATIONS LOG",
            icon="terminal",
            value=False,
        ).classes(
            "w-full"
        ):

            with ui.row().classes(
                "w-full items-center"
            ):

                self.status_label = (
                    ui.label(
                        "SYSTEM ONLINE"
                    )
                    .classes(
                        "text-xs "
                        "advisor-subtitle"
                    )
                )

                ui.space()

                ui.button(
                    "Clear",
                    icon="delete_sweep",
                    on_click=self.clear,
                ).props(
                    "flat dense"
                )

            self.container = (
                ui.column()
                .classes(
                    "w-full "
                    "gap-1 "
                    "q-pa-sm"
                )
                .style(
                    "max-height: 260px; "
                    "overflow-y: auto; "
                    "background: #091014; "
                    "border: "
                    "1px solid #344750;"
                )
            )

            self.refresh()

            ui.timer(
                0.7,
                self.refresh,
            )

    def clear(self) -> None:

        activity_store.clear()

        self._last_event_id = None

        self.refresh()

    def refresh(self) -> None:

        if self.container is None:
            return

        entries = (
            activity_store.recent(
                self.MAX_VISIBLE
            )
        )

        latest_id = (
            entries[-1].id
            if entries
            else None
        )

        if (
            latest_id
            == self._last_event_id
        ):
            return

        self._last_event_id = (
            latest_id
        )

        self.container.clear()

        with self.container:

            if not entries:

                ui.label(
                    "No operations recorded."
                ).classes(
                    "text-xs advisor-muted"
                )

                return

            for entry in entries:

                with ui.row().classes(
                    "w-full "
                    "no-wrap "
                    "items-start "
                    "gap-2"
                ):

                    ui.label(
                        entry.created_at.strftime(
                            "%H:%M:%S"
                        )
                    ).classes(
                        "text-xs "
                        "advisor-muted"
                    )

                    ui.label(
                        entry.category
                    ).classes(
                        (
                            "text-xs "
                            "advisor-subtitle"
                        )
                    ).style(
                        "width: 92px;"
                    )

                    level_class = (
                        "text-negative"
                        if (
                            entry.level
                            in {
                                "ERROR",
                                "CRITICAL",
                            }
                        )
                        else
                        (
                            "text-warning"
                            if (
                                entry.level
                                == "WARNING"
                            )
                            else ""
                        )
                    )

                    ui.label(
                        entry.message
                    ).classes(
                        (
                            "text-xs "
                            f"{level_class}"
                        )
                    ).style(
                        "overflow-wrap: anywhere;"
                    )


activity_console = (
    ActivityConsole()
)