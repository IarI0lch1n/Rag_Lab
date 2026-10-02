from sqlalchemy import inspect
from nicegui import ui

import src.db.models

from src.config import settings
from src.db.base import Base
from src.db.session import (
    engine,
    test_database_connection,
)
from src.ui.main_page import create_main_page
from src.vector_store.qdrant_store import qdrant_store

from src.logging_config import (
    setup_logging,
)

def initialize_database() -> tuple[bool, str]:
    try:
        Base.metadata.create_all(
            bind=engine
        )

        inspector = inspect(engine)

        tables = inspector.get_table_names()

        return (
            True,
            (
                "Database schema initialized. "
                f"Tables: {', '.join(sorted(tables))}"
            ),
        )

    except Exception as exc:
        return False, str(exc)

setup_logging()

def initialize_application() -> bool:
    print()
    print("=" * 70)
    print(
        f"{settings.app_name} - Initialization"
    )
    print("=" * 70)

    print()
    print(
        "Testing Microsoft SQL Server..."
    )

    sql_success, sql_message = (
        test_database_connection()
    )

    if sql_success:
        print(
            f"[OK] {sql_message}"
        )
    else:
        print(
            "[ERROR] SQL Server connection failed:"
        )
        print(
            sql_message
        )

    print()
    print(
        "Testing Qdrant..."
    )

    qdrant_success, qdrant_message = (
        qdrant_store.test_connection()
    )

    if qdrant_success:
        print(
            f"[OK] {qdrant_message}"
        )
    else:
        print(
            "[ERROR] Qdrant connection failed:"
        )
        print(
            qdrant_message
        )

    db_success = False

    if sql_success:
        print()
        print(
            "Initializing SQL Server schema..."
        )

        db_success, db_message = (
            initialize_database()
        )

        if db_success:
            print(
                f"[OK] {db_message}"
            )
        else:
            print(
                "[ERROR] Database initialization failed:"
            )
            print(
                db_message
            )

    print()
    print("=" * 70)

    ready = (
        sql_success
        and qdrant_success
        and db_success
    )

    if ready:
        print(
            "Application infrastructure is ready."
        )
    else:
        print(
            "One or more initialization steps failed."
        )

    print("=" * 70)
    print()

    return ready


if __name__ in {
    "__main__",
    "__mp_main__",
}:
    if not initialize_application():
        raise SystemExit(
            "Application initialization failed."
        )

    setup_logging()

    create_main_page()

    ui.run(
        title="The Advisor",
        host="127.0.0.1",
        port=8080,
        reload=False,
        show=True,
    )