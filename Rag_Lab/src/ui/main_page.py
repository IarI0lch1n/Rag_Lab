import logging
import shutil

from pathlib import Path
from uuid import uuid4

from nicegui import (
    events,
    run,
    ui,
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

from src.ui.activity_console import (
    activity_console,
)

from src.ui.internet_research_panel import (
    internet_research_panel,
)

from src.ui.rag_chat import (
    RagChat,
)


logger = logging.getLogger(
    "advisor.ui"
)


TEMP_UPLOAD_DIR = Path(
    "data/temp"
)

MAX_UPLOAD_SIZE_MB = 200

MAX_UPLOAD_SIZE_BYTES = (
    MAX_UPLOAD_SIZE_MB
    * 1024
    * 1024
)


def format_file_size(
    size: int | None,
) -> str:

    if size is None:
        return ""

    units = [
        "B",
        "KB",
        "MB",
        "GB",
    ]

    value = float(
        size
    )

    for unit in units:

        if (
            value < 1024
            or unit == units[-1]
        ):

            if unit == "B":
                return (
                    f"{int(value)} "
                    f"{unit}"
                )

            return (
                f"{value:.1f} "
                f"{unit}"
            )

        value /= 1024

    return (
        f"{size} B"
    )


def get_source_display_type(
    source,
) -> str:

    if (
        source.source_type
        == "web"
    ):
        return "Web"

    if (
        source.source_type
        == "git"
    ):
        return "Git"

    if (
        source.source_type
        == "file"
    ):

        if source.file_extension:

            return (
                source
                .file_extension
                .lstrip(".")
                .upper()
            )

        return "File"

    return (
        source
        .source_type
        .capitalize()
    )


def get_source_icon(
    source,
) -> str:

    if (
        source.source_type
        == "web"
    ):
        return "language"

    if (
        source.source_type
        == "git"
    ):
        return "code"

    if (
        source.file_extension
        == ".pdf"
    ):
        return (
            "picture_as_pdf"
        )

    if (
        source.file_extension
        in {
            ".doc",
            ".docx",
        }
    ):
        return "description"

    if (
        source.file_extension
        in {
            ".xls",
            ".xlsx",
            ".csv",
        }
    ):
        return "table_chart"

    if (
        source.file_extension
        in {
            ".ppt",
            ".pptx",
        }
    ):
        return "slideshow"

    return "draft"


def get_status_color(
    status: str,
) -> str:

    colors = {
        "pending": "orange-8",
        "processing": "light-blue-8",
        "indexed": "green-8",
        "completed": "green-8",
        "failed": "red-8",
        "error": "red-8",
    }

    return colors.get(
        status.lower(),
        "blue-grey-7",
    )


def create_main_page() -> None:

    logger.info(
        "Creating Advisor main interface."
    )

    TEMP_UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    #
    # THEME
    #

    ui.colors(
        primary="#8fb8c8",
        secondary="#b58a49",
        accent="#d0ad68",
        dark="#11171b",
        positive="#6f9275",
        negative="#a85b52",
        warning="#c0914d",
        info="#6f929f",
    )

    ui.add_css(
        """
        :root {
            --advisor-bg: #0d1316;
            --advisor-bg-soft: #11191d;
            --advisor-panel: #172126;
            --advisor-panel-soft: #1b272d;
            --advisor-panel-raised: #202d34;

            --advisor-border: #344750;
            --advisor-border-soft: #283940;

            --advisor-text: #dce4e7;
            --advisor-muted: #84969e;

            --advisor-ice: #8fb8c8;
            --advisor-ice-bright: #c3e4ef;

            --advisor-brass: #b58a49;
            --advisor-brass-bright: #d0ad68;

            --advisor-danger: #a85b52;
        }

        html,
        body,
        #app {
            background:
                radial-gradient(
                    circle at 78% 0%,
                    rgba(
                        124,
                        170,
                        188,
                        0.10
                    ),
                    transparent 34%
                ),
                linear-gradient(
                    180deg,
                    #121a1f 0%,
                    #0c1114 100%
                ) !important;

            color:
                var(--advisor-text);
        }

        body {
            font-family:
                "Segoe UI",
                Arial,
                sans-serif;
        }

        .rag-header {
            background:
                linear-gradient(
                    180deg,
                    #1b272d 0%,
                    #121a1e 100%
                ) !important;

            color:
                var(
                    --advisor-text
                ) !important;

            border-bottom:
                1px solid
                var(
                    --advisor-brass
                );

            box-shadow:
                0 4px 20px
                rgba(
                    0,
                    0,
                    0,
                    0.35
                );
        }

        .source-panel {
            background:
                linear-gradient(
                    180deg,
                    #162126 0%,
                    #10171b 100%
                ) !important;

            border-right:
                1px solid
                var(
                    --advisor-border
                );
        }

        .chat-panel {
            background:
                linear-gradient(
                    180deg,
                    #11191d 0%,
                    #0c1215 100%
                ) !important;
        }

        .source-card {
            background:
                linear-gradient(
                    145deg,
                    #1d292f,
                    #162126
                ) !important;

            color:
                var(
                    --advisor-text
                ) !important;

            border:
                1px solid
                var(
                    --advisor-border
                ) !important;

            border-radius:
                3px !important;

            box-shadow:
                inset 0 1px 0
                rgba(
                    255,
                    255,
                    255,
                    0.025
                ),
                0 4px 12px
                rgba(
                    0,
                    0,
                    0,
                    0.12
                )
                !important;
        }

        .source-card:hover {
            border-color:
                var(
                    --advisor-ice
                ) !important;

            box-shadow:
                0 0 0 1px
                rgba(
                    143,
                    184,
                    200,
                    0.08
                ),
                0 8px 24px
                rgba(
                    0,
                    0,
                    0,
                    0.30
                )
                !important;
        }

        .source-uri {
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        .advisor-title {
            color:
                var(
                    --advisor-ice-bright
                ) !important;

            letter-spacing:
                0.15em;

            font-weight:
                700;
        }

        .advisor-subtitle {
            color:
                var(
                    --advisor-brass-bright
                ) !important;

            letter-spacing:
                0.08em;

            text-transform:
                uppercase;
        }

        .advisor-logo {
            color:
                var(
                    --advisor-ice-bright
                ) !important;

            filter:
                drop-shadow(
                    0 0 7px
                    rgba(
                        143,
                        184,
                        200,
                        0.40
                    )
                );
        }

        .advisor-section-title {
            color:
                var(
                    --advisor-text
                ) !important;

            letter-spacing:
                0.08em;

            text-transform:
                uppercase;
        }

        .advisor-muted {
            color:
                var(
                    --advisor-muted
                ) !important;
        }

        .advisor-terminal-label {
            color:
                var(
                    --advisor-brass-bright
                ) !important;

            letter-spacing:
                0.12em;

            text-transform:
                uppercase;
        }

        .q-separator {
            background:
                var(
                    --advisor-border-soft
                ) !important;
        }

        .q-card {
            background:
                var(
                    --advisor-panel
                ) !important;

            color:
                var(
                    --advisor-text
                ) !important;
        }

        .q-field__control {
            background:
                rgba(
                    9,
                    14,
                    17,
                    0.64
                ) !important;

            color:
                var(
                    --advisor-text
                ) !important;
        }

        .q-field__native,
        .q-field__input,
        .q-field__label,
        .q-field__marginal {
            color:
                var(
                    --advisor-text
                ) !important;
        }

        .q-field--outlined
        .q-field__control:before {
            border-color:
                var(
                    --advisor-border
                ) !important;
        }

        .q-field--outlined.q-field--focused
        .q-field__control:after {
            border-color:
                var(
                    --advisor-ice
                ) !important;
        }

        .q-btn {
            letter-spacing:
                0.04em;
        }

        .q-btn.bg-primary {
            background:
                #456c7b
                !important;

            color:
                #eff9fc
                !important;
        }

        .q-btn.text-primary {
            color:
                var(
                    --advisor-ice
                ) !important;
        }

        .q-menu {
            background:
                var(
                    --advisor-panel-soft
                ) !important;

            color:
                var(
                    --advisor-text
                ) !important;

            border:
                1px solid
                var(
                    --advisor-border
                );
        }

        .q-item:hover {
            background:
                rgba(
                    143,
                    184,
                    200,
                    0.08
                ) !important;
        }

        .q-badge {
            border-radius:
                2px !important;
        }

        .q-expansion-item,
        .q-expansion-item__container {
            color:
                var(
                    --advisor-text
                ) !important;
        }

        .text-grey-5,
        .text-grey-6,
        .text-grey-7 {
            color:
                var(
                    --advisor-muted
                ) !important;
        }

        a,
        .text-primary {
            color:
                var(
                    --advisor-ice
                ) !important;
        }

        ::selection {
            background:
                rgba(
                    143,
                    184,
                    200,
                    0.28
                );
        }

        * {
            scrollbar-color:
                #506a75
                #0f171b;
        }

        ::-webkit-scrollbar {
            width: 9px;
            height: 9px;
        }

        ::-webkit-scrollbar-track {
            background:
                #0f171b;
        }

        ::-webkit-scrollbar-thumb {
            background:
                #506a75;

            border:
                2px solid
                #0f171b;
        }
        """
    )

    delete_state = {
        "source_id": None,
    }

    edit_state = {
        "source_id": None,
        "source_type": None,
    }

    #
    # DELETE SOURCE
    #

    with ui.dialog() as delete_dialog:

        with ui.card().classes(
            "w-96"
        ):

            ui.label(
                "Delete archive record?"
            ).classes(
                "text-lg "
                "font-semibold "
                "advisor-section-title"
            )

            delete_source_name = (
                ui.label("")
                .classes(
                    "text-sm "
                    "advisor-muted"
                )
            )

            ui.label(
                (
                    "The source and all "
                    "associated SQL data "
                    "will be permanently "
                    "removed."
                )
            ).classes(
                "text-sm "
                "advisor-muted"
            )

            with ui.row().classes(
                "w-full "
                "justify-end "
                "q-mt-md"
            ):

                ui.button(
                    "Cancel",
                    on_click=(
                        delete_dialog.close
                    ),
                ).props(
                    "flat"
                )

                ui.button(
                    "Delete",
                    color="negative",
                    on_click=lambda:
                    confirm_delete(),
                )

    def open_delete_dialog(
        source_id: int,
        source_name: str,
    ) -> None:

        logger.info(
            (
                "Delete dialog opened | "
                "source_id=%s | "
                "name=%s"
            ),
            source_id,
            source_name,
        )

        delete_state[
            "source_id"
        ] = source_id

        delete_source_name.set_text(
            source_name
        )

        delete_dialog.open()

    def confirm_delete() -> None:

        source_id = (
            delete_state[
                "source_id"
            ]
        )

        if source_id is None:
            return

        logger.info(
            (
                "Archive deletion "
                "requested | "
                "source_id=%s"
            ),
            source_id,
        )

        try:

            source_service.delete_source(
                source_id
            )

            logger.info(
                (
                    "Archive source deleted | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                "Archive record deleted.",
                color="positive",
            )

            delete_dialog.close()

            source_list.refresh()

        except SourceNotFoundError as exc:

            logger.warning(
                (
                    "Archive deletion failed: "
                    "source not found | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                str(exc),
                color="negative",
            )

        except Exception as exc:

            logger.exception(
                (
                    "Archive deletion failed | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                (
                    "Could not delete "
                    "archive record: "
                    f"{exc}"
                ),
                color="negative",
            )

    #
    # ADD URL / GIT SOURCE
    #

    with ui.dialog() as add_url_dialog:

        with ui.card().classes(
            "w-full max-w-xl"
        ):

            ui.label(
                "Add archive source"
            ).classes(
                "text-xl "
                "font-semibold "
                "advisor-section-title"
            )

            ui.label(
                (
                    "Add a website or repository "
                    "to the Advisor's archive. "
                    "GitHub, GitLab and Bitbucket "
                    "repositories are detected "
                    "automatically."
                )
            ).classes(
                "text-sm "
                "advisor-muted"
            )

            url_input = (
                ui.input(
                    label="URL",
                    placeholder=(
                        "https://example.com/docs "
                        "or "
                        "https://github.com/"
                        "user/repository"
                    ),
                )
                .props(
                    "outlined"
                )
                .classes(
                    "w-full "
                    "q-mt-md"
                )
            )

            name_input = (
                ui.input(
                    label=(
                        "Archive name "
                        "(optional)"
                    ),
                )
                .props(
                    "outlined"
                )
                .classes(
                    "w-full"
                )
            )

            with ui.row().classes(
                "w-full "
                "justify-end"
            ):

                ui.button(
                    "Cancel",
                    on_click=(
                        add_url_dialog.close
                    ),
                ).props(
                    "flat"
                )

                ui.button(
                    "Add source",
                    icon="add",
                    on_click=lambda:
                    add_url_source(),
                )

    def add_url_source() -> None:

        url = (
            url_input.value
            or ""
        ).strip()

        name = (
            name_input.value
            or ""
        ).strip()

        if not url:

            ui.notify(
                "Enter a URL.",
                color="warning",
            )

            return

        logger.info(
            (
                "Adding archive URL | "
                "url=%s | "
                "name=%s"
            ),
            url,
            name or "-",
        )

        try:

            source = (
                source_service
                .add_url_source(
                    url=url,
                    name=(
                        name
                        or None
                    ),
                )
            )

            logger.info(
                (
                    "Archive URL added | "
                    "source_id=%s | "
                    "type=%s | "
                    "name=%s"
                ),
                source.id,
                source.source_type,
                source.name,
            )

            ui.notify(
                (
                    f"Added "
                    f"{get_source_display_type(source)} "
                    f"archive source: "
                    f"{source.name}"
                ),
                color="positive",
            )

            url_input.set_value(
                ""
            )

            name_input.set_value(
                ""
            )

            add_url_dialog.close()

            source_list.refresh()

        except DuplicateSourceError as exc:

            logger.warning(
                (
                    "Duplicate archive source | "
                    "url=%s"
                ),
                url,
            )

            ui.notify(
                str(exc),
                color="warning",
            )

        except InvalidSourceError as exc:

            logger.warning(
                (
                    "Invalid archive source | "
                    "url=%s | error=%s"
                ),
                url,
                exc,
            )

            ui.notify(
                str(exc),
                color="negative",
            )

        except Exception as exc:

            logger.exception(
                (
                    "Could not add "
                    "archive source | "
                    "url=%s"
                ),
                url,
            )

            ui.notify(
                (
                    "Could not add "
                    "archive source: "
                    f"{exc}"
                ),
                color="negative",
            )

    #
    # EDIT URL SOURCE
    #

    with ui.dialog() as edit_url_dialog:

        with ui.card().classes(
            "w-full max-w-xl"
        ):

            ui.label(
                "Edit archive source"
            ).classes(
                "text-xl "
                "font-semibold "
                "advisor-section-title"
            )

            edit_url_name_input = (
                ui.input(
                    label="Name"
                )
                .props(
                    "outlined"
                )
                .classes(
                    "w-full"
                )
            )

            edit_url_input = (
                ui.input(
                    label="URL"
                )
                .props(
                    "outlined"
                )
                .classes(
                    "w-full"
                )
            )

            ui.label(
                (
                    "Changing the URL will "
                    "mark this record as "
                    "Pending. Index it again "
                    "afterwards."
                )
            ).classes(
                "text-xs "
                "advisor-muted"
            )

            with ui.row().classes(
                "w-full "
                "justify-end"
            ):

                ui.button(
                    "Cancel",
                    on_click=(
                        edit_url_dialog.close
                    ),
                ).props(
                    "flat"
                )

                ui.button(
                    "Save",
                    icon="save",
                    on_click=lambda:
                    save_url_source(),
                )

    def open_edit_url_dialog(
        source,
    ) -> None:

        edit_state[
            "source_id"
        ] = source.id

        edit_state[
            "source_type"
        ] = source.source_type

        edit_url_name_input.set_value(
            source.name
        )

        edit_url_input.set_value(
            source.uri
            or ""
        )

        edit_url_dialog.open()

    def save_url_source() -> None:

        source_id = (
            edit_state[
                "source_id"
            ]
        )

        if source_id is None:
            return

        logger.info(
            (
                "Updating archive URL | "
                "source_id=%s"
            ),
            source_id,
        )

        try:

            source_service.update_url_source(
                source_id=source_id,
                url=(
                    edit_url_input.value
                    or ""
                ),
                name=(
                    edit_url_name_input.value
                    or ""
                ).strip() or None,
            )

            logger.info(
                (
                    "Archive URL updated | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                (
                    "Archive source updated. "
                    "Index it again to parse "
                    "the new content."
                ),
                color="positive",
            )

            edit_url_dialog.close()

            source_list.refresh()

        except (
            DuplicateSourceError,
            InvalidSourceError,
            SourceNotFoundError,
        ) as exc:

            logger.warning(
                (
                    "Archive URL update "
                    "rejected | "
                    "source_id=%s | "
                    "error=%s"
                ),
                source_id,
                exc,
            )

            ui.notify(
                str(exc),
                color="negative",
            )

        except Exception as exc:

            logger.exception(
                (
                    "Archive URL update "
                    "failed | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                (
                    "Could not update "
                    "archive source: "
                    f"{exc}"
                ),
                color="negative",
            )

    #
    # FILE EDITING
    #

    async def handle_replace_file(
        event:
        events.UploadEventArguments,
    ) -> None:

        source_id = (
            edit_state[
                "source_id"
            ]
        )

        if source_id is None:
            return

        filename = Path(
            event.file.name
        ).name

        upload_directory = (
            TEMP_UPLOAD_DIR
            / uuid4().hex
        )

        upload_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            upload_directory
            / filename
        )

        logger.info(
            (
                "Archive file replacement "
                "started | "
                "source_id=%s | "
                "file=%s"
            ),
            source_id,
            filename,
        )

        try:

            await event.file.save(
                temporary_path
            )

            source_service.replace_file_source(
                source_id=source_id,
                file_path=(
                    temporary_path
                ),
                name=(
                    edit_file_name_input.value
                    or filename
                ).strip(),
            )

            logger.info(
                (
                    "Archive file replaced | "
                    "source_id=%s | "
                    "file=%s"
                ),
                source_id,
                filename,
            )

            ui.notify(
                (
                    "Archive file replaced. "
                    "Index it again to parse "
                    "the new version."
                ),
                color="positive",
            )

            edit_file_dialog.close()

            source_list.refresh()

        except (
            DuplicateSourceError,
            InvalidSourceError,
            SourceNotFoundError,
        ) as exc:

            logger.warning(
                (
                    "File replacement "
                    "rejected | "
                    "source_id=%s | "
                    "error=%s"
                ),
                source_id,
                exc,
            )

            ui.notify(
                str(exc),
                color="negative",
            )

        except Exception as exc:

            logger.exception(
                (
                    "File replacement "
                    "failed | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                (
                    "Could not replace "
                    "archive file: "
                    f"{exc}"
                ),
                color="negative",
            )

        finally:

            shutil.rmtree(
                upload_directory,
                ignore_errors=True,
            )

    def save_file_name() -> None:

        source_id = (
            edit_state[
                "source_id"
            ]
        )

        if source_id is None:
            return

        try:

            source_service.rename_source(
                source_id,
                (
                    edit_file_name_input.value
                    or ""
                ),
            )

            logger.info(
                (
                    "Archive file renamed | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                "Archive record name updated.",
                color="positive",
            )

            edit_file_dialog.close()

            source_list.refresh()

        except Exception as exc:

            logger.exception(
                (
                    "Archive rename failed | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                str(exc),
                color="negative",
            )

    with ui.dialog() as edit_file_dialog:

        with ui.card().classes(
            "w-full max-w-xl"
        ):

            ui.label(
                "Edit archive file"
            ).classes(
                "text-xl "
                "font-semibold "
                "advisor-section-title"
            )

            edit_file_name_input = (
                ui.input(
                    label="Name"
                )
                .props(
                    "outlined"
                )
                .classes(
                    "w-full"
                )
            )

            ui.label(
                (
                    "Rename the archive "
                    "record or replace "
                    "the original file."
                )
            ).classes(
                "text-sm "
                "advisor-muted"
            )

            ui.upload(
                label="Replace file",
                on_upload=(
                    handle_replace_file
                ),
                auto_upload=True,
                max_file_size=(
                    MAX_UPLOAD_SIZE_BYTES
                ),
                on_rejected=lambda:
                ui.notify(
                    (
                        "File rejected. "
                        f"Maximum file size is "
                        f"{MAX_UPLOAD_SIZE_MB} MB."
                    ),
                    color="negative",
                ),
            ).classes(
                "w-full"
            )

            ui.label(
                (
                    "Replacing the file "
                    "will mark this record "
                    "as Pending."
                )
            ).classes(
                "text-xs "
                "advisor-muted"
            )

            with ui.row().classes(
                "w-full "
                "justify-end"
            ):

                ui.button(
                    "Cancel",
                    on_click=(
                        edit_file_dialog.close
                    ),
                ).props(
                    "flat"
                )

                ui.button(
                    "Save name",
                    icon="save",
                    on_click=lambda:
                    save_file_name(),
                )

    def open_edit_file_dialog(
        source,
    ) -> None:

        edit_state[
            "source_id"
        ] = source.id

        edit_state[
            "source_type"
        ] = "file"

        edit_file_name_input.set_value(
            source.name
        )

        edit_file_dialog.open()

    #
    # FILE UPLOAD
    #

    async def handle_file_upload(
        event:
        events.UploadEventArguments,
    ) -> None:

        filename = Path(
            event.file.name
        ).name

        if not filename:

            ui.notify(
                "Invalid file name.",
                color="negative",
            )

            return

        upload_directory = (
            TEMP_UPLOAD_DIR
            / uuid4().hex
        )

        upload_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            upload_directory
            / filename
        )

        logger.info(
            (
                "Archive file upload "
                "started | file=%s"
            ),
            filename,
        )

        try:

            await event.file.save(
                temporary_path
            )

            file_size = (
                temporary_path
                .stat()
                .st_size
            )

            logger.info(
                (
                    "Temporary upload saved | "
                    "file=%s | "
                    "bytes=%s"
                ),
                filename,
                file_size,
            )

            source = (
                source_service
                .add_file_source(
                    temporary_path,
                    name=filename,
                )
            )

            logger.info(
                (
                    "Archive file stored | "
                    "source_id=%s | "
                    "file=%s | "
                    "bytes=%s"
                ),
                source.id,
                filename,
                file_size,
            )

            ui.notify(
                (
                    "Added archive file: "
                    f"{source.name}"
                ),
                color="positive",
            )

            source_list.refresh()

        except DuplicateSourceError as exc:

            logger.warning(
                (
                    "Duplicate archive file | "
                    "file=%s"
                ),
                filename,
            )

            ui.notify(
                str(exc),
                color="warning",
            )

        except InvalidSourceError as exc:

            logger.warning(
                (
                    "Invalid archive file | "
                    "file=%s | "
                    "error=%s"
                ),
                filename,
                exc,
            )

            ui.notify(
                str(exc),
                color="negative",
            )

        except Exception as exc:

            logger.exception(
                (
                    "Archive file upload "
                    "failed | file=%s"
                ),
                filename,
            )

            ui.notify(
                (
                    "Could not add "
                    "archive file: "
                    f"{exc}"
                ),
                color="negative",
            )

        finally:

            shutil.rmtree(
                upload_directory,
                ignore_errors=True,
            )

    with ui.dialog() as upload_dialog:

        with ui.card().classes(
            "w-full max-w-xl"
        ):

            ui.label(
                "Import archive files"
            ).classes(
                "text-xl "
                "font-semibold "
                "advisor-section-title"
            )

            ui.label(
                (
                    "The Advisor detects "
                    "the file type from "
                    "its content and stores "
                    "the original file in "
                    "SQL Server."
                )
            ).classes(
                "text-sm "
                "advisor-muted"
            )

            ui.upload(
                label="Select files",
                on_upload=(
                    handle_file_upload
                ),
                on_rejected=lambda:
                ui.notify(
                    (
                        "File rejected. "
                        f"Maximum file size is "
                        f"{MAX_UPLOAD_SIZE_MB} MB."
                    ),
                    color="negative",
                ),
                multiple=True,
                auto_upload=True,
                max_file_size=(
                    MAX_UPLOAD_SIZE_BYTES
                ),
            ).classes(
                "w-full "
                "q-mt-md"
            )

            with ui.row().classes(
                "w-full "
                "justify-end"
            ):

                ui.button(
                    "Close",
                    on_click=(
                        upload_dialog.close
                    ),
                ).props(
                    "flat"
                )

    #
    # INDEXING
    #

    async def index_source(
        source_id: int,
    ) -> None:

        logger.info(
            (
                "Archive indexing "
                "requested | "
                "source_id=%s"
            ),
            source_id,
        )

        ui.notify(
            "Archive indexing started...",
            color="info",
        )

        try:

            result = await (
                run.io_bound(
                    indexing_service
                    .index_source,
                    source_id,
                )
            )

        except Exception as exc:

            logger.exception(
                (
                    "Archive indexing "
                    "crashed | "
                    "source_id=%s"
                ),
                source_id,
            )

            source_list.refresh()

            ui.notify(
                (
                    "Archive indexing failed: "
                    f"{exc}"
                ),
                color="negative",
                timeout=10000,
            )

            return

        source_list.refresh()

        if (
            result.status
            == "busy"
        ):

            logger.warning(
                (
                    "Archive source already "
                    "being indexed | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                (
                    result.error
                    or
                    "This archive source is "
                    "already being indexed."
                ),
                color="warning",
            )

            return

        if (
            result.status
            == "indexed"
        ):

            logger.info(
                (
                    "Archive indexing "
                    "completed | "
                    "source_id=%s | "
                    "created=%s | "
                    "updated=%s | "
                    "skipped=%s | "
                    "failed=%s | "
                    "chunks=%s"
                ),
                source_id,
                result.documents_created,
                result.documents_updated,
                result.documents_skipped,
                result.documents_failed,
                result.chunks_created,
            )

            message = (
                "Archive indexed successfully. "
                f"Documents: "
                f"{result.documents_created} new, "
                f"{result.documents_updated} updated, "
                f"{result.documents_skipped} unchanged. "
                f"Chunks created: "
                f"{result.chunks_created}."
            )

            if (
                result.documents_failed
                > 0
            ):

                message += (
                    " "
                    f"{result.documents_failed} "
                    "document(s) skipped "
                    "because of errors."
                )

            ui.notify(
                message,
                color="positive",
                timeout=8000,
            )

            return

        logger.error(
            (
                "Archive indexing failed | "
                "source_id=%s | "
                "status=%s | "
                "error=%s"
            ),
            source_id,
            result.status,
            result.error,
        )

        ui.notify(
            (
                "Archive indexing failed: "
                f"{result.error}"
            ),
            color="negative",
            timeout=10000,
        )

    #
    # SOURCE HELPERS
    #

    def open_edit_url_dialog_by_id(
        source_id: int,
    ) -> None:

        try:

            source = (
                source_service
                .get_source(
                    source_id
                )
            )

            open_edit_url_dialog(
                source
            )

        except Exception as exc:

            logger.exception(
                (
                    "Could not load "
                    "archive URL source | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                (
                    "Could not load "
                    "archive source: "
                    f"{exc}"
                ),
                color="negative",
            )

    def open_edit_file_dialog_by_id(
        source_id: int,
    ) -> None:

        try:

            source = (
                source_service
                .get_source(
                    source_id
                )
            )

            open_edit_file_dialog(
                source
            )

        except Exception as exc:

            logger.exception(
                (
                    "Could not load "
                    "archive file | "
                    "source_id=%s"
                ),
                source_id,
            )

            ui.notify(
                (
                    "Could not load "
                    "archive source: "
                    f"{exc}"
                ),
                color="negative",
            )

    #
    # SOURCE LIST
    #
    # IMPORTANT:
    # this is defined BEFORE Internet Recon
    # is rendered.
    #

    @ui.refreshable
    def source_list() -> None:

        try:

            sources = (
                source_service
                .get_sources()
            )

        except Exception as exc:

            logger.exception(
                "Could not load archive sources."
            )

            ui.label(
                "Could not load the archive."
            ).classes(
                "text-negative "
                "font-medium"
            )

            ui.label(
                str(exc)
            ).classes(
                "text-xs "
                "advisor-muted"
            )

            return

        logger.info(
            (
                "Archive view refreshed | "
                "sources=%s"
            ),
            len(sources),
        )

        if not sources:

            with ui.column().classes(
                "w-full "
                "items-center "
                "q-pa-lg"
            ):

                ui.icon(
                    "inventory_2",
                    size="48px",
                ).classes(
                    "advisor-logo"
                )

                ui.label(
                    "No archive records"
                ).classes(
                    "font-medium "
                    "advisor-section-title"
                )

                ui.label(
                    (
                        "Add a website, "
                        "Git repository or "
                        "file to begin building "
                        "the archive."
                    )
                ).classes(
                    "text-xs "
                    "advisor-muted "
                    "text-center"
                )

            return

        for source in sources:

            with ui.card().classes(
                "source-card "
                "w-full "
                "q-pa-sm "
                "shadow-none"
            ):

                with ui.row().classes(
                    "w-full "
                    "no-wrap "
                    "items-start"
                ):

                    with ui.avatar(
                        color=(
                            "blue-grey-10"
                        ),
                        text_color=(
                            "blue-grey-1"
                        ),
                        size="40px",
                    ):

                        ui.icon(
                            get_source_icon(
                                source
                            )
                        )

                    with ui.column().classes(
                        "col "
                        "q-gutter-none"
                    ):

                        ui.label(
                            source.name
                        ).classes(
                            "font-medium "
                            "text-sm"
                        )

                        with ui.row().classes(
                            "items-center "
                            "q-gutter-xs "
                            "q-mt-xs"
                        ):

                            ui.badge(
                                get_source_display_type(
                                    source
                                ),
                                color=(
                                    "blue-grey-9"
                                ),
                                text_color=(
                                    "blue-grey-2"
                                ),
                            )

                            ui.badge(
                                source
                                .status
                                .capitalize(),
                                color=(
                                    get_status_color(
                                        source.status
                                    )
                                ),
                            )

                            if (
                                source.status
                                == "failed"
                                and
                                source.last_error
                            ):

                                ui.icon(
                                    "error_outline",
                                    size="16px",
                                ).classes(
                                    "text-negative "
                                    "cursor-help"
                                ).tooltip(
                                    source.last_error
                                )

                            if (
                                source.source_type
                                == "file"
                                and
                                source.file_size_bytes
                            ):

                                ui.label(
                                    format_file_size(
                                        source
                                        .file_size_bytes
                                    )
                                ).classes(
                                    "text-xs "
                                    "advisor-muted"
                                )

                        if source.uri:

                            ui.link(
                                source.uri,
                                source.uri,
                                new_tab=True,
                            ).classes(
                                "source-uri "
                                "text-xs "
                                "text-primary "
                                "q-mt-xs"
                            )

                        elif (
                            source
                            .original_filename
                        ):

                            ui.label(
                                source
                                .original_filename
                            ).classes(
                                "text-xs "
                                "advisor-muted "
                                "q-mt-xs"
                            )

                    #
                    # Edit
                    #

                    if (
                        source.source_type
                        == "file"
                    ):

                        ui.button(
                            icon="edit",
                            on_click=(
                                lambda
                                source_id=source.id:
                                open_edit_file_dialog_by_id(
                                    source_id
                                )
                            ),
                        ).props(
                            "flat "
                            "round "
                            "dense"
                        ).tooltip(
                            "Edit archive record"
                        )

                    else:

                        ui.button(
                            icon="edit",
                            on_click=(
                                lambda
                                source_id=source.id:
                                open_edit_url_dialog_by_id(
                                    source_id
                                )
                            ),
                        ).props(
                            "flat "
                            "round "
                            "dense"
                        ).tooltip(
                            "Edit archive record"
                        )

                    #
                    # Index
                    #

                    if (
                        source.source_type
                        in {
                            "file",
                            "web",
                            "git",
                        }
                    ):

                        index_button = (
                            ui.button(
                                icon=(
                                    "refresh"
                                    if (
                                        source.status
                                        == "indexed"
                                    )
                                    else
                                    "play_arrow"
                                ),
                                on_click=(
                                    lambda
                                    source_id=source.id:
                                    index_source(
                                        source_id
                                    )
                                ),
                            )
                            .props(
                                "flat "
                                "round "
                                "dense"
                            )
                            .classes(
                                "text-primary"
                            )
                        )

                        index_button.tooltip(
                            (
                                "Re-index archive record"
                                if (
                                    source.status
                                    == "indexed"
                                )
                                else
                                "Index archive record"
                            )
                        )

                        if (
                            source.status
                            == "processing"
                        ):

                            index_button.disable()

                    #
                    # Delete
                    #

                    ui.button(
                        icon="delete_outline",
                        on_click=(
                            lambda
                            source_id=source.id,
                            source_name=source.name:
                            open_delete_dialog(
                                source_id,
                                source_name,
                            )
                        ),
                    ).props(
                        "flat "
                        "round "
                        "dense"
                    ).tooltip(
                        "Delete archive record"
                    )

    #
    # MAIN HEADER
    #

    with ui.header(
        elevated=False,
    ).classes(
        "rag-header h-16"
    ):

        with ui.row().classes(
            "w-full "
            "items-center "
            "q-px-md "
            "gap-3"
        ):

            ui.icon(
                "ac_unit",
                size="30px",
            ).classes(
                "advisor-logo"
            )

            ui.label(
                "THE ADVISOR"
            ).classes(
                "text-xl "
                "advisor-title"
            )

            ui.label(
                (
                    "CITY ARCHIVE "
                    "ANALYSIS SYSTEM"
                )
            ).classes(
                "text-xs "
                "advisor-subtitle"
            )

            ui.space()

            ui.label(
                "CITY ARCHIVE TERMINAL"
            ).classes(
                "text-xs "
                "advisor-terminal-label"
            )

    #
    # MAIN BODY
    #

    with ui.row().classes(
        "w-full no-wrap"
    ).style(
        "height: "
        "calc(100vh - 64px);"
    ):

        #
        # LEFT PANEL
        #

        with ui.column().classes(
            "source-panel "
            "q-pa-md "
            "q-gutter-sm"
        ).style(
            "width: 400px; "
            "min-width: 340px; "
            "height: 100%; "
            "overflow-y: auto;"
        ):

            with ui.row().classes(
                "w-full "
                "items-center"
            ):

                ui.label(
                    "CITY ARCHIVES"
                ).classes(
                    "text-xl "
                    "font-semibold "
                    "advisor-section-title"
                )

                ui.space()

                ui.button(
                    icon="refresh",
                    on_click=(
                        source_list.refresh
                    ),
                ).props(
                    "flat "
                    "round "
                    "dense"
                ).tooltip(
                    "Refresh archive"
                )

            ui.label(
                (
                    "Indexed records available "
                    "to the Advisor."
                )
            ).classes(
                "text-xs "
                "advisor-muted"
            )

            with ui.row().classes(
                "w-full "
                "q-mt-sm"
            ):

                ui.button(
                    "Add source",
                    icon="add_link",
                    on_click=(
                        add_url_dialog.open
                    ),
                ).classes(
                    "col"
                )

                ui.button(
                    "Upload file",
                    icon="upload_file",
                    on_click=(
                        upload_dialog.open
                    ),
                ).props(
                    "outline"
                ).classes(
                    "col"
                )

            ui.separator().classes(
                "q-my-sm"
            )

            #
            # INTERNET RECON
            #

            internet_research_panel.render(
                on_archive_changed=(
                    source_list.refresh
                )
            )

            ui.separator().classes(
                "q-my-sm"
            )

            #
            # EXISTING ARCHIVE
            #

            source_list()

        #
        # RIGHT PANEL
        #

        rag_chat = RagChat()

        with ui.column().classes(
            "chat-panel "
            "col "
            "h-full"
        ).style(
            "min-width: 0;"
        ):

            with ui.column().classes(
                "w-full "
                "q-pa-lg "
                "q-pb-md"
            ):

                ui.label(
                    "THE ADVISOR"
                ).classes(
                    "text-xl "
                    "font-semibold "
                    "advisor-section-title"
                )

                ui.label(
                    (
                        "Consult the archive, "
                        "monitor system operations "
                        "and request analysis from "
                        "indexed records."
                    )
                ).classes(
                    "text-sm "
                    "advisor-muted"
                )

            ui.separator()

            #
            # CITY OPERATIONS LOG
            #

            with ui.column().classes(
                "w-full "
                "q-px-md "
                "q-pt-sm"
            ):

                activity_console.render()

            ui.separator().classes(
                "q-mt-sm"
            )

            #
            # ADVISOR CHAT
            #

            with ui.column().classes(
                "col "
                "w-full"
            ).style(
                "min-height: 0;"
            ):

                rag_chat.render()

    logger.info(
        "Advisor main interface ready."
    )