"""Unit tests for field_mapper module."""

import pytest

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
    map_ads_record,
    map_clearquest_record,
    map_records,
)


class TestMapAdsRecord:
    def test_basic_mapping(self):
        raw = {
            "source": "ADS",
            "project": "Earth",
            "id": 42,
            "brief": "Login fails on timeout",
            "component": "Earth\\Auth",
            "severity": "2 - High",
            "status": "Active",
            "generic02": "g02_val",
            "generic03": "g03_val",
            "generic04": "g04_val",
            "generic05": "g05_val",
        }
        result = map_ads_record(raw)

        assert result[FIELD_SOURCE] == "ADS"
        assert result[FIELD_PROJECT] == "Earth"
        assert result[FIELD_RECORD_TYPE] == "Bug"
        assert result[FIELD_ID] == "42"
        assert result[FIELD_BRIEF] == "Login fails on timeout"
        assert result[FIELD_COMPONENT] == "Earth\\Auth"
        assert result[FIELD_SEVERITY] == "2 - High"
        assert result[FIELD_STATUS] == "Active"
        assert result[FIELD_GENERIC02] == "g02_val"
        assert result[FIELD_GENERIC03] == "g03_val"
        assert result[FIELD_GENERIC04] == "g04_val"
        assert result[FIELD_GENERIC05] == "g05_val"

    def test_cq_fields_are_none(self):
        result = map_ads_record({"id": 1})
        assert result[FIELD_SCORE] is None
        assert result[FIELD_PROBABILITY] is None
        assert result[FIELD_RISK] is None

    def test_id_is_stringified(self):
        result = map_ads_record({"id": 999})
        assert result[FIELD_ID] == "999"
        assert isinstance(result[FIELD_ID], str)

    def test_missing_optional_fields_default_to_none(self):
        result = map_ads_record({})
        assert result[FIELD_BRIEF] is None
        assert result[FIELD_COMPONENT] is None
        assert result[FIELD_SEVERITY] is None
        assert result[FIELD_STATUS] is None


class TestMapClearQuestRecord:
    def test_basic_mapping(self):
        raw = {
            "source": "ClearQuest",
            "project": "Earth",
            "record_type": "PD",
            "id": "PD00123",
            "brief": "Data loss under high load",
            "component": "DB Layer",
            "status": "Open",
            "score": 8.5,
            "probability": 0.6,
        }
        result = map_clearquest_record(raw)

        assert result[FIELD_SOURCE] == "ClearQuest"
        assert result[FIELD_PROJECT] == "Earth"
        assert result[FIELD_RECORD_TYPE] == "PD"
        assert result[FIELD_ID] == "PD00123"
        assert result[FIELD_BRIEF] == "Data loss under high load"
        assert result[FIELD_COMPONENT] == "DB Layer"
        assert result[FIELD_STATUS] == "Open"
        assert result[FIELD_SCORE] == 8.5
        assert result[FIELD_PROBABILITY] == 0.6

    def test_risk_calculated(self):
        raw = {"id": "EI001", "score": 5.0, "probability": 0.4}
        result = map_clearquest_record(raw)
        assert result[FIELD_RISK] == pytest.approx(2.0)

    def test_risk_none_when_score_missing(self):
        raw = {"id": "EI002", "score": None, "probability": 0.5}
        result = map_clearquest_record(raw)
        assert result[FIELD_RISK] is None

    def test_risk_none_when_probability_missing(self):
        raw = {"id": "EI003", "score": 5.0, "probability": None}
        result = map_clearquest_record(raw)
        assert result[FIELD_RISK] is None

    def test_ads_fields_are_none(self):
        result = map_clearquest_record({"id": "X"})
        assert result[FIELD_SEVERITY] is None
        assert result[FIELD_GENERIC02] is None
        assert result[FIELD_GENERIC03] is None
        assert result[FIELD_GENERIC04] is None
        assert result[FIELD_GENERIC05] is None


class TestMapRecords:
    def _ads_record(self, id_=1, status="Active"):
        return {
            "source": "ADS",
            "project": "Earth",
            "id": id_,
            "brief": f"Bug {id_}",
            "component": "Core",
            "severity": "3 - Medium",
            "status": status,
        }

    def _cq_record(self, id_="PD001", status="Open", score=3.0, prob=0.5):
        return {
            "source": "ClearQuest",
            "project": "Earth",
            "record_type": "PD",
            "id": id_,
            "brief": f"Defect {id_}",
            "component": "UI",
            "status": status,
            "score": score,
            "probability": prob,
        }

    def test_combines_ads_and_cq(self):
        ads = [self._ads_record(1), self._ads_record(2)]
        cq = [self._cq_record("PD1")]
        combined = map_records(ads, cq)
        assert len(combined) == 3

    def test_sources_preserved(self):
        combined = map_records([self._ads_record()], [self._cq_record()])
        sources = {r[FIELD_SOURCE] for r in combined}
        assert "ADS" in sources
        assert "ClearQuest" in sources

    def test_empty_inputs(self):
        assert map_records([], []) == []

    def test_only_ads(self):
        combined = map_records([self._ads_record(1)], [])
        assert len(combined) == 1
        assert combined[0][FIELD_SOURCE] == "ADS"

    def test_only_cq(self):
        combined = map_records([], [self._cq_record()])
        assert len(combined) == 1
        assert combined[0][FIELD_SOURCE] == "ClearQuest"
