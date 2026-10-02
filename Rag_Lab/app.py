import logging

from nicegui import (
    ui,
)

from sqlalchemy import (
    inspect,
)

import src.db.models

from src.config import (
    settings,
)

from src.db.base import (
    Base,
)

from src.db.session import (
    engine,
    test_database_connection,
)

from src.logging_config import (
    setup_logging,
)

from src.observability.langfuse_service import (
    langfuse_service,
)

from src.ui.main_page import (
    create_main_page,
)

from src.vector_store.qdrant_store import (
    qdrant_store,
)


setup_logging()


logger = logging.getLogger(
    "advisor.application"
)


def initialize_database(
) -> tuple[
    bool,
    str,
]:

    logger.info(
        (
            "Initializing SQL "
            "Server schema."
        )
    )

    try:

        Base.metadata.create_all(
            bind=engine
        )

        inspector = (
            inspect(
                engine
            )
        )

        tables = (
            inspector
            .get_table_names()
        )

        message = (
            "Database schema initialized. "
            f"Tables: "
            f"{', '.join(sorted(tables))}"
        )

        logger.info(
            message
        )

        return (
            True,
            message,
        )

    except Exception as exc:

        logger.exception(
            (
                "Database schema "
                "initialization failed."
            )
        )

        return (
            False,
            str(exc),
        )


def initialize_application(
) -> bool:

    logger.info(
        (
            "Advisor application "
            "initialization started."
        )
    )

    print()
    print(
        "=" * 70
    )

    print(
        (
            f"{settings.app_name} "
            "- Initialization"
        )
    )

    print(
        "=" * 70
    )

    #
    # SQL SERVER
    #

    print()
    print(
        "Testing Microsoft SQL Server..."
    )

    (
        sql_success,
        sql_message,
    ) = (
        test_database_connection()
    )

    if sql_success:

        print(
            f"[OK] {sql_message}"
        )

        logger.info(
            (
                "SQL Server connection "
                "successful | %s"
            ),
            sql_message,
        )

    else:

        print(
            (
                "[ERROR] SQL Server "
                "connection failed:"
            )
        )

        print(
            sql_message
        )

        logger.error(
            (
                "SQL Server connection "
                "failed | %s"
            ),
            sql_message,
        )

    #
    # QDRANT
    #

    print()
    print(
        "Testing Qdrant..."
    )

    (
        qdrant_success,
        qdrant_message,
    ) = (
        qdrant_store
        .test_connection()
    )

    if qdrant_success:

        print(
            (
                f"[OK] "
                f"{qdrant_message}"
            )
        )

        logger.info(
            (
                "Qdrant connection "
                "successful | %s"
            ),
            qdrant_message,
        )

    else:

        print(
            (
                "[ERROR] Qdrant "
                "connection failed:"
            )
        )

        print(
            qdrant_message
        )

        logger.error(
            (
                "Qdrant connection "
                "failed | %s"
            ),
            qdrant_message,
        )

    #
    # LANGFUSE PUBLIC API
    #

    print()
    print(
        "Testing Langfuse API..."
    )

    if (
        settings
        .langfuse_enabled
    ):

        (
            langfuse_success,
            langfuse_message,
        ) = (
            langfuse_service
            .test_connection()
        )

        if langfuse_success:

            print(
                (
                    f"[OK] "
                    f"{langfuse_message}"
                )
            )

            logger.info(
                (
                    "Langfuse API "
                    "connection successful | %s"
                ),
                langfuse_message,
            )

        else:

            print(
                (
                    "[ERROR] Langfuse API "
                    "connection failed:"
                )
            )

            print(
                langfuse_message
            )

            logger.error(
                (
                    "Langfuse API "
                    "connection failed | %s"
                ),
                langfuse_message,
            )

    else:

        langfuse_success = (
            not settings
            .langfuse_required
        )

        langfuse_message = (
            "Langfuse is disabled."
        )

        print(
            (
                "[WARNING] "
                f"{langfuse_message}"
            )
        )

        logger.warning(
            langfuse_message
        )

    #
    # DATABASE SCHEMA
    #

    db_success = False

    if sql_success:

        print()
        print(
            (
                "Initializing SQL "
                "Server schema..."
            )
        )

        (
            db_success,
            db_message,
        ) = (
            initialize_database()
        )

        if db_success:

            print(
                (
                    f"[OK] "
                    f"{db_message}"
                )
            )

        else:

            print(
                (
                    "[ERROR] Database "
                    "initialization failed:"
                )
            )

            print(
                db_message
            )

    else:

        logger.warning(
            (
                "Database schema "
                "initialization skipped "
                "because SQL Server "
                "is unavailable."
            )
        )

    #
    # RESULT
    #

    langfuse_ready = (
        langfuse_success
        or not settings
        .langfuse_required
    )

    ready = (
        sql_success
        and qdrant_success
        and db_success
        and langfuse_ready
    )

    print()
    print(
        "=" * 70
    )

    if ready:

        print(
            (
                "Application infrastructure "
                "is ready."
            )
        )

        logger.info(
            (
                "Advisor application "
                "infrastructure is ready."
            )
        )

    else:

        print(
            (
                "One or more "
                "initialization steps failed."
            )
        )

        logger.error(
            (
                "Advisor application "
                "initialization failed | "
                "sql=%s | "
                "qdrant=%s | "
                "database=%s | "
                "langfuse=%s"
            ),
            sql_success,
            qdrant_success,
            db_success,
            langfuse_success,
        )

    print(
        "=" * 70
    )

    print()

    return ready


def run_application(
) -> None:

    if not (
        initialize_application()
    ):

        raise SystemExit(
            (
                "Application "
                "initialization failed."
            )
        )

    logger.info(
        (
            "Creating Advisor "
            "user interface."
        )
    )

    create_main_page()

    logger.info(
        (
            "Starting NiceGUI "
            "web server."
        )
    )

    try:

        ui.run(
            title="The Advisor",
            host="127.0.0.1",
            port=8080,
            reload=False,
            show=True,
        )

    finally:

        langfuse_service.shutdown()


if __name__ == "__main__":

    run_application()