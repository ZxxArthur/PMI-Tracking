"""ClearQuest connector for fetching PD and EI defect records."""

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ClearQuest REST API field name constants
CQ_FIELD_ID = "id"
CQ_FIELD_HEADLINE = "headline"
CQ_FIELD_COMPONENT = "component"
CQ_FIELD_STATE = "state"
CQ_FIELD_SCORE = "score"
CQ_FIELD_PROBABILITY = "probability"

DEFAULT_FIELDS = [
    CQ_FIELD_ID,
    CQ_FIELD_HEADLINE,
    CQ_FIELD_COMPONENT,
    CQ_FIELD_STATE,
    CQ_FIELD_SCORE,
    CQ_FIELD_PROBABILITY,
]


class ClearQuestConnector:
    """Connects to ClearQuest REST API and retrieves PD/EI records."""

    API_VERSION = "v2"
    PAGE_SIZE = 500

    def __init__(self, url: str, username: str, password: str, database: str):
        """Initialize the ClearQuest connector.

        Args:
            url: Base URL of the ClearQuest REST API server.
            username: ClearQuest login username.
            password: ClearQuest login password.
            database: ClearQuest schema repository / database name.
        """
        self.base_url = url.rstrip("/")
        self.database = database
        self._session = requests.Session()
        self._session.auth = (username, password)
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _build_query_url(self, record_type: str) -> str:
        """Build the REST API URL for querying a record type.

        Args:
            record_type: ClearQuest record type (e.g. "PD" or "EI").

        Returns:
            Fully qualified REST API URL string.
        """
        return (
            f"{self.base_url}/cqweb/oslc/{self.API_VERSION}"
            f"/repo/{self.database}/db/{self.database}"
            f"/record/{record_type}"
        )

    def _fetch_records_page(
        self,
        record_type: str,
        project: str,
        fields: list[str],
        page: int,
    ) -> dict[str, Any]:
        """Fetch a single page of records from ClearQuest.

        Args:
            record_type: ClearQuest record type to query.
            project: Project name to filter results.
            fields: List of field names to retrieve.
            page: 1-based page number.

        Returns:
            Parsed JSON response dictionary.
        """
        url = self._build_query_url(record_type)
        params = {
            "fields": ",".join(fields),
            "pageSize": self.PAGE_SIZE,
            "pageNumber": page,
            "project": project,
        }
        response = self._session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def fetch_records(
        self,
        project: str,
        record_type: str,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all records of a given type for a project.

        Args:
            project: ClearQuest project name (e.g. "Earth").
            record_type: Record type to retrieve (e.g. "PD" or "EI").
            fields: Fields to include; defaults to DEFAULT_FIELDS.

        Returns:
            List of record dictionaries.
        """
        if fields is None:
            fields = DEFAULT_FIELDS

        logger.info(
            "Querying ClearQuest project '%s' for '%s' records...",
            project,
            record_type,
        )

        records: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self._fetch_records_page(record_type, project, fields, page)
            entries = data.get("entries", [])
            for entry in entries:
                values = entry.get("fields", {})
                records.append(
                    {
                        "source": "ClearQuest",
                        "project": project,
                        "record_type": record_type,
                        "id": values.get(CQ_FIELD_ID),
                        "brief": values.get(CQ_FIELD_HEADLINE),
                        "component": values.get(CQ_FIELD_COMPONENT),
                        "status": values.get(CQ_FIELD_STATE),
                        "score": _to_float(values.get(CQ_FIELD_SCORE)),
                        "probability": _to_float(values.get(CQ_FIELD_PROBABILITY)),
                    }
                )

            total = data.get("totalCount", 0)
            if len(records) >= total or not entries:
                break
            page += 1

        logger.info(
            "Retrieved %d '%s' records from ClearQuest project '%s'.",
            len(records),
            record_type,
            project,
        )
        return records

    def fetch_all_types(
        self,
        project: str,
        record_types: list[str],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch records for multiple record types.

        Args:
            project: ClearQuest project name.
            record_types: List of record types to retrieve (e.g. ["PD", "EI"]).
            fields: Fields to include; defaults to DEFAULT_FIELDS.

        Returns:
            Combined list of record dictionaries from all record types.
        """
        all_records: list[dict[str, Any]] = []
        for record_type in record_types:
            records = self.fetch_records(project, record_type, fields)
            all_records.extend(records)
        return all_records


def _to_float(value: Any) -> float | None:
    """Convert a value to float, returning None if conversion fails."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
