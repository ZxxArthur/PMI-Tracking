"""Unit tests for ClearQuestConnector."""

from unittest.mock import MagicMock, patch

import pytest

from src.clearquest_connector import (
    CQ_FIELD_COMPONENT,
    CQ_FIELD_HEADLINE,
    CQ_FIELD_ID,
    CQ_FIELD_PROBABILITY,
    CQ_FIELD_SCORE,
    CQ_FIELD_STATE,
    ClearQuestConnector,
    _to_float,
)


@pytest.fixture()
def connector():
    """Return a ClearQuestConnector with dummy credentials (no real HTTP calls)."""
    return ClearQuestConnector(
        url="http://cq.example.com",
        username="tester",
        password="secret",
        database="EARTH_DB",
    )


class TestClearQuestConnectorInit:
    def test_base_url_stored(self, connector):
        assert connector.base_url == "http://cq.example.com"

    def test_database_stored(self, connector):
        assert connector.database == "EARTH_DB"

    def test_auth_set(self, connector):
        assert connector._session.auth == ("tester", "secret")


class TestBuildQueryUrl:
    def test_url_contains_record_type(self, connector):
        url = connector._build_query_url("PD")
        assert "PD" in url
        assert "EARTH_DB" in url

    def test_url_differs_per_record_type(self, connector):
        assert connector._build_query_url("PD") != connector._build_query_url("EI")


class TestFetchRecordsPage:
    def _page_response(self, entries, total):
        mock = MagicMock()
        mock.json.return_value = {"entries": entries, "totalCount": total}
        mock.raise_for_status = MagicMock()
        return mock

    def _make_entry(self, id_="PD001", headline="Issue", component="UI",
                    state="Open", score=5.0, prob=0.3):
        return {
            "fields": {
                CQ_FIELD_ID: id_,
                CQ_FIELD_HEADLINE: headline,
                CQ_FIELD_COMPONENT: component,
                CQ_FIELD_STATE: state,
                CQ_FIELD_SCORE: score,
                CQ_FIELD_PROBABILITY: prob,
            }
        }

    def test_single_page_returned(self, connector):
        entries = [self._make_entry("PD001"), self._make_entry("PD002")]
        response = self._page_response(entries, total=2)

        with patch.object(connector._session, "get", return_value=response):
            records = connector.fetch_records("Earth", "PD")

        assert len(records) == 2
        assert records[0]["id"] == "PD001"
        assert records[0]["source"] == "ClearQuest"
        assert records[0]["project"] == "Earth"
        assert records[0]["record_type"] == "PD"
        assert records[0]["brief"] == "Issue"
        assert records[0]["status"] == "Open"
        assert records[0]["score"] == pytest.approx(5.0)
        assert records[0]["probability"] == pytest.approx(0.3)

    def test_pagination_fetches_all_pages(self, connector):
        page1_entries = [self._make_entry(f"PD{i:03d}") for i in range(3)]
        page2_entries = [self._make_entry(f"PD{i:03d}") for i in range(3, 5)]

        page1 = self._page_response(page1_entries, total=5)
        page2 = self._page_response(page2_entries, total=5)
        no_more = self._page_response([], total=5)

        with patch.object(
            connector._session, "get", side_effect=[page1, page2, no_more]
        ):
            records = connector.fetch_records("Earth", "PD")

        assert len(records) == 5

    def test_empty_project_returns_empty_list(self, connector):
        response = self._page_response([], total=0)
        with patch.object(connector._session, "get", return_value=response):
            records = connector.fetch_records("Earth", "PD")
        assert records == []


class TestFetchAllTypes:
    def test_combines_pd_and_ei(self, connector):
        empty_response = MagicMock()
        empty_response.json.return_value = {"entries": [], "totalCount": 0}
        empty_response.raise_for_status = MagicMock()

        with patch.object(connector._session, "get", return_value=empty_response):
            records = connector.fetch_all_types("Earth", ["PD", "EI"])

        assert records == []


class TestToFloat:
    def test_integer_input(self):
        assert _to_float(5) == pytest.approx(5.0)

    def test_string_number(self):
        assert _to_float("3.14") == pytest.approx(3.14)

    def test_none_returns_none(self):
        assert _to_float(None) is None

    def test_non_numeric_returns_none(self):
        assert _to_float("n/a") is None

    def test_zero(self):
        assert _to_float(0) == pytest.approx(0.0)
