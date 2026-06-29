"""ADS (Azure DevOps Services) connector for fetching Bug work items."""

import base64
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ADS field name constants
ADS_FIELD_ID = "System.Id"
ADS_FIELD_TITLE = "System.Title"
ADS_FIELD_AREA = "System.AreaPath"
ADS_FIELD_SEVERITY = "Microsoft.VSTS.Common.Severity"
ADS_FIELD_STATE = "System.State"
ADS_FIELD_GENERIC02 = "Custom.Generic02"
ADS_FIELD_GENERIC03 = "Custom.Generic03"
ADS_FIELD_GENERIC04 = "Custom.Generic04"
ADS_FIELD_GENERIC05 = "Custom.Generic05"

DEFAULT_FIELDS = [
    ADS_FIELD_ID,
    ADS_FIELD_TITLE,
    ADS_FIELD_AREA,
    ADS_FIELD_SEVERITY,
    ADS_FIELD_STATE,
    ADS_FIELD_GENERIC02,
    ADS_FIELD_GENERIC03,
    ADS_FIELD_GENERIC04,
    ADS_FIELD_GENERIC05,
]


class ADSConnector:
    """Connects to Azure DevOps Services and retrieves Bug work items."""

    API_VERSION = "7.1"
    WIQL_ENDPOINT = "_apis/wit/wiql"
    WORKITEMS_ENDPOINT = "_apis/wit/workitemsbatch"
    BATCH_SIZE = 200

    def __init__(self, url: str, organization: str, personal_access_token: str):
        """Initialize the ADS connector.

        Args:
            url: Base URL of the Azure DevOps organization
                 (e.g. "https://dev.azure.com/{org}").
            organization: Azure DevOps organization name.
            personal_access_token: Personal Access Token for authentication.
        """
        self.base_url = url.rstrip("/").format(organization=organization)
        self.organization = organization
        self._session = requests.Session()
        encoded = base64.b64encode(f":{personal_access_token}".encode()).decode()
        self._session.headers.update(
            {
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _wiql_query(self, project: str, work_item_type: str) -> list[int]:
        """Run a WIQL query and return matching work item IDs.

        Args:
            project: Azure DevOps project name.
            work_item_type: Work item type to filter (e.g. "Bug").

        Returns:
            List of work item IDs.
        """
        url = f"{self.base_url}/{project}/{self.WIQL_ENDPOINT}"
        params = {"api-version": self.API_VERSION}
        body = {
            "query": (
                f"SELECT [{ADS_FIELD_ID}] "
                f"FROM WorkItems "
                f"WHERE [System.TeamProject] = '{project}' "
                f"AND [System.WorkItemType] = '{work_item_type}'"
            )
        }
        response = self._session.post(url, json=body, params=params)
        response.raise_for_status()
        data = response.json()
        return [item["id"] for item in data.get("workItems", [])]

    def _fetch_work_items_batch(
        self, ids: list[int], fields: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch work item details for a batch of IDs.

        Args:
            ids: List of work item IDs to fetch.
            fields: List of field reference names to retrieve.

        Returns:
            List of work item dictionaries with field values.
        """
        url = f"{self.base_url}/{self.WORKITEMS_ENDPOINT}"
        params = {"api-version": self.API_VERSION}
        body = {"ids": ids, "fields": fields}
        response = self._session.post(url, json=body, params=params)
        response.raise_for_status()
        return response.json().get("value", [])

    def fetch_bugs(
        self,
        project: str,
        work_item_type: str = "Bug",
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all Bug work items for a project.

        Args:
            project: Azure DevOps project name.
            work_item_type: Work item type to retrieve (default "Bug").
            fields: Fields to include in results; defaults to DEFAULT_FIELDS.

        Returns:
            List of dictionaries containing work item fields.
        """
        if fields is None:
            fields = DEFAULT_FIELDS

        logger.info("Querying ADS project '%s' for '%s' items...", project, work_item_type)
        ids = self._wiql_query(project, work_item_type)
        logger.info("Found %d items in project '%s'.", len(ids), project)

        items: list[dict[str, Any]] = []
        for i in range(0, len(ids), self.BATCH_SIZE):
            batch = ids[i : i + self.BATCH_SIZE]
            raw_items = self._fetch_work_items_batch(batch, fields)
            for raw in raw_items:
                f = raw.get("fields", {})
                items.append(
                    {
                        "source": "ADS",
                        "project": project,
                        "id": raw.get("id"),
                        "brief": f.get(ADS_FIELD_TITLE),
                        "component": f.get(ADS_FIELD_AREA),
                        "severity": f.get(ADS_FIELD_SEVERITY),
                        "status": f.get(ADS_FIELD_STATE),
                        "generic02": f.get(ADS_FIELD_GENERIC02),
                        "generic03": f.get(ADS_FIELD_GENERIC03),
                        "generic04": f.get(ADS_FIELD_GENERIC04),
                        "generic05": f.get(ADS_FIELD_GENERIC05),
                    }
                )
        return items

    def fetch_all_projects(
        self,
        projects: list[dict[str, str]],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch bugs from multiple projects.

        Args:
            projects: List of project config dicts with keys ``name`` and
                      ``work_item_type``.
            fields: Fields to include; defaults to DEFAULT_FIELDS.

        Returns:
            Combined list of work item dictionaries from all projects.
        """
        all_items: list[dict[str, Any]] = []
        for proj in projects:
            items = self.fetch_bugs(
                project=proj["name"],
                work_item_type=proj.get("work_item_type", "Bug"),
                fields=fields,
            )
            all_items.extend(items)
        return all_items
