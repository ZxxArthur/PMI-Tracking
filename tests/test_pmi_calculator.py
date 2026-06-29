"""Unit tests for pmi_calculator module."""

import pytest

from src.pmi_calculator import (
    DEFAULT_CLOSED_STATUSES,
    DEFAULT_SEVERITY_WEIGHTS,
    PMICalculator,
    PhaseTarget,
)


def _ads(status="Active", severity="3 - Medium"):
    return {"source": "ADS", "status": status, "severity": severity,
            "score": None, "probability": None, "risk": None}


def _cq(status="Open", score=5.0, probability=0.4):
    return {"source": "ClearQuest", "status": status, "severity": None,
            "score": score, "probability": probability, "risk": score * probability}


class TestPMICalculatorBasic:
    def setup_method(self):
        self.calc = PMICalculator()

    def test_empty_records_returns_100(self):
        result = self.calc.calculate([])
        assert result.pmi_score == 100.0
        assert result.total_records == 0

    def test_all_open_returns_0(self):
        records = [_ads("Active"), _ads("New"), _cq("Open")]
        result = self.calc.calculate(records)
        assert result.pmi_score == pytest.approx(0.0)
        assert result.open_records == 3
        assert result.closed_records == 0

    def test_all_closed_returns_100(self):
        records = [_ads("Closed"), _cq("Closed")]
        result = self.calc.calculate(records)
        assert result.pmi_score == pytest.approx(100.0)
        assert result.open_records == 0
        assert result.closed_records == 2

    def test_mixed_returns_partial_pmi(self):
        # 1 ADS critical (weight=4, open), 1 ADS medium (weight=2, closed)
        # total_weight=6, closed_weight=2  => PMI = 2/6 * 100 ≈ 33.33
        records = [
            _ads("Active", "1 - Critical"),
            _ads("Closed", "3 - Medium"),
        ]
        result = self.calc.calculate(records)
        assert result.pmi_score == pytest.approx(100 * 2 / 6, rel=1e-4)

    def test_cq_weight_is_one(self):
        # 1 CQ open (weight=1), 1 CQ closed (weight=1) => PMI = 50%
        records = [_cq("Open"), _cq("Resolved")]
        result = self.calc.calculate(records)
        assert result.pmi_score == pytest.approx(50.0)

    def test_total_risk_accumulated(self):
        records = [_cq("Open", score=10.0, probability=0.5),   # risk = 5
                   _cq("Open", score=4.0, probability=0.25)]   # risk = 1
        result = self.calc.calculate(records)
        assert result.total_risk == pytest.approx(6.0)

    def test_risk_none_ignored(self):
        records = [
            {"source": "ClearQuest", "status": "Open",
             "score": None, "probability": None, "risk": None},
        ]
        result = self.calc.calculate(records)
        assert result.total_risk == pytest.approx(0.0)

    def test_open_by_severity_counts(self):
        records = [
            _ads("Active", "1 - Critical"),
            _ads("Active", "1 - Critical"),
            _ads("Active", "2 - High"),
            _ads("Closed", "1 - Critical"),
        ]
        result = self.calc.calculate(records)
        assert result.open_by_severity["1 - Critical"] == 2
        assert result.open_by_severity["2 - High"] == 1

    def test_unknown_severity_defaults_to_weight_1(self):
        records = [_ads("Active", "Unknown Severity")]
        result = self.calc.calculate(records)
        assert result.weighted_total == pytest.approx(1.0)


class TestPMICalculatorPhaseEvaluation:
    def _calc_with_targets(self):
        targets = [
            PhaseTarget("SIT", pmi_threshold=60.0, max_open_critical=5, max_open_high=20),
            PhaseTarget("UAT", pmi_threshold=75.0, max_open_critical=2, max_open_high=10),
            PhaseTarget("Production", pmi_threshold=90.0, max_open_critical=0, max_open_high=3),
        ]
        return PMICalculator(phase_targets=targets)

    def test_meets_sit_target(self):
        # PMI = 80%, 0 critical open, 1 high open
        records = (
            [_ads("Closed", "1 - Critical")] * 8 +
            [_ads("Active", "2 - High")] * 1 +
            [_ads("Closed", "3 - Medium")] * 1
        )
        calc = self._calc_with_targets()
        result = calc.calculate(records)
        sit_eval = next(e for e in result.phase_evaluations if e["phase"] == "SIT")
        assert sit_eval["meets_target"] is True

    def test_fails_production_if_critical_open(self):
        # 1 open critical => fails Production (max_open_critical=0)
        records = [_ads("Active", "1 - Critical"), _ads("Closed", "3 - Medium")] * 5
        calc = self._calc_with_targets()
        result = calc.calculate(records)
        prod_eval = next(e for e in result.phase_evaluations if e["phase"] == "Production")
        assert prod_eval["meets_target"] is False
        assert prod_eval["meets_critical_limit"] is False

    def test_fails_if_pmi_below_threshold(self):
        # All open => PMI = 0
        records = [_ads("Active"), _ads("Active")]
        calc = self._calc_with_targets()
        result = calc.calculate(records)
        for ev in result.phase_evaluations:
            assert ev["meets_pmi"] is False
            assert ev["meets_target"] is False

    def test_no_phase_targets_empty_evaluations(self):
        calc = PMICalculator()
        result = calc.calculate([_ads("Closed")])
        assert result.phase_evaluations == []


class TestPMICalculatorCustomConfig:
    def test_custom_severity_weights(self):
        weights = {"Blocker": 10.0, "Minor": 1.0}
        calc = PMICalculator(severity_weights=weights, closed_statuses={"Fixed"})
        records = [
            {"source": "ADS", "status": "Open", "severity": "Blocker",
             "score": None, "probability": None, "risk": None},
            {"source": "ADS", "status": "Fixed", "severity": "Minor",
             "score": None, "probability": None, "risk": None},
        ]
        result = calc.calculate(records)
        # weighted_total=11, weighted_closed=1 => PMI = 1/11 * 100
        assert result.pmi_score == pytest.approx(100 * 1 / 11, rel=1e-4)

    def test_custom_closed_statuses(self):
        calc = PMICalculator(closed_statuses={"Done", "Deployed"})
        records = [_ads("Done"), _ads("Deployed"), _ads("Active")]
        result = calc.calculate(records)
        assert result.closed_records == 2
        assert result.open_records == 1


class TestPMIResultStr:
    def test_str_contains_pmi_score(self):
        calc = PMICalculator()
        result = calc.calculate([_ads("Closed"), _ads("Active")])
        output = str(result)
        assert "PMI Score" in output
        assert "%" in output
