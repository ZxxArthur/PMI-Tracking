# PMI-Tracking

Calculate Product Maturity Index by accessing data from ADS and ClearQuest automatically.

## Overview

PMI-Tracking is a Python pipeline that:

1. **Fetches Bug work items from ADS** (Azure DevOps Services) for projects *Earth* and *LCM Tracker*, filtered to `Type = Bug`. Fields retrieved: ID, Brief (Title), Component (Area Path), Severity, Status, Generic02–05.
2. **Fetches defect records from ClearQuest** for project *Earth*, record types `PD` and `EI`. Fields retrieved: ID, Brief (Headline), Component, Status, Score, Probability.
3. **Maps both sources into a common schema** – combining all fields and deriving a `risk = score × probability` value for ClearQuest records.
4. **Persists the combined data** in a local SQLite database (upsert on each run).
5. **Calculates the PMI** – a severity-weighted defect-closure rate – and evaluates whether the result meets configurable next-phase targets (SIT, UAT, Production).

## Project Structure

```
PMI-Tracking/
├── config/
│   └── config.yaml          # All settings (credentials, projects, PMI thresholds)
├── src/
│   ├── ads_connector.py     # Azure DevOps REST API client
│   ├── clearquest_connector.py  # ClearQuest REST API client
│   ├── field_mapper.py      # Maps ADS & CQ records to common schema
│   ├── database.py          # SQLite persistence layer
│   └── pmi_calculator.py    # PMI calculation & phase evaluation
├── tests/
│   ├── test_ads_connector.py
│   ├── test_clearquest_connector.py
│   ├── test_database.py
│   ├── test_field_mapper.py
│   └── test_pmi_calculator.py
├── main.py                  # CLI entry point
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
```

## Configuration

Edit `config/config.yaml` to fill in:

| Section | Key | Description |
|---|---|---|
| `ads` | `url` | Azure DevOps organisation URL |
| `ads` | `organization` | Organisation name |
| `ads` | `personal_access_token` | PAT (or set `ADS_PAT` env var) |
| `ads` | `projects` | List of `{name, work_item_type}` entries |
| `clearquest` | `url` | ClearQuest REST API base URL |
| `clearquest` | `username` / `password` | Credentials (or set `CQ_PASSWORD` env var) |
| `clearquest` | `database` | ClearQuest schema repository name |
| `pmi` | `severity_weights` | Numeric weight per ADS severity label |
| `pmi` | `status_closed` | Status values that count as "closed" |
| `pmi` | `phase_targets` | PMI threshold & open-defect limits per phase |

Sensitive credentials can be provided via environment variables to avoid storing them in the config file:

```bash
export ADS_PAT="<your-personal-access-token>"
export CQ_PASSWORD="<your-clearquest-password>"
```

## Usage

```bash
python main.py                         # uses config/config.yaml by default
python main.py --config path/to/config.yaml
python main.py --log-level DEBUG
```

### Sample output

```
============================================================
  Product Maturity Index (PMI) Report
============================================================
PMI Score         : 82.50%
Total records     : 120
Open records      : 21
Closed records    : 99
Weighted total    : 228.00
Weighted open     : 39.00
Weighted closed   : 189.00
Total CQ risk     : 12.4000
Open by severity  :
  1 - Critical: 1
  2 - High: 5
  3 - Medium: 15
Phase evaluations :
  [PASS] SIT: PMI 82.5% (target ≥ 60.0%)
  [PASS] UAT: PMI 82.5% (target ≥ 75.0%)
  [FAIL] Production: PMI 82.5% (target ≥ 90.0%)
============================================================
```

## PMI Calculation

```
PMI = (weighted_closed / weighted_total) × 100 %
```

* Each **ADS Bug** contributes its severity weight (Critical=4, High=3, Medium=2, Low=1).
* Each **ClearQuest PD/EI** record contributes a uniform weight of 1; its `score × probability` is tracked as a separate *risk* metric.
* If there are no records, PMI defaults to **100 %**.

## Running Tests

```bash
python -m pytest tests/ -v
```
