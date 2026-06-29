"""Field mapper: normalises ADS and ClearQuest records into a common schema."""

from typing import Any

# Common schema field names used throughout the application
FIELD_SOURCE = "source"
FIELD_PROJECT = "project"
FIELD_RECORD_TYPE = "record_type"
FIELD_ID = "id"
FIELD_BRIEF = "brief"
FIELD_COMPONENT = "component"
FIELD_SEVERITY = "severity"
FIELD_STATUS = "status"
FIELD_GENERIC02 = "generic02"
FIELD_GENERIC03 = "generic03"
FIELD_GENERIC04 = "generic04"
FIELD_GENERIC05 = "generic05"
FIELD_SCORE = "score"
FIELD_PROBABILITY = "probability"
FIELD_RISK = "risk"


def map_ads_record(record: dict[str, Any]) -> dict[str, Any]:
    """Map an ADS work item to the common schema.

    ADS-specific fields (generic02-05) are preserved as-is.
    ClearQuest-specific fields (score, probability, risk) are set to None.

    Args:
        record: Raw ADS work item dictionary produced by ADSConnector.

    Returns:
        Dictionary conforming to the common schema.
    """
    return {
        FIELD_SOURCE: record.get("source", "ADS"),
        FIELD_PROJECT: record.get("project"),
        FIELD_RECORD_TYPE: "Bug",
        FIELD_ID: str(record.get("id", "")),
        FIELD_BRIEF: record.get("brief"),
        FIELD_COMPONENT: record.get("component"),
        FIELD_SEVERITY: record.get("severity"),
        FIELD_STATUS: record.get("status"),
        FIELD_GENERIC02: record.get("generic02"),
        FIELD_GENERIC03: record.get("generic03"),
        FIELD_GENERIC04: record.get("generic04"),
        FIELD_GENERIC05: record.get("generic05"),
        FIELD_SCORE: None,
        FIELD_PROBABILITY: None,
        FIELD_RISK: None,
    }


def map_clearquest_record(record: dict[str, Any]) -> dict[str, Any]:
    """Map a ClearQuest record to the common schema.

    ClearQuest records carry score and probability; risk is derived as
    ``score * probability``.  ADS-specific generic fields are set to None.

    Args:
        record: Raw ClearQuest record dictionary produced by ClearQuestConnector.

    Returns:
        Dictionary conforming to the common schema.
    """
    score = record.get("score")
    probability = record.get("probability")
    risk = _calculate_risk(score, probability)

    return {
        FIELD_SOURCE: record.get("source", "ClearQuest"),
        FIELD_PROJECT: record.get("project"),
        FIELD_RECORD_TYPE: record.get("record_type"),
        FIELD_ID: str(record.get("id", "")),
        FIELD_BRIEF: record.get("brief"),
        FIELD_COMPONENT: record.get("component"),
        FIELD_SEVERITY: None,
        FIELD_STATUS: record.get("status"),
        FIELD_GENERIC02: None,
        FIELD_GENERIC03: None,
        FIELD_GENERIC04: None,
        FIELD_GENERIC05: None,
        FIELD_SCORE: score,
        FIELD_PROBABILITY: probability,
        FIELD_RISK: risk,
    }


def map_records(
    ads_records: list[dict[str, Any]],
    cq_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map and combine ADS and ClearQuest records into the common schema.

    Args:
        ads_records: List of raw ADS work item dictionaries.
        cq_records: List of raw ClearQuest record dictionaries.

    Returns:
        Single combined list of records conforming to the common schema.
    """
    mapped: list[dict[str, Any]] = []
    for record in ads_records:
        mapped.append(map_ads_record(record))
    for record in cq_records:
        mapped.append(map_clearquest_record(record))
    return mapped


def _calculate_risk(
    score: float | None, probability: float | None
) -> float | None:
    """Calculate risk as ``score * probability``.

    Returns None if either input is None.
    """
    if score is None or probability is None:
        return None
    return score * probability
