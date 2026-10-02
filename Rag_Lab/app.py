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

from src.ui.main_page import (
    create_main_page,
)

from src.vector_store.qdrant_store import (
    qdrant_store,
)


#
# Initialize logging once, before
# application infrastructure checks.
#

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

    logger.info(
        (
            "Testing Microsoft "
            "SQL Server connection."
        )
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

    logger.info(
        (
            "Testing Qdrant "
            "connection."
        )
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

    print()
    print(
        "=" * 70
    )

    ready = (
        sql_success
        and qdrant_success
        and db_success
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
                "database=%s"
            ),
            sql_success,
            qdrant_success,
            db_success,
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

    ui.run(
        title="The Advisor",
        host="127.0.0.1",
        port=8080,

        #
        # Important on Windows:
        # disabling reload prevents
        # the application initialization
        # sequence from running twice.
        #
        reload=False,

        show=True,
    )


if __name__ == "__main__":

    run_application()