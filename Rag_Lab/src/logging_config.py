import logging

from logging.handlers import (
    RotatingFileHandler,
)

from pathlib import Path


from src.observability.activity import (
    ActivityLogHandler,
    install_console_mirror,
)


LOG_DIR = Path("logs")

APP_LOG = (
    LOG_DIR
    / "advisor.log"
)

ERROR_LOG = (
    LOG_DIR
    / "advisor_errors.log"
)


def setup_logging() -> None:

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    root_logger = (
        logging.getLogger()
    )

    if getattr(
        root_logger,
        "_advisor_configured",
        False,
    ):
        return

    root_logger.setLevel(
        logging.INFO
    )

    formatter = logging.Formatter(
        (
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)s | "
            "%(message)s"
        ),
        datefmt=(
            "%Y-%m-%d "
            "%H:%M:%S"
        ),
    )

    #
    # Console
    #
    console_handler = (
        logging.StreamHandler()
    )

    console_handler.setLevel(
        logging.INFO
    )

    console_handler.setFormatter(
        formatter
    )

    #
    # General log
    #
    app_handler = (
        RotatingFileHandler(
            APP_LOG,
            maxBytes=(
                10
                * 1024
                * 1024
            ),
            backupCount=5,
            encoding="utf-8",
        )
    )

    app_handler.setLevel(
        logging.INFO
    )

    app_handler.setFormatter(
        formatter
    )

    #
    # Errors only
    #
    error_handler = (
        RotatingFileHandler(
            ERROR_LOG,
            maxBytes=(
                10
                * 1024
                * 1024
            ),
            backupCount=5,
            encoding="utf-8",
        )
    )

    error_handler.setLevel(
        logging.ERROR
    )

    error_handler.setFormatter(
        formatter
    )

    #
    # UI activity feed
    #
    activity_handler = (
        ActivityLogHandler()
    )

    activity_handler.setLevel(
        logging.INFO
    )

    root_logger.addHandler(
        console_handler
    )

    root_logger.addHandler(
        app_handler
    )

    root_logger.addHandler(
        error_handler
    )

    root_logger.addHandler(
        activity_handler
    )

    #
    # Existing print-based pipeline
    # also becomes visible in UI.
    #
    install_console_mirror()

    #
    # Reduce third-party noise.
    #
    logging.getLogger(
        "httpx"
    ).setLevel(
        logging.WARNING
    )

    logging.getLogger(
        "httpcore"
    ).setLevel(
        logging.WARNING
    )

    logging.getLogger(
        "urllib3"
    ).setLevel(
        logging.WARNING
    )

    logging.getLogger(
        "sqlalchemy.engine"
    ).setLevel(
        logging.WARNING
    )

    root_logger._advisor_configured = (
        True
    )

    logging.getLogger(
        "advisor.system"
    ).info(
        "The Advisor system initialized."
    )