"""Main entry point for the PMI Tracking pipeline."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from src.ads_connector import ADSConnector
from src.clearquest_connector import ClearQuestConnector
from src.database import Database
from src.field_mapper import map_records
from src.pmi_calculator import PhaseTarget, PMICalculator

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict[str, Any]:
    """Load and return the YAML configuration file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the file cannot be parsed.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _build_phase_targets(pmi_config: dict[str, Any]) -> list[PhaseTarget]:
    """Build PhaseTarget list from the ``pmi.phase_targets`` config section."""
    targets: list[PhaseTarget] = []
    for phase_name, settings in pmi_config.get("phase_targets", {}).items():
        targets.append(
            PhaseTarget(
                name=phase_name,
                pmi_threshold=float(settings.get("pmi_threshold", 0.0)),
                max_open_critical=int(settings.get("max_open_critical", 0)),
                max_open_high=int(settings.get("max_open_high", 0)),
            )
        )
    return targets


def run(config_path: str) -> None:
    """Execute the full PMI tracking pipeline.

    Steps:
    1. Load configuration.
    2. Fetch Bug work items from ADS (Earth + LCM Tracker, Type=Bug).
    3. Fetch PD and EI records from ClearQuest (Earth project).
    4. Map all records into the common schema.
    5. Persist combined records to SQLite database.
    6. Calculate and print the PMI.

    Args:
        config_path: Path to the YAML configuration file.
    """
    config = load_config(config_path)

    # ── ADS ──────────────────────────────────────────────────────────────────
    ads_cfg = config.get("ads", {})
    pat = os.environ.get("ADS_PAT") or ads_cfg.get("personal_access_token", "")
    ads_connector = ADSConnector(
        url=ads_cfg["url"],
        organization=ads_cfg.get("organization", ""),
        personal_access_token=pat,
    )
    ads_records = ads_connector.fetch_all_projects(
        projects=ads_cfg.get("projects", []),
        fields=ads_cfg.get("fields"),
    )
    logger.info("ADS: fetched %d records.", len(ads_records))

    # ── ClearQuest ───────────────────────────────────────────────────────────
    cq_cfg = config.get("clearquest", {})
    cq_password = os.environ.get("CQ_PASSWORD") or cq_cfg.get("password", "")
    cq_connector = ClearQuestConnector(
        url=cq_cfg["url"],
        username=cq_cfg.get("username", ""),
        password=cq_password,
        database=cq_cfg.get("database", ""),
    )
    cq_records = cq_connector.fetch_all_types(
        project=cq_cfg.get("project", "Earth"),
        record_types=cq_cfg.get("record_types", ["PD", "EI"]),
        fields=cq_cfg.get("fields"),
    )
    logger.info("ClearQuest: fetched %d records.", len(cq_records))

    # ── Field mapping ─────────────────────────────────────────────────────────
    combined = map_records(ads_records, cq_records)
    logger.info("Combined: %d records after mapping.", len(combined))

    # ── Database ──────────────────────────────────────────────────────────────
    db_cfg = config.get("database", {})
    db_path = db_cfg.get("path", "pmi_tracking.db")
    with Database(db_path) as db:
        db.upsert_records(combined)
        all_records = db.query_all()

    # ── PMI calculation ───────────────────────────────────────────────────────
    pmi_cfg = config.get("pmi", {})
    severity_weights = pmi_cfg.get("severity_weights")
    closed_statuses = set(pmi_cfg.get("status_closed", []))
    phase_targets = _build_phase_targets(pmi_cfg)

    calculator = PMICalculator(
        severity_weights=severity_weights,
        closed_statuses=closed_statuses or None,
        phase_targets=phase_targets,
    )
    result = calculator.calculate(all_records)

    print("\n" + "=" * 60)
    print("  Product Maturity Index (PMI) Report")
    print("=" * 60)
    print(result)
    print("=" * 60 + "\n")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PMI Tracking – calculate Product Maturity Index "
                    "from ADS and ClearQuest data."
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to the YAML configuration file (default: config/config.yaml).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
    )

    try:
        run(args.config)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
