import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine
from databricks.sdk import WorkspaceClient


def _get_database_credential() -> str:
    """Generate a fresh OAuth credential for the Lakebase endpoint."""
    endpoint_name = os.environ.get("ENDPOINT_NAME")

    if not endpoint_name:
        raise ValueError(
            "Missing ENDPOINT_NAME environment variable. "
            "Expected the Lakebase endpoint resource name."
        )

    workspace_client = WorkspaceClient()
    credential = workspace_client.postgres.generate_database_credential(
        endpoint=endpoint_name
    )

    return credential.token


def _connection_parameters() -> dict:
    """Build PostgreSQL connection parameters from Databricks App variables."""
    host = os.environ.get("PGHOST")
    port = os.environ.get("PGPORT", "5432")
    database = os.environ.get("PGDATABASE")
    user = os.environ.get("PGUSER")
    sslmode = os.environ.get("PGSSLMODE", "require")

    if not all([host, database, user]):
        raise ValueError(
            "Missing required Lakebase environment variables. "
            "Expected PGHOST, PGDATABASE, and PGUSER."
        )

    return {
        "host": host,
        "port": port,
        "dbname": database,
        "user": user,
        "sslmode": sslmode,
    }


def _connect():
    """Create a new PostgreSQL connection with a fresh OAuth credential."""
    params = _connection_parameters()
    params["password"] = _get_database_credential()

    return psycopg2.connect(
        **params,
        cursor_factory=RealDictCursor,
    )


@contextmanager
def get_connection():
    """Yield a raw psycopg2 connection."""
    conn = _connect()

    try:
        yield conn
    finally:
        conn.close()


def get_engine():
    """Return a SQLAlchemy engine using OAuth-authenticated connections."""
    return create_engine(
        "postgresql+psycopg2://",
        creator=_connect,
        pool_pre_ping=True,
        pool_recycle=3300,
    )


def run_query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    """Run a read query against Lakebase and return rows as dictionaries."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def run_write(sql: str, params: tuple | dict | None = None) -> int:
    """Run an INSERT/UPDATE/DELETE against Lakebase."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount