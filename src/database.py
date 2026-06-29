"""SQLite database layer for storing and querying PMI tracking data."""

import logging
import sqlite3
from typing import Any

from src.field_mapper import (
    FIELD_BRIEF,
    FIELD_COMPONENT,
    FIELD_GENERIC02,
    FIELD_GENERIC03,
    FIELD_GENERIC04,
    FIELD_GENERIC05,
    FIELD_ID,
    FIELD_PROBABILITY,
    FIELD_PROJECT,
    FIELD_RECORD_TYPE,
    FIELD_RISK,
    FIELD_SCORE,
    FIELD_SEVERITY,
    FIELD_SOURCE,
    FIELD_STATUS,
)

logger = logging.getLogger(__name__)

TABLE_DEFECTS = "defects"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_DEFECTS} (
    {FIELD_SOURCE}      TEXT NOT NULL,
    {FIELD_PROJECT}     TEXT,
    {FIELD_RECORD_TYPE} TEXT,
    {FIELD_ID}          TEXT NOT NULL,
    {FIELD_BRIEF}       TEXT,
    {FIELD_COMPONENT}   TEXT,
    {FIELD_SEVERITY}    TEXT,
    {FIELD_STATUS}      TEXT,
    {FIELD_GENERIC02}   TEXT,
    {FIELD_GENERIC03}   TEXT,
    {FIELD_GENERIC04}   TEXT,
    {FIELD_GENERIC05}   TEXT,
    {FIELD_SCORE}       REAL,
    {FIELD_PROBABILITY} REAL,
    {FIELD_RISK}        REAL,
    PRIMARY KEY ({FIELD_SOURCE}, {FIELD_ID})
)
"""

UPSERT_SQL = f"""
INSERT INTO {TABLE_DEFECTS} (
    {FIELD_SOURCE}, {FIELD_PROJECT}, {FIELD_RECORD_TYPE}, {FIELD_ID},
    {FIELD_BRIEF}, {FIELD_COMPONENT}, {FIELD_SEVERITY}, {FIELD_STATUS},
    {FIELD_GENERIC02}, {FIELD_GENERIC03}, {FIELD_GENERIC04}, {FIELD_GENERIC05},
    {FIELD_SCORE}, {FIELD_PROBABILITY}, {FIELD_RISK}
) VALUES (
    :source, :project, :record_type, :id,
    :brief, :component, :severity, :status,
    :generic02, :generic03, :generic04, :generic05,
    :score, :probability, :risk
)
ON CONFLICT({FIELD_SOURCE}, {FIELD_ID}) DO UPDATE SET
    {FIELD_PROJECT}     = excluded.{FIELD_PROJECT},
    {FIELD_RECORD_TYPE} = excluded.{FIELD_RECORD_TYPE},
    {FIELD_BRIEF}       = excluded.{FIELD_BRIEF},
    {FIELD_COMPONENT}   = excluded.{FIELD_COMPONENT},
    {FIELD_SEVERITY}    = excluded.{FIELD_SEVERITY},
    {FIELD_STATUS}      = excluded.{FIELD_STATUS},
    {FIELD_GENERIC02}   = excluded.{FIELD_GENERIC02},
    {FIELD_GENERIC03}   = excluded.{FIELD_GENERIC03},
    {FIELD_GENERIC04}   = excluded.{FIELD_GENERIC04},
    {FIELD_GENERIC05}   = excluded.{FIELD_GENERIC05},
    {FIELD_SCORE}       = excluded.{FIELD_SCORE},
    {FIELD_PROBABILITY} = excluded.{FIELD_PROBABILITY},
    {FIELD_RISK}        = excluded.{FIELD_RISK}
"""


class Database:
    """SQLite-backed storage for combined ADS and ClearQuest defect records."""

    def __init__(self, db_path: str = "pmi_tracking.db"):
        """Open (or create) the SQLite database and ensure the schema exists.

        Args:
            db_path: Path to the SQLite database file.
                     Use ``":memory:"`` for an in-memory database.
        """
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        """Create the defects table if it does not already exist."""
        with self._conn:
            self._conn.execute(CREATE_TABLE_SQL)

    def upsert_records(self, records: list[dict[str, Any]]) -> int:
        """Insert or update records in the defects table.

        Args:
            records: List of common-schema dictionaries (output of field_mapper).

        Returns:
            Number of rows affected.
        """
        with self._conn:
            cursor = self._conn.executemany(UPSERT_SQL, records)
        affected = cursor.rowcount
        logger.info("Upserted %d records into '%s'.", affected, TABLE_DEFECTS)
        return affected

    def query_all(self) -> list[dict[str, Any]]:
        """Return all records from the defects table.

        Returns:
            List of row dictionaries.
        """
        cursor = self._conn.execute(f"SELECT * FROM {TABLE_DEFECTS}")
        return [dict(row) for row in cursor.fetchall()]

    def query_by_source(self, source: str) -> list[dict[str, Any]]:
        """Return records filtered by source system.

        Args:
            source: Source identifier (``"ADS"`` or ``"ClearQuest"``).

        Returns:
            List of matching row dictionaries.
        """
        cursor = self._conn.execute(
            f"SELECT * FROM {TABLE_DEFECTS} WHERE {FIELD_SOURCE} = ?", (source,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def query_open_defects(self, closed_statuses: list[str]) -> list[dict[str, Any]]:
        """Return records whose status is not in the closed statuses list.

        Args:
            closed_statuses: List of status values that indicate a closed record.

        Returns:
            List of open defect dictionaries.
        """
        placeholders = ",".join("?" * len(closed_statuses))
        cursor = self._conn.execute(
            f"SELECT * FROM {TABLE_DEFECTS} "
            f"WHERE {FIELD_STATUS} NOT IN ({placeholders}) "
            f"OR {FIELD_STATUS} IS NULL",
            closed_statuses,
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
