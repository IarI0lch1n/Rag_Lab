import logging

from nicegui import (
    run,
    ui,
)

from src.observability.langfuse_service import (
    langfuse_service,
)

from src.repositories.chat_repository import (
    chat_repository,
)

from src.services.auto_research_service import (
    AutoResearchReport,
    auto_research_service,
)

from src.services.rag_service import (
    RagAnswer,
    rag_service,
)

from src.ui.llm_selector import (
    llm_selector,
)


logger = logging.getLogger(
    "advisor.chat"
)


class RagChat:

    HISTORY_LIMIT = 10

    def __init__(
        self,
    ) -> None:

        self.session_id: int | None = None

        self.session_title = (
            "New consultation"
        )

        self.messages_container = None
        self.empty_state = None
        self.session_label = None

        self.question_input = None
        self.send_button = None
        self.new_chat_button = None
        self.web_recon_checkbox = None

        self.is_busy = False

    #
    # UI
    #

    def render(
        self,
    ) -> None:

        logger.info(
            "Initializing Advisor chat UI."
        )

        with (
            ui.column()
            .classes(
                "w-full h-full gap-0"
            )
            .style(
                "min-height: 0;"
            )
        ):

            #
            # ADVISOR CORE
            #

            with ui.column().classes(
                "w-full q-pa-md"
            ):

                llm_selector.render()

                with ui.row().classes(
                    (
                        "w-full "
                        "items-center "
                        "q-mt-sm"
                    )
                ):

                    self.web_recon_checkbox = (
                        ui.checkbox(
                            "OPEN WEB RECON",
                            value=False,
                        )
                        .props(
                            "dense"
                        )
                    )

                    self.web_recon_checkbox.tooltip(
                        (
                            "Search the open web "
                            "before answering. "
                            "The Advisor will try "
                            "to archive one useful "
                            "source so it can be "
                            "used again later."
                        )
                    )

                    ui.icon(
                        "travel_explore",
                        size="18px",
                    ).classes(
                        "advisor-logo"
                    )

                    ui.space()

                    self.new_chat_button = (
                        ui.button(
                            "New consultation",
                            icon="add_comment",
                            on_click=(
                                self.new_chat
                            ),
                        )
                        .props(
                            "flat"
                        )
                    )

                self.session_label = (
                    ui.label(
                        self.session_title
                    )
                    .classes(
                        (
                            "text-xs "
                            "advisor-muted"
                        )
                    )
                )

            ui.separator()

            #
            # MESSAGES
            #

            self.messages_container = (
                ui.column()
                .classes(
                    (
                        "col "
                        "w-full "
                        "q-pa-lg "
                        "gap-4"
                    )
                )
                .style(
                    (
                        "overflow-y: auto; "
                        "min-height: 0;"
                    )
                )
            )

            #
            # INPUT
            #

            with (
                ui.row()
                .classes(
                    (
                        "w-full "
                        "q-pa-md "
                        "items-center "
                        "gap-2"
                    )
                )
                .style(
                    (
                        "background: "
                        "rgba(12, 18, 21, 0.96); "
                        "border-top: "
                        "1px solid #344750;"
                    )
                )
            ):

                self.question_input = (
                    ui.input(
                        placeholder=(
                            "Consult the Advisor..."
                        ),
                    )
                    .props(
                        "outlined"
                    )
                    .classes(
                        "col"
                    )
                )

                self.send_button = (
                    ui.button(
                        icon="send",
                        on_click=(
                            self.send_message
                        ),
                    )
                    .props(
                        "round"
                    )
                )

            self.question_input.on(
                "keydown.enter",
                self._on_enter,
            )

            self._restore_latest_session()

    async def _on_enter(
        self,
        _event,
    ) -> None:

        await self.send_message()

    #
    # SEND MESSAGE
    #

    async def send_message(
        self,
    ) -> None:

        if self.is_busy:

            logger.warning(
                (
                    "Message ignored because "
                    "Advisor is busy | "
                    "session_id=%s"
                ),
                self.session_id,
            )

            return

        question = (
            self.question_input.value
            or ""
        ).strip()

        if not question:
            return

        provider = (
            llm_selector.provider
        )

        model = (
            llm_selector.model
        )

        use_web_recon = bool(
            self.web_recon_checkbox
            and self.web_recon_checkbox.value
        )

        if (
            not provider
            or not model
        ):

            ui.notify(
                (
                    "Select an Advisor "
                    "core first."
                ),
                color="warning",
            )

            return

        logger.info(
            (
                "Advisor consultation "
                "started | "
                "session_id=%s | "
                "provider=%s | "
                "model=%s | "
                "web_recon=%s | "
                "question_chars=%s"
            ),
            self.session_id,
            provider,
            model,
            use_web_recon,
            len(question),
        )

        #
        # LOAD CHAT HISTORY
        #

        if (
            self.session_id
            is not None
        ):

            try:

                history_for_rag = await (
                    run.io_bound(
                        chat_repository
                        .get_history,
                        session_id=(
                            self.session_id
                        ),
                        limit=(
                            self.HISTORY_LIMIT
                        ),
                    )
                )

                logger.info(
                    (
                        "Consultation history "
                        "loaded | "
                        "session_id=%s | "
                        "messages=%s"
                    ),
                    self.session_id,
                    len(
                        history_for_rag
                    ),
                )

            except Exception:

                logger.exception(
                    (
                        "Could not load "
                        "consultation history | "
                        "session_id=%s"
                    ),
                    self.session_id,
                )

                ui.notify(
                    (
                        "Could not load "
                        "consultation history."
                    ),
                    color="negative",
                )

                return

        else:

            history_for_rag = []

        #
        # CREATE CHAT SESSION
        #

        if (
            self.session_id
            is None
        ):

            try:

                title = (
                    chat_repository
                    .build_title(
                        question
                    )
                )

                chat_session = await (
                    run.io_bound(
                        chat_repository
                        .create_session,
                        title=title,
                    )
                )

                self.session_id = (
                    chat_session.id
                )

                self.session_title = (
                    chat_session.title
                    or title
                )

                self._update_session_label()

                logger.info(
                    (
                        "Consultation created | "
                        "session_id=%s | "
                        "title=%s"
                    ),
                    self.session_id,
                    self.session_title,
                )

            except Exception:

                logger.exception(
                    "Could not create consultation."
                )

                ui.notify(
                    (
                        "Could not create "
                        "consultation."
                    ),
                    color="negative",
                )

                return

        #
        # SAVE USER MESSAGE
        #

        try:

            saved_message = await (
                run.io_bound(
                    chat_repository
                    .add_message,
                    session_id=(
                        self.session_id
                    ),
                    role="user",
                    content=question,
                )
            )

            logger.info(
                (
                    "User message persisted | "
                    "session_id=%s | "
                    "message_id=%s"
                ),
                self.session_id,
                saved_message.id,
            )

        except Exception:

            logger.exception(
                (
                    "Could not persist "
                    "user message | "
                    "session_id=%s"
                ),
                self.session_id,
            )

            ui.notify(
                (
                    "Could not save "
                    "your message."
                ),
                color="negative",
            )

            return

        self._remove_empty_state()

        self._append_user_message(
            question
        )

        self.question_input.set_value(
            ""
        )

        (
            loading_row,
            loading_status,
        ) = self._append_loading_message(
            provider=provider,
            model=model,
            web_recon=(
                use_web_recon
            ),
        )

        self._set_busy(
            True
        )

        web_report = None

        #
        # Everything below belongs to ONE
        # Langfuse consultation trace.
        #

        try:

            langfuse_session_id = (
                f"advisor-chat-"
                f"{self.session_id}"
            )

            with (
                langfuse_service
                .trace(
                    name=(
                        "advisor-consultation"
                    ),
                    input_data={
                        "question": (
                            question
                        ),
                        "provider": (
                            provider
                        ),
                        "model": (
                            model
                        ),
                        "web_recon": (
                            use_web_recon
                        ),
                        "history_messages": (
                            len(
                                history_for_rag
                            )
                        ),
                    },
                    session_id=(
                        langfuse_session_id
                    ),
                    metadata={
                        "chat_session_id": (
                            self.session_id
                        ),
                        "provider": (
                            provider
                        ),
                        "model": (
                            model
                        ),
                        "web_recon": (
                            use_web_recon
                        ),
                    },
                    tags=[
                        "advisor",
                        "consultation",
                        (
                            "web-recon"
                            if use_web_recon
                            else
                            "local-archive"
                        ),
                    ],
                )
            ) as consultation_trace:

                #
                # run.io_bound executes work
                # in another thread.
                #
                # Therefore explicitly pass
                # Langfuse trace context.
                #

                trace_context = (
                    consultation_trace
                    .child_trace_context()
                )

                #
                # OPEN WEB RECON
                #

                if use_web_recon:

                    loading_status.set_text(
                        (
                            "Scanning open networks "
                            "for relevant records..."
                        )
                    )

                    logger.info(
                        (
                            "Open web recon enabled | "
                            "session_id=%s"
                        ),
                        self.session_id,
                    )

                    try:

                        web_report = await (
                            run.io_bound(
                                auto_research_service
                                .research,
                                question,
                                trace_context=(
                                    trace_context
                                ),
                                session_id=(
                                    self.session_id
                                ),
                            )
                        )

                        logger.info(
                            (
                                "Open web recon "
                                "completed | "
                                "session_id=%s | "
                                "hits=%s | "
                                "indexed=%s | "
                                "duplicates=%s"
                            ),
                            self.session_id,
                            (
                                web_report
                                .hits_found
                            ),
                            (
                                web_report
                                .indexed_count
                            ),
                            (
                                web_report
                                .duplicate_count
                            ),
                        )

                        if (
                            web_report
                            .indexed_count
                            > 0
                        ):

                            loading_status.set_text(
                                (
                                    "New record archived. "
                                    "Searching the expanded "
                                    "city archive..."
                                )
                            )

                        elif (
                            web_report
                            .duplicate_count
                            > 0
                        ):

                            loading_status.set_text(
                                (
                                    "External record "
                                    "already exists in "
                                    "the archive. "
                                    "Consulting stored "
                                    "data..."
                                )
                            )

                        else:

                            loading_status.set_text(
                                (
                                    "No new external "
                                    "record could be "
                                    "archived. "
                                    "Consulting existing "
                                    "city archives..."
                                )
                            )

                    except Exception as exc:

                        #
                        # Web Recon is optional.
                        # Its failure does not stop RAG.
                        #

                        logger.exception(
                            (
                                "Open web recon "
                                "failed | "
                                "session_id=%s"
                            ),
                            self.session_id,
                        )

                        consultation_trace.update(
                            metadata={
                                "web_recon_failed": (
                                    True
                                ),
                                "web_recon_error": (
                                    str(exc)[:1000]
                                ),
                            }
                        )

                        loading_status.set_text(
                            (
                                "Open network scan "
                                "failed. Continuing "
                                "with existing city "
                                "archives..."
                            )
                        )

                        web_report = None

                else:

                    loading_status.set_text(
                        (
                            "Consulting the "
                            "city archives..."
                        )
                    )

                #
                # RAG PIPELINE
                #

                logger.info(
                    (
                        "RAG analysis started | "
                        "session_id=%s"
                    ),
                    self.session_id,
                )

                result: RagAnswer = await (
                    run.io_bound(
                        rag_service.ask,
                        question=(
                            question
                        ),
                        history=(
                            history_for_rag
                        ),
                        llm_provider=(
                            provider
                        ),
                        llm_model=(
                            model
                        ),
                        session_id=(
                            self.session_id
                        ),
                        trace_context=(
                            trace_context
                        ),
                    )
                )

                logger.info(
                    (
                        "RAG analysis completed | "
                        "session_id=%s | "
                        "provider=%s | "
                        "model=%s | "
                        "sources=%s | "
                        "retrieval=%.3fs | "
                        "rerank=%.3fs | "
                        "generation=%.3fs | "
                        "total=%.3fs"
                    ),
                    self.session_id,
                    result.provider,
                    result.model,
                    len(
                        result.sources
                    ),
                    result.retrieval_seconds,
                    result.rerank_seconds,
                    result.generation_seconds,
                    result.total_seconds,
                )

                #
                # FINAL CONSULTATION TRACE OUTPUT
                #

                consultation_trace.update(
                    output={
                        "answer": (
                            result.answer
                        ),
                        "source_count": (
                            len(
                                result.sources
                            )
                        ),
                        "sources": [
                            {
                                "citation": (
                                    source.citation
                                ),
                                "source_id": (
                                    source.source_id
                                ),
                                "document_id": (
                                    source.document_id
                                ),
                                "chunk_id": (
                                    source.chunk_id
                                ),
                                "source_name": (
                                    source.source_name
                                ),
                                "document_title": (
                                    source
                                    .document_title
                                ),
                                "reference": (
                                    source.reference
                                ),
                            }
                            for source
                            in result.sources
                        ],
                        "web_recon": (
                            web_report.to_dict()
                            if web_report
                            else None
                        ),
                    },
                    metadata={
                        "provider": (
                            result.provider
                        ),
                        "model": (
                            result.model
                        ),
                        "retrieval_seconds": (
                            result
                            .retrieval_seconds
                        ),
                        "rerank_seconds": (
                            result
                            .rerank_seconds
                        ),
                        "generation_seconds": (
                            result
                            .generation_seconds
                        ),
                        "total_seconds": (
                            result
                            .total_seconds
                        ),
                        "source_count": (
                            len(
                                result.sources
                            )
                        ),
                        "web_recon_enabled": (
                            use_web_recon
                        ),
                        "web_sources_indexed": (
                            (
                                web_report
                                .indexed_count
                            )
                            if web_report
                            else 0
                        ),
                    },
                )

                #
                # SAVE ASSISTANT RESPONSE
                #

                metadata = (
                    self._build_result_metadata(
                        result=result,
                        web_report=(
                            web_report
                        ),
                    )
                )

                saved_assistant = await (
                    run.io_bound(
                        chat_repository
                        .add_message,
                        session_id=(
                            self.session_id
                        ),
                        role="assistant",
                        content=(
                            result.answer
                        ),
                        metadata=(
                            metadata
                        ),
                    )
                )

                logger.info(
                    (
                        "Advisor answer "
                        "persisted | "
                        "session_id=%s | "
                        "message_id=%s | "
                        "citations=%s"
                    ),
                    self.session_id,
                    saved_assistant.id,
                    len(
                        result.sources
                    ),
                )

                loading_row.delete()

                self._append_advisor_message(
                    result=result,
                    web_report=(
                        web_report
                    ),
                )

        except Exception as exc:

            logger.exception(
                (
                    "Advisor consultation "
                    "failed | "
                    "session_id=%s | "
                    "provider=%s | "
                    "model=%s"
                ),
                self.session_id,
                provider,
                model,
            )

            try:
                loading_row.delete()

            except Exception:
                pass

            self._append_error_message(
                provider=provider,
                model=model,
                error=exc,
                web_report=(
                    web_report
                ),
            )

        finally:

            self._set_busy(
                False
            )

    #
    # NEW CHAT
    #

    def new_chat(
        self,
    ) -> None:

        if self.is_busy:
            return

        logger.info(
            (
                "New consultation "
                "requested | "
                "previous_session_id=%s"
            ),
            self.session_id,
        )

        self.session_id = None

        self.session_title = (
            "New consultation"
        )

        self._update_session_label()

        if (
            self.messages_container
            is not None
        ):
            self.messages_container.clear()

        self.empty_state = None

        self._show_empty_state()

        if (
            self.question_input
            is not None
        ):
            self.question_input.set_value(
                ""
            )

        ui.notify(
            "New consultation ready.",
            color="info",
        )

    #
    # RESTORE CHAT
    #

    def _restore_latest_session(
        self,
    ) -> None:

        logger.info(
            (
                "Restoring latest "
                "Advisor consultation."
            )
        )

        try:

            chat_session = (
                chat_repository
                .get_latest_session()
            )

        except Exception:

            logger.exception(
                (
                    "Could not restore "
                    "latest consultation."
                )
            )

            self._show_empty_state()

            ui.notify(
                (
                    "Could not restore "
                    "consultation history."
                ),
                color="warning",
            )

            return

        if (
            chat_session
            is None
        ):

            logger.info(
                (
                    "No previous "
                    "consultation found."
                )
            )

            self._show_empty_state()

            return

        self.session_id = (
            chat_session.id
        )

        self.session_title = (
            chat_session.title
            or "Consultation"
        )

        self._update_session_label()

        try:

            messages = (
                chat_repository
                .get_messages(
                    session_id=(
                        chat_session.id
                    )
                )
            )

        except Exception:

            logger.exception(
                (
                    "Could not restore "
                    "chat messages | "
                    "session_id=%s"
                ),
                self.session_id,
            )

            self._show_empty_state()

            return

        if not messages:

            self._show_empty_state()

            return

        logger.info(
            (
                "Restoring consultation | "
                "session_id=%s | "
                "messages=%s"
            ),
            self.session_id,
            len(messages),
        )

        for message in messages:

            if (
                message.role
                == "user"
            ):

                self._append_user_message(
                    message.content
                )

                continue

            if (
                message.role
                != "assistant"
            ):
                continue

            metadata = (
                chat_repository
                .decode_metadata(
                    message
                )
            )

            self._append_saved_advisor_message(
                text=(
                    message.content
                ),
                metadata=(
                    metadata
                ),
            )

    #
    # USER MESSAGE
    #

    def _append_user_message(
        self,
        text: str,
    ) -> None:

        with self.messages_container:

            with ui.row().classes(
                (
                    "w-full "
                    "justify-end"
                )
            ):

                with (
                    ui.card()
                    .classes(
                        (
                            "q-pa-md "
                            "shadow-none"
                        )
                    )
                    .style(
                        (
                            "max-width: 78%; "
                            "background: "
                            "#29434f !important; "
                            "border: "
                            "1px solid #567887;"
                        )
                    )
                ):

                    ui.label(
                        "YOU"
                    ).classes(
                        (
                            "text-xs "
                            "advisor-subtitle"
                        )
                    )

                    ui.label(
                        text
                    ).classes(
                        (
                            "text-body1 "
                            "whitespace-pre-wrap"
                        )
                    )

    #
    # LOADING MESSAGE
    #

    def _append_loading_message(
        self,
        provider: str,
        model: str,
        web_recon: bool,
    ):

        with self.messages_container:

            with ui.row().classes(
                (
                    "w-full "
                    "justify-start"
                )
            ) as row:

                with (
                    ui.card()
                    .classes(
                        (
                            "q-pa-md "
                            "shadow-none"
                        )
                    )
                    .style(
                        (
                            "max-width: 78%; "
                            "border: "
                            "1px solid #344750;"
                        )
                    )
                ):

                    with ui.row().classes(
                        (
                            "items-center "
                            "gap-3"
                        )
                    ):

                        ui.spinner(
                            size="22px"
                        )

                        with ui.column().classes(
                            "gap-0"
                        ):

                            ui.label(
                                "THE ADVISOR"
                            ).classes(
                                (
                                    "text-xs "
                                    "advisor-subtitle"
                                )
                            )

                            status_label = (
                                ui.label(
                                    (
                                        "Scanning open "
                                        "networks..."
                                        if web_recon
                                        else
                                        (
                                            "Consulting "
                                            "the city "
                                            "archives..."
                                        )
                                    )
                                )
                                .classes(
                                    (
                                        "text-sm "
                                        "advisor-muted"
                                    )
                                )
                            )

                            ui.label(
                                (
                                    f"{provider} / "
                                    f"{model}"
                                )
                            ).classes(
                                (
                                    "text-xs "
                                    "advisor-muted"
                                )
                            )

        return (
            row,
            status_label,
        )

    #
    # ADVISOR MESSAGE
    #

    def _append_advisor_message(
        self,
        result: RagAnswer,
        web_report: (
            AutoResearchReport
            | None
        ),
    ) -> None:

        citations = (
            self._serialize_sources(
                result
            )
        )

        timing = {
            "retrieval": (
                result
                .retrieval_seconds
            ),
            "rerank": (
                result
                .rerank_seconds
            ),
            "generation": (
                result
                .generation_seconds
            ),
            "total": (
                result
                .total_seconds
            ),
        }

        self._render_advisor_message(
            text=(
                result.answer
            ),
            provider=(
                result.provider
            ),
            model=(
                result.model
            ),
            citations=(
                citations
            ),
            timing=(
                timing
            ),
            web_recon=(
                web_report.to_dict()
                if web_report
                else None
            ),
        )

    def _append_saved_advisor_message(
        self,
        text: str,
        metadata: dict,
    ) -> None:

        self._render_advisor_message(
            text=text,
            provider=str(
                metadata.get(
                    "provider",
                    "",
                )
                or ""
            ),
            model=str(
                metadata.get(
                    "model",
                    "",
                )
                or ""
            ),
            citations=(
                metadata.get(
                    "citations"
                )
                or []
            ),
            timing=(
                metadata.get(
                    "timing"
                )
                or {}
            ),
            web_recon=(
                metadata.get(
                    "web_recon"
                )
            ),
        )

    def _render_advisor_message(
        self,
        text: str,
        provider: str,
        model: str,
        citations: list,
        timing: dict,
        web_recon: (
            dict
            | None
        ),
    ) -> None:

        with self.messages_container:

            with ui.row().classes(
                (
                    "w-full "
                    "justify-start"
                )
            ):

                with (
                    ui.card()
                    .classes(
                        (
                            "q-pa-md "
                            "shadow-none"
                        )
                    )
                    .style(
                        (
                            "max-width: 84%; "
                            "border: "
                            "1px solid #344750;"
                        )
                    )
                ):

                    with ui.row().classes(
                        (
                            "w-full "
                            "items-center"
                        )
                    ):

                        ui.label(
                            "THE ADVISOR"
                        ).classes(
                            (
                                "text-xs "
                                "advisor-subtitle"
                            )
                        )

                        ui.space()

                        if (
                            provider
                            or model
                        ):

                            core_text = (
                                " / ".join(
                                    value
                                    for value
                                    in [
                                        provider,
                                        model,
                                    ]
                                    if value
                                )
                            )

                            ui.label(
                                core_text
                            ).classes(
                                (
                                    "text-xs "
                                    "advisor-muted"
                                )
                            )

                    #
                    # WEB RECON
                    #

                    if web_recon:

                        self._render_web_recon(
                            web_recon
                        )

                    #
                    # ANSWER
                    #

                    ui.markdown(
                        text
                    ).classes(
                        "w-full"
                    )

                    #
                    # SOURCES
                    #

                    if citations:

                        with ui.expansion(
                            (
                                "Archive references "
                                f"({len(citations)})"
                            ),
                            icon="inventory_2",
                        ).classes(
                            (
                                "w-full "
                                "q-mt-sm"
                            )
                        ):

                            for source in citations:

                                self._render_source(
                                    source
                                )

                    #
                    # TIMING
                    #

                    if timing:

                        timing_text = (
                            self._format_timing(
                                timing
                            )
                        )

                        if timing_text:

                            ui.label(
                                timing_text
                            ).classes(
                                (
                                    "text-xs "
                                    "advisor-muted "
                                    "q-mt-sm"
                                )
                            )

    #
    # WEB RECON RESULT
    #

    def _render_web_recon(
        self,
        report: dict,
    ) -> None:

        hits_found = int(
            report.get(
                "hits_found",
                0,
            )
            or 0
        )

        indexed_count = int(
            report.get(
                "indexed_count",
                0,
            )
            or 0
        )

        duplicate_count = int(
            report.get(
                "duplicate_count",
                0,
            )
            or 0
        )

        sources = (
            report.get(
                "sources"
            )
            or []
        )

        title = (
            "OPEN WEB RECON "
            f"· {hits_found} discovered "
            f"· {indexed_count} archived"
        )

        if (
            duplicate_count
            > 0
        ):

            title += (
                " · "
                f"{duplicate_count} existing"
            )

        with ui.expansion(
            title,
            icon="travel_explore",
            value=False,
        ).classes(
            (
                "w-full "
                "q-mb-sm"
            )
        ):

            query = (
                report.get(
                    "query"
                )
            )

            if query:

                ui.label(
                    (
                        f"Search: "
                        f"{query}"
                    )
                ).classes(
                    (
                        "text-xs "
                        "advisor-muted"
                    )
                )

            if not sources:

                ui.label(
                    (
                        "No external records "
                        "were archived."
                    )
                ).classes(
                    (
                        "text-xs "
                        "advisor-muted"
                    )
                )

            for source in sources:

                status = (
                    source.get(
                        "status",
                        "unknown",
                    )
                )

                with ui.column().classes(
                    (
                        "w-full "
                        "gap-1 "
                        "q-mt-sm"
                    )
                ):

                    with ui.row().classes(
                        (
                            "items-center "
                            "gap-2"
                        )
                    ):

                        if (
                            status
                            == "indexed"
                        ):

                            color = "positive"

                        elif status in {
                            "duplicate",
                            "skipped",
                        }:

                            color = "warning"

                        else:

                            color = "negative"

                        ui.badge(
                            status.upper(),
                            color=color,
                        )

                        ui.label(
                            (
                                source.get(
                                    "title"
                                )
                                or
                                "Internet source"
                            )
                        ).classes(
                            (
                                "text-sm "
                                "font-medium"
                            )
                        )

                    url = (
                        source.get(
                            "url"
                        )
                    )

                    if url:

                        ui.link(
                            url,
                            url,
                            new_tab=True,
                        ).classes(
                            (
                                "text-xs "
                                "text-primary "
                                "source-uri"
                            )
                        )

                    source_id = (
                        source.get(
                            "source_id"
                        )
                    )

                    if source_id:

                        ui.label(
                            (
                                "Archive source ID: "
                                f"{source_id}"
                            )
                        ).classes(
                            (
                                "text-xs "
                                "advisor-muted"
                            )
                        )

                    error = (
                        source.get(
                            "error"
                        )
                    )

                    if error:

                        error_class = (
                            "text-warning"
                            if status
                            in {
                                "duplicate",
                                "skipped",
                            }
                            else
                            "text-negative"
                        )

                        ui.label(
                            error
                        ).classes(
                            (
                                "text-xs "
                                f"{error_class}"
                            )
                        )

    #
    # ARCHIVE SOURCE
    #

    def _render_source(
        self,
        source: dict,
    ) -> None:

        citation = (
            source.get(
                "citation"
            )
            or "?"
        )

        source_name = (
            source.get(
                "source_name"
            )
            or "Archive record"
        )

        document_title = (
            source.get(
                "document_title"
            )
            or ""
        )

        chunk_index = (
            source.get(
                "chunk_index"
            )
        )

        reference = (
            source.get(
                "reference"
            )
        )

        vector_score = (
            source.get(
                "vector_score"
            )
        )

        rerank_score = (
            source.get(
                "rerank_score"
            )
        )

        with ui.column().classes(
            (
                "w-full "
                "gap-1 "
                "q-mb-sm"
            )
        ):

            with ui.row().classes(
                (
                    "items-center "
                    "gap-2"
                )
            ):

                ui.badge(
                    f"[{citation}]",
                    color="primary",
                )

                ui.label(
                    source_name
                ).classes(
                    (
                        "text-sm "
                        "font-medium"
                    )
                )

            if document_title:

                ui.label(
                    document_title
                ).classes(
                    (
                        "text-xs "
                        "advisor-muted"
                    )
                )

            if (
                chunk_index
                is not None
            ):

                ui.label(
                    (
                        "Archive segment "
                        f"{chunk_index}"
                    )
                ).classes(
                    (
                        "text-xs "
                        "advisor-muted"
                    )
                )

            if reference:

                reference = str(
                    reference
                )

                if reference.startswith(
                    (
                        "http://",
                        "https://",
                    )
                ):

                    ui.link(
                        reference,
                        reference,
                        new_tab=True,
                    ).classes(
                        (
                            "text-xs "
                            "text-primary "
                            "source-uri"
                        )
                    )

                else:

                    ui.label(
                        reference
                    ).classes(
                        (
                            "text-xs "
                            "advisor-muted"
                        )
                    )

            scores = []

            if (
                vector_score
                is not None
            ):

                try:

                    scores.append(
                        (
                            "Vector "
                            f"{float(vector_score):.4f}"
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    pass

            if (
                rerank_score
                is not None
            ):

                try:

                    scores.append(
                        (
                            "Rerank "
                            f"{float(rerank_score):.4f}"
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    pass

            if scores:

                ui.label(
                    (
                        " · ".join(
                            scores
                        )
                    )
                ).classes(
                    (
                        "text-xs "
                        "advisor-muted"
                    )
                )

            ui.separator()

    #
    # ERROR MESSAGE
    #

    def _append_error_message(
        self,
        provider: str,
        model: str,
        error: Exception,
        web_report: (
            AutoResearchReport
            | None
        ),
    ) -> None:

        raw_error = str(
            error
        )

        lowered = (
            raw_error.lower()
        )

        title = (
            "ADVISOR CORE ERROR"
        )

        #
        # 429
        #

        if (
            "429" in raw_error
            or "rate limit"
            in lowered
            or "too_many_requests"
            in lowered
            or "quota exhausted"
            in lowered
            or "quota exceeded"
            in lowered
        ):

            title = (
                "CORE QUOTA EXHAUSTED"
            )

            message = (
                "The selected Advisor core "
                "has reached its request or "
                "quota limit. Select another "
                "core or try again later."
            )

        #
        # 403
        #

        elif (
            "403" in raw_error
            or "access denied"
            in lowered
            or "forbidden"
            in lowered
        ):

            title = (
                "CORE ACCESS DENIED"
            )

            message = (
                "The selected Advisor core "
                "rejected access. Check the "
                "provider account, model "
                "permissions or network "
                "connection."
            )

        #
        # 503
        #

        elif (
            "503" in raw_error
            or "service_unavailable"
            in lowered
            or "service unavailable"
            in lowered
            or "high demand"
            in lowered
            or "temporarily unavailable"
            in lowered
        ):

            title = (
                "CORE TEMPORARILY OVERLOADED"
            )

            message = (
                "The selected Advisor core "
                "is temporarily overloaded. "
                "Automatic retry attempts "
                "were exhausted. Try again "
                "shortly or select another core."
            )

        #
        # TIMEOUT
        #

        elif (
            "timeout" in lowered
            or "timed out"
            in lowered
        ):

            if (
                "gemini api"
                in lowered
                or "groq api"
                in lowered
            ):

                title = (
                    "CORE NETWORK TIMEOUT"
                )

                message = (
                    "The language model did "
                    "not respond in time. "
                    "Automatic retry attempts "
                    "were exhausted."
                )

            else:

                title = (
                    "ARCHIVE NETWORK TIMEOUT"
                )

                message = (
                    "A remote archive service "
                    "did not respond in time. "
                    "Automatic retries were "
                    "exhausted. The request "
                    "can be safely repeated."
                )

        else:

            message = (
                "The Advisor could not "
                "complete the analysis. "
                "Check CITY OPERATIONS LOG "
                "for technical details."
            )

        with self.messages_container:

            with ui.row().classes(
                (
                    "w-full "
                    "justify-start"
                )
            ):

                with (
                    ui.card()
                    .classes(
                        (
                            "q-pa-md "
                            "shadow-none"
                        )
                    )
                    .style(
                        (
                            "max-width: 84%; "
                            "border: "
                            "1px solid #a85b52;"
                        )
                    )
                ):

                    ui.label(
                        title
                    ).classes(
                        (
                            "text-xs "
                            "text-negative"
                        )
                    )

                    #
                    # Web Recon may have succeeded
                    # even if final RAG failed.
                    #

                    if web_report:

                        self._render_web_recon(
                            web_report.to_dict()
                        )

                    ui.label(
                        message
                    ).classes(
                        (
                            "text-sm "
                            "whitespace-pre-wrap"
                        )
                    )

                    ui.label(
                        (
                            f"{provider} / "
                            f"{model}"
                        )
                    ).classes(
                        (
                            "text-xs "
                            "advisor-muted"
                        )
                    )

    #
    # EMPTY STATE
    #

    def _show_empty_state(
        self,
    ) -> None:

        if (
            self.messages_container
            is None
        ):
            return

        with self.messages_container:

            with ui.column().classes(
                (
                    "w-full "
                    "items-center "
                    "justify-center "
                    "q-py-xl"
                )
            ) as empty_state:

                ui.icon(
                    "ac_unit",
                    size="58px",
                ).classes(
                    "advisor-logo"
                )

                ui.label(
                    (
                        "THE ADVISOR AWAITS "
                        "YOUR INQUIRY"
                    )
                ).classes(
                    (
                        "text-lg "
                        "font-medium "
                        "advisor-section-title"
                    )
                )

                ui.label(
                    (
                        "Use the city archives "
                        "or enable OPEN WEB RECON "
                        "to acquire new records."
                    )
                ).classes(
                    (
                        "text-sm "
                        "advisor-muted "
                        "text-center"
                    )
                )

        self.empty_state = (
            empty_state
        )

    def _remove_empty_state(
        self,
    ) -> None:

        if (
            self.empty_state
            is None
        ):
            return

        self.empty_state.delete()

        self.empty_state = None

    def _update_session_label(
        self,
    ) -> None:

        if (
            self.session_label
            is None
        ):
            return

        self.session_label.set_text(
            self.session_title
        )

    #
    # METADATA
    #

    def _build_result_metadata(
        self,
        result: RagAnswer,
        web_report: (
            AutoResearchReport
            | None
        ),
    ) -> dict:

        return {
            "version": 3,

            "provider": (
                result.provider
            ),

            "model": (
                result.model
            ),

            "citations": (
                self._serialize_sources(
                    result
                )
            ),

            "web_recon": (
                web_report.to_dict()
                if web_report
                else None
            ),

            "timing": {
                "retrieval": (
                    result
                    .retrieval_seconds
                ),
                "rerank": (
                    result
                    .rerank_seconds
                ),
                "generation": (
                    result
                    .generation_seconds
                ),
                "total": (
                    result
                    .total_seconds
                ),
            },
        }

    @staticmethod
    def _serialize_sources(
        result: RagAnswer,
    ) -> list[
        dict
    ]:

        serialized = []

        for source in result.sources:

            serialized.append(
                {
                    "citation": (
                        source.citation
                    ),

                    "source_id": (
                        source.source_id
                    ),

                    "document_id": (
                        source.document_id
                    ),

                    "chunk_id": (
                        source.chunk_id
                    ),

                    "source_name": (
                        source.source_name
                    ),

                    "source_type": (
                        source.source_type
                    ),

                    "document_title": (
                        source
                        .document_title
                    ),

                    "chunk_index": (
                        source.chunk_index
                    ),

                    "reference": (
                        source.reference
                    ),

                    "vector_score": (
                        source.vector_score
                    ),

                    "rerank_score": (
                        source.rerank_score
                    ),
                }
            )

        return serialized

    @staticmethod
    def _format_timing(
        timing: dict,
    ) -> str:

        parts = []

        values = [
            (
                "Search",
                timing.get(
                    "retrieval"
                ),
            ),
            (
                "Analysis",
                timing.get(
                    "rerank"
                ),
            ),
            (
                "Core",
                timing.get(
                    "generation"
                ),
            ),
            (
                "Total",
                timing.get(
                    "total"
                ),
            ),
        ]

        for (
            label,
            value,
        ) in values:

            if (
                value
                is None
            ):
                continue

            try:

                parts.append(
                    (
                        f"{label} "
                        f"{float(value):.2f}s"
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

        return (
            " · ".join(
                parts
            )
        )

    #
    # BUSY STATE
    #

    def _set_busy(
        self,
        busy: bool,
    ) -> None:

        self.is_busy = busy

        controls = [
            self.question_input,
            self.send_button,
            self.new_chat_button,
            self.web_recon_checkbox,
            (
                llm_selector
                .provider_select
            ),
            (
                llm_selector
                .model_select
            ),
            (
                llm_selector
                .test_button
            ),
        ]

        for control in controls:

            if (
                control
                is None
            ):
                continue

            if busy:
                control.disable()

            else:
                control.enable()