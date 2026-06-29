"""Unit tests for ADSConnector."""

from unittest.mock import MagicMock, patch

import pytest

from src.ads_connector import (
    ADS_FIELD_AREA,
    ADS_FIELD_GENERIC02,
    ADS_FIELD_GENERIC03,
    ADS_FIELD_GENERIC04,
    ADS_FIELD_GENERIC05,
    ADS_FIELD_ID,
    ADS_FIELD_SEVERITY,
    ADS_FIELD_STATE,
    ADS_FIELD_TITLE,
    ADSConnector,
    DEFAULT_FIELDS,
)


@pytest.fixture()
def connector():
    """Return an ADSConnector with a dummy PAT (no real HTTP calls)."""
    return ADSConnector(
        url="https://dev.azure.com/{organization}",
        organization="my-org",
        personal_access_token="dummy-pat",
    )


class TestADSConnectorInit:
    def test_base_url_organisation_substituted(self, connector):
        assert "my-org" in connector.base_url

    def test_authorization_header_set(self, connector):
        assert "Authorization" in connector._session.headers
        assert connector._session.headers["Authorization"].startswith("Basic ")


class TestWiqlQuery:
    def test_returns_ids(self, connector):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "workItems": [{"id": 1}, {"id": 2}, {"id": 3}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(connector._session, "post", return_value=mock_response):
            ids = connector._wiql_query("Earth", "Bug")

        assert ids == [1, 2, 3]

    def test_empty_query_returns_empty_list(self, connector):
        mock_response = MagicMock()
        mock_response.json.return_value = {"workItems": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(connector._session, "post", return_value=mock_response):
            ids = connector._wiql_query("Earth", "Bug")

        assert ids == []


class TestFetchWorkItemsBatch:
    def _mock_work_item(self, id_: int, title: str, severity: str, state: str):
        return {
            "id": id_,
            "fields": {
                ADS_FIELD_TITLE: title,
                ADS_FIELD_AREA: f"Earth\\Component",
                ADS_FIELD_SEVERITY: severity,
                ADS_FIELD_STATE: state,
                ADS_FIELD_GENERIC02: None,
                ADS_FIELD_GENERIC03: None,
                ADS_FIELD_GENERIC04: None,
                ADS_FIELD_GENERIC05: None,
            },
        }

    def test_returns_mapped_fields(self, connector):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "value": [
                self._mock_work_item(1, "Crash on login", "1 - Critical", "Active"),
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(connector._session, "post", return_value=mock_response):
            items = connector._fetch_work_items_batch([1], DEFAULT_FIELDS)

        assert len(items) == 1
        assert items[0]["id"] == 1
        assert items[0]["fields"][ADS_FIELD_TITLE] == "Crash on login"


class TestFetchBugs:
    def test_fetch_bugs_returns_normalised_records(self, connector):
        wiql_response = MagicMock()
        wiql_response.json.return_value = {"workItems": [{"id": 10}, {"id": 11}]}
        wiql_response.raise_for_status = MagicMock()

        batch_response = MagicMock()
        batch_response.json.return_value = {
            "value": [
                {
                    "id": 10,
                    "fields": {
                        ADS_FIELD_TITLE: "Bug A",
                        ADS_FIELD_AREA: "Earth\\UI",
                        ADS_FIELD_SEVERITY: "2 - High",
                        ADS_FIELD_STATE: "Active",
                        ADS_FIELD_GENERIC02: "v02",
                        ADS_FIELD_GENERIC03: None,
                        ADS_FIELD_GENERIC04: None,
                        ADS_FIELD_GENERIC05: None,
                    },
                },
                {
                    "id": 11,
                    "fields": {
                        ADS_FIELD_TITLE: "Bug B",
                        ADS_FIELD_AREA: "Earth\\API",
                        ADS_FIELD_SEVERITY: "3 - Medium",
                        ADS_FIELD_STATE: "Resolved",
                        ADS_FIELD_GENERIC02: None,
                        ADS_FIELD_GENERIC03: None,
                        ADS_FIELD_GENERIC04: None,
                        ADS_FIELD_GENERIC05: None,
                    },
                },
            ]
        }
        batch_response.raise_for_status = MagicMock()

        responses = [wiql_response, batch_response]
        with patch.object(connector._session, "post", side_effect=responses):
            items = connector.fetch_bugs("Earth")

        assert len(items) == 2
        assert items[0]["source"] == "ADS"
        assert items[0]["project"] == "Earth"
        assert items[0]["id"] == 10
        assert items[0]["brief"] == "Bug A"
        assert items[0]["severity"] == "2 - High"
        assert items[0]["status"] == "Active"
        assert items[0]["generic02"] == "v02"
        assert items[1]["status"] == "Resolved"


class TestFetchAllProjects:
    def test_combines_multiple_projects(self, connector):
        empty_wiql = MagicMock()
        empty_wiql.json.return_value = {"workItems": []}
        empty_wiql.raise_for_status = MagicMock()

        with patch.object(connector._session, "post", return_value=empty_wiql):
            items = connector.fetch_all_projects(
                [
                    {"name": "Earth", "work_item_type": "Bug"},
                    {"name": "LCM Tracker", "work_item_type": "Bug"},
                ]
            )

        assert items == []
