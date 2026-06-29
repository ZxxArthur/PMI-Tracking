"""Unit tests for database module."""

import pytest

from src.database import Database


def _make_record(source="ADS", rec_id="1", status="Active", severity="3 - Medium",
                 score=None, prob=None, risk=None):
    return {
        "source": source,
        "project": "Earth",
        "record_type": "Bug",
        "id": rec_id,
        "brief": f"Test record {rec_id}",
        "component": "Core",
        "severity": severity,
        "status": status,
        "generic02": None,
        "generic03": None,
        "generic04": None,
        "generic05": None,
        "score": score,
        "probability": prob,
        "risk": risk,
    }


@pytest.fixture()
def db():
    """Provide an in-memory database for each test."""
    with Database(":memory:") as database:
        yield database


class TestDatabaseSchema:
    def test_table_created(self, db):
        cursor = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='defects'"
        )
        assert cursor.fetchone() is not None


class TestUpsertRecords:
    def test_insert_single_record(self, db):
        db.upsert_records([_make_record()])
        rows = db.query_all()
        assert len(rows) == 1
        assert rows[0]["id"] == "1"

    def test_insert_multiple_records(self, db):
        records = [_make_record(rec_id=str(i)) for i in range(5)]
        db.upsert_records(records)
        assert len(db.query_all()) == 5

    def test_upsert_updates_existing(self, db):
        db.upsert_records([_make_record(rec_id="42", status="Active")])
        db.upsert_records([_make_record(rec_id="42", status="Closed")])
        rows = db.query_all()
        assert len(rows) == 1
        assert rows[0]["status"] == "Closed"

    def test_different_sources_same_id_both_stored(self, db):
        ads_rec = _make_record(source="ADS", rec_id="100")
        cq_rec = _make_record(source="ClearQuest", rec_id="100")
        db.upsert_records([ads_rec, cq_rec])
        assert len(db.query_all()) == 2

    def test_empty_list_no_error(self, db):
        affected = db.upsert_records([])
        assert db.query_all() == []


class TestQueryBySource:
    def test_filter_ads(self, db):
        db.upsert_records([
            _make_record(source="ADS", rec_id="1"),
            _make_record(source="ClearQuest", rec_id="CQ1"),
        ])
        rows = db.query_by_source("ADS")
        assert len(rows) == 1
        assert rows[0]["source"] == "ADS"

    def test_filter_clearquest(self, db):
        db.upsert_records([
            _make_record(source="ADS", rec_id="1"),
            _make_record(source="ClearQuest", rec_id="CQ1"),
            _make_record(source="ClearQuest", rec_id="CQ2"),
        ])
        rows = db.query_by_source("ClearQuest")
        assert len(rows) == 2

    def test_unknown_source_returns_empty(self, db):
        db.upsert_records([_make_record(source="ADS", rec_id="1")])
        assert db.query_by_source("Jira") == []


class TestQueryOpenDefects:
    def test_returns_only_open(self, db):
        db.upsert_records([
            _make_record(rec_id="1", status="Active"),
            _make_record(rec_id="2", status="Closed"),
            _make_record(rec_id="3", status="Resolved"),
            _make_record(rec_id="4", status="New"),
        ])
        open_rows = db.query_open_defects(["Closed", "Resolved"])
        ids = {r["id"] for r in open_rows}
        assert "1" in ids
        assert "4" in ids
        assert "2" not in ids
        assert "3" not in ids

    def test_null_status_treated_as_open(self, db):
        rec = _make_record(rec_id="5", status=None)
        rec["status"] = None
        db.upsert_records([rec])
        open_rows = db.query_open_defects(["Closed"])
        assert any(r["id"] == "5" for r in open_rows)

    def test_all_closed_returns_empty(self, db):
        db.upsert_records([_make_record(rec_id="1", status="Done")])
        assert db.query_open_defects(["Done"]) == []


class TestDatabaseContextManager:
    def test_context_manager_closes_connection(self):
        with Database(":memory:") as db:
            db.upsert_records([_make_record()])
        # After context exits, further operations should raise
        with pytest.raises(Exception):
            db.query_all()
