"""Postgres access for the central index. Owner: lead."""

from collections.abc import Iterator
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from central.config import get_settings

SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().central_database_url, row_factory=dict_row, autocommit=True)


def apply_schema() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)


def get_conn() -> Iterator[psycopg.Connection]:
    """FastAPI dependency: one short-lived connection per request."""
    with connect() as conn:
        yield conn
