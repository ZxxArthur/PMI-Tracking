"""PMI (Product Maturity Index) calculator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default severity weights (higher = more severe)
DEFAULT_SEVERITY_WEIGHTS: dict[str, float] = {
    "1 - Critical": 4.0,
    "2 - High": 3.0,
    "3 - Medium": 2.0,
    "4 - Low": 1.0,
}

# Default set of statuses that indicate a closed/resolved record
DEFAULT_CLOSED_STATUSES: set[str] = {
    "Resolved",
    "Closed",
    "Done",
    "Verified",
}


@dataclass
class PhaseTarget:
    """Threshold configuration for a single delivery phase."""

    name: str
    pmi_threshold: float
    max_open_critical: int = 0
    max_open_high: int = 0


@dataclass
class PMIResult:
    """Aggregated PMI result for a single calculation run."""

    pmi_score: float
    total_records: int
    open_records: int
    closed_records: int
    weighted_total: float
    weighted_open: float
    weighted_closed: float
    open_by_severity: dict[str, int] = field(default_factory=dict)
    total_risk: float = 0.0
    phase_evaluations: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [
            f"PMI Score         : {self.pmi_score:.2f}%",
            f"Total records     : {self.total_records}",
            f"Open records      : {self.open_records}",
            f"Closed records    : {self.closed_records}",
            f"Weighted total    : {self.weighted_total:.2f}",
            f"Weighted open     : {self.weighted_open:.2f}",
            f"Weighted closed   : {self.weighted_closed:.2f}",
            f"Total CQ risk     : {self.total_risk:.4f}",
            "Open by severity  :",
        ]
        for sev, cnt in self.open_by_severity.items():
            lines.append(f"  {sev}: {cnt}")
        if self.phase_evaluations:
            lines.append("Phase evaluations :")
            for ev in self.phase_evaluations:
                status = "PASS" if ev["meets_target"] else "FAIL"
                lines.append(
                    f"  [{status}] {ev['phase']}: "
                    f"PMI {self.pmi_score:.1f}% (target ≥ {ev['pmi_threshold']}%)"
                )
        return "\n".join(lines)


class PMICalculator:
    """Calculates the Product Maturity Index from combined defect records.

    The PMI is a weighted closure rate calculated as::

        PMI = (weighted_closed / weighted_total) * 100

    where each ADS Bug contributes its severity weight, and each ClearQuest
    record contributes a fixed weight of 1 (its risk metric is tracked
    separately as *total_risk*).

    If there are no records, PMI defaults to 100.0 (perfect maturity).
    """

    def __init__(
        self,
        severity_weights: dict[str, float] | None = None,
        closed_statuses: set[str] | None = None,
        phase_targets: list[PhaseTarget] | None = None,
    ):
        """Initialise the calculator.

        Args:
            severity_weights: Mapping of severity label → numeric weight.
                              Defaults to DEFAULT_SEVERITY_WEIGHTS.
            closed_statuses: Set of status strings considered "closed".
                             Defaults to DEFAULT_CLOSED_STATUSES.
            phase_targets: Optional list of :class:`PhaseTarget` objects used
                           to evaluate whether the PMI meets next-phase goals.
        """
        self.severity_weights = severity_weights or DEFAULT_SEVERITY_WEIGHTS
        self.closed_statuses = closed_statuses or DEFAULT_CLOSED_STATUSES
        self.phase_targets = phase_targets or []

    def _is_closed(self, record: dict[str, Any]) -> bool:
        """Return True if the record's status is in the closed statuses set."""
        return str(record.get("status") or "").strip() in self.closed_statuses

    def _weight_of(self, record: dict[str, Any]) -> float:
        """Return the severity weight for an ADS record (default 1.0)."""
        severity = str(record.get("severity") or "").strip()
        return self.severity_weights.get(severity, 1.0)

    def calculate(self, records: list[dict[str, Any]]) -> PMIResult:
        """Calculate the PMI from a combined list of defect records.

        Args:
            records: Combined list of common-schema records (ADS + ClearQuest).

        Returns:
            :class:`PMIResult` containing PMI score and supporting metrics.
        """
        if not records:
            logger.warning("No records provided; returning PMI = 100.0.")
            return PMIResult(
                pmi_score=100.0,
                total_records=0,
                open_records=0,
                closed_records=0,
                weighted_total=0.0,
                weighted_open=0.0,
                weighted_closed=0.0,
            )

        weighted_total = 0.0
        weighted_open = 0.0
        weighted_closed = 0.0
        open_count = 0
        closed_count = 0
        total_risk = 0.0
        open_by_severity: dict[str, int] = {}

        for record in records:
            source = str(record.get("source") or "").strip()
            closed = self._is_closed(record)

            if source == "ADS":
                w = self._weight_of(record)
                weighted_total += w
                if closed:
                    weighted_closed += w
                    closed_count += 1
                else:
                    weighted_open += w
                    open_count += 1
                    sev = str(record.get("severity") or "Unknown").strip()
                    open_by_severity[sev] = open_by_severity.get(sev, 0) + 1
            else:
                # ClearQuest records: weight = 1, risk tracked separately
                weighted_total += 1.0
                risk = record.get("risk")
                if risk is not None:
                    total_risk += float(risk)
                if closed:
                    weighted_closed += 1.0
                    closed_count += 1
                else:
                    weighted_open += 1.0
                    open_count += 1

        pmi_score = (
            (weighted_closed / weighted_total) * 100.0 if weighted_total > 0 else 100.0
        )

        phase_evaluations = self._evaluate_phases(pmi_score, open_by_severity)

        result = PMIResult(
            pmi_score=round(pmi_score, 4),
            total_records=len(records),
            open_records=open_count,
            closed_records=closed_count,
            weighted_total=weighted_total,
            weighted_open=weighted_open,
            weighted_closed=weighted_closed,
            open_by_severity=open_by_severity,
            total_risk=round(total_risk, 6),
            phase_evaluations=phase_evaluations,
        )
        logger.info("PMI calculated: %.2f%%  (%d records)", pmi_score, len(records))
        return result

    def _evaluate_phases(
        self,
        pmi_score: float,
        open_by_severity: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Evaluate the PMI score against each configured phase target.

        Args:
            pmi_score: Calculated PMI percentage.
            open_by_severity: Mapping of severity label → open defect count.

        Returns:
            List of evaluation dictionaries, one per phase target.
        """
        evaluations: list[dict[str, Any]] = []
        for target in self.phase_targets:
            open_critical = sum(
                v
                for k, v in open_by_severity.items()
                if "critical" in k.lower()
            )
            open_high = sum(
                v
                for k, v in open_by_severity.items()
                if "high" in k.lower()
            )
            meets_pmi = pmi_score >= target.pmi_threshold
            meets_critical = open_critical <= target.max_open_critical
            meets_high = open_high <= target.max_open_high
            meets_target = meets_pmi and meets_critical and meets_high

            evaluations.append(
                {
                    "phase": target.name,
                    "pmi_threshold": target.pmi_threshold,
                    "meets_pmi": meets_pmi,
                    "meets_critical_limit": meets_critical,
                    "meets_high_limit": meets_high,
                    "meets_target": meets_target,
                    "open_critical": open_critical,
                    "open_high": open_high,
                }
            )
        return evaluations
