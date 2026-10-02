from nicegui import (
    run,
    ui,
)

from src.config import settings

from src.generation.llm import (
    get_llm_catalog,
    llm_manager,
)


class LLMSelector:

    def __init__(
        self,
    ) -> None:

        self.catalog = (
            get_llm_catalog()
        )

        self.provider_select = None
        self.model_select = None

        self.status_label = None
        self.response_label = None

        self.test_button = None
        self.spinner = None

    @property
    def provider(
        self,
    ) -> str:

        if self.provider_select is None:
            return ""

        return str(
            self.provider_select.value
            or ""
        )

    @property
    def model(
        self,
    ) -> str:

        if self.model_select is None:
            return ""

        return str(
            self.model_select.value
            or ""
        )

    def render(
        self,
    ) -> None:

        default_provider = (
            settings
            .llm_provider
            .strip()
            .lower()
        )

        if (
            default_provider
            not in self.catalog
        ):
            default_provider = next(
                iter(
                    self.catalog
                )
            )

        default_models = (
            self.catalog.get(
                default_provider,
                [],
            )
        )

        if not default_models:
            raise ValueError(
                f"No models configured "
                f"for provider "
                f"'{default_provider}'."
            )

        default_model = (
            llm_manager
            .get_default_model(
                default_provider
            )
        )

        if (
            default_model
            not in default_models
        ):
            default_model = (
                default_models[0]
            )

        with ui.column().classes(
            "w-full gap-3"
        ):

            ui.label(
                "ADVISOR CORE"
            ).classes(
                "text-subtitle1 "
                "font-medium "
                "advisor-section-title"
            )

            ui.label(
                "Select the language model "
                "used by the Advisor."
            ).classes(
                "text-xs "
                "advisor-muted"
            )

            with ui.row().classes(
                "w-full "
                "gap-3 "
                "items-start"
            ):

                self.provider_select = (
                    ui.select(
                        options=list(
                            self.catalog.keys()
                        ),
                        value=(
                            default_provider
                        ),
                        label="Provider",
                    )
                    .classes(
                        "w-40"
                    )
                )

                self.model_select = (
                    ui.select(
                        options=(
                            default_models
                        ),
                        value=(
                            default_model
                        ),
                        label="Core model",
                    )
                    .classes(
                        "flex-1"
                    )
                )

            self.provider_select.on(
                "update:model-value",
                lambda _:
                self._sync_provider_models(),
            )

            self.model_select.on(
                "update:model-value",
                lambda _:
                self._update_selection_text(),
            )

            with ui.row().classes(
                "w-full "
                "items-center "
                "gap-3"
            ):

                self.test_button = (
                    ui.button(
                        "Test core connection",
                        icon=(
                            "settings_input_antenna"
                        ),
                        on_click=(
                            self
                            .test_selected_model
                        ),
                    )
                    .props(
                        "outline"
                    )
                )

                self.spinner = (
                    ui.spinner(
                        size="22px"
                    )
                )

                self.spinner.set_visibility(
                    False
                )

            self.status_label = (
                ui.label(
                    (
                        f"Active core: "
                        f"{default_provider} / "
                        f"{default_model}"
                    )
                )
                .classes(
                    "text-caption "
                    "advisor-muted"
                )
            )

            self.response_label = (
                ui.label("")
                .classes(
                    "text-body2 "
                    "whitespace-pre-wrap"
                )
            )

    def _sync_provider_models(
        self,
    ) -> None:

        provider = (
            self.provider
        )

        if not provider:
            return

        models = (
            self.catalog.get(
                provider,
                [],
            )
        )

        if not models:

            self.model_select.options = []

            self.model_select.value = None

            self.model_select.update()

            self._update_selection_text()

            return

        default_model = (
            llm_manager
            .get_default_model(
                provider
            )
        )

        if (
            default_model
            not in models
        ):
            default_model = (
                models[0]
            )

        self.model_select.options = list(
            models
        )

        self.model_select.value = (
            default_model
        )

        self.model_select.update()

        self.response_label.set_text(
            ""
        )

        self._update_selection_text()

        print(
            f"[UI] Advisor core changed: "
            f"{provider} / "
            f"{default_model}"
        )

    def _update_selection_text(
        self,
    ) -> None:

        if (
            self.status_label
            is None
        ):
            return

        self.status_label.set_text(
            f"Active core: "
            f"{self.provider} / "
            f"{self.model}"
        )

    async def test_selected_model(
        self,
    ) -> None:

        provider = (
            self.provider
        )

        model = (
            self.model
        )

        if (
            not provider
            or not model
        ):

            ui.notify(
                "Select an Advisor core first.",
                color="warning",
            )

            return

        available_models = (
            self.catalog.get(
                provider,
                [],
            )
        )

        if (
            model
            not in available_models
        ):

            self._sync_provider_models()

            ui.notify(
                "Core selection synchronized. "
                "Try again.",
                color="warning",
            )

            return

        self.test_button.disable()

        self.spinner.set_visibility(
            True
        )

        self.status_label.set_text(
            f"Testing core: "
            f"{provider} / "
            f"{model}..."
        )

        self.response_label.set_text(
            ""
        )

        try:

            response = await run.io_bound(
                llm_manager.generate,
                system_prompt=(
                    "You are the Advisor system. "
                    "This is a connection test. "
                    "Reply with one short sentence."
                ),
                user_prompt=(
                    "Confirm that the Advisor "
                    "core is operational."
                ),
                provider=provider,
                model=model,
            )

            self.status_label.set_text(
                f"Core online: "
                f"{response.provider} / "
                f"{response.model}"
            )

            self.response_label.set_text(
                f"{response.text}"
            )

            ui.notify(
                "Advisor core online.",
                color="positive",
            )

        except Exception as exc:

            error_message = str(
                exc
            )

            lowered_error = (
                error_message.lower()
            )

            if (
                "429" in error_message
                or "rate limit"
                in lowered_error
                or "too_many_requests"
                in lowered_error
            ):

                self.status_label.set_text(
                    f"Core unavailable: "
                    f"{provider} / "
                    f"{model}"
                )

                self.response_label.set_text(
                    "Provider rate limit reached. "
                    "Select another core or "
                    "try again later."
                )

                ui.notify(
                    "Core rate limit reached.",
                    color="warning",
                )

            else:

                self.status_label.set_text(
                    f"Core failure: "
                    f"{provider} / "
                    f"{model}"
                )

                self.response_label.set_text(
                    f"Connection error:\n"
                    f"{error_message}"
                )

                ui.notify(
                    "Advisor core unavailable.",
                    color="negative",
                )

        finally:

            self.spinner.set_visibility(
                False
            )

            self.test_button.enable()


llm_selector = LLMSelector()