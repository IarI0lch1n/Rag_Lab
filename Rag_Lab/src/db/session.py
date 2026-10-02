from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from src.config import settings


def build_connection_string() -> str:
    parts = [
        f"DRIVER={{{settings.mssql_driver}}}",
        f"SERVER={settings.mssql_server}",
        f"DATABASE={settings.mssql_database}",
        f"TrustServerCertificate={'yes' if settings.mssql_trust_server_certificate else 'no'}",
    ]

    if settings.mssql_trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend([
            f"UID={settings.mssql_username}",
            f"PWD={settings.mssql_password}",
        ])

    return ";".join(parts)


connection_url = URL.create(
    "mssql+pyodbc",
    query={
        "odbc_connect": build_connection_string()
    },
)


engine = create_engine(
    connection_url,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def test_database_connection() -> tuple[bool, str]:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT
                        DB_NAME() AS database_name,
                        @@SERVERNAME AS server_name,
                        @@VERSION AS server_version
                    """
                )
            ).mappings().one()

        message = (
            f"Connected to SQL Server "
            f"'{result['server_name']}', "
            f"database '{result['database_name']}'"
        )

        return True, message

    except Exception as exc:
        return False, str(exc)