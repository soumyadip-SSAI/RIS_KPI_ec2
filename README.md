# RIS KPI

Builds the RIS KPI tables `ris_view_dw` and `ris_trends_dw` from the silver defect tables and the defect status
tables (`dlm_defect_case`, `udm_defect_reference`). Every input is read from S3 and every output is written to S3;
nothing is kept on the machine that runs it.

| Command | Use it when | Writes |
|---|---|---|
| `ris-kpi run` | Full KPI creation (new survey data / silver tables) | everything below |
| `ris-kpi ris-view` | Only defect statuses changed (cases closed, assigned, ...) | silver with status, intermediate, `ris_view_dw.csv` |

## Where the data lives (`s3://dhms-new-stgae/NSV/...`)

| | S3 location | Contents |
|---|---|---|
| in  | `DHMS/Staging/Latest/` | `dlm_defect_case.csv`, `udm_defect_reference.csv` (written by the separate DB export job) |
| in  | `Silver/old_silver_data_for_test/` | silver tables (`master_*.csv`, `master_chainage.csv`, `upc_reporting_intervals.csv`, `dlm_threshold_mapping.csv`) and `project_master.xlsx` |
| out | `Silver_Status_Updated/` | silver defect tables + `defect_reference_id`, `current_status`, `final_status` |
| out | `Gold_Intermediate/` | `final_intermediate.csv` |
| out | `Gold_kpi_status/` | `ris_view_dw.csv`, `ris_trends_dw.csv` |

Each run overwrites the files of the same name. The locations are set at the top of `src/ris_kpi/config.py`.
AWS access comes from boto3's usual chain: the EC2 instance role (needs `s3:GetObject` on the inputs and
`s3:PutObject` on the outputs), or `aws configure` locally. No credentials are stored in the repo.

## Running on the EC2 instance (SSM console)

Needs Python 3.10 or newer (`python3 --version`); on Ubuntu, `apt install python3-venv` if `venv` is missing.

First time:

```bash
sudo su
cd ~
git clone <repo-url> ris_kpi
cd ris_kpi
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
ris-kpi run
```

Every later run (after a new push):

```bash
sudo su
cd ~/ris_kpi
git pull
source .venv/bin/activate
pip install -e .                 # only needed when pyproject.toml changed; harmless otherwise
ris-kpi run                      # or: ris-kpi ris-view   when only statuses changed
```

A full run takes several minutes. If the SSM session may time out, run it in the background with a log file:

```bash
nohup ris-kpi run > run_$(date +%F_%H%M).log 2>&1 &
tail -f run_*.log                # Ctrl+C stops watching, not the run
```

The run ends with a summary (`OK` / `FAILED` / `SKIPPED` per step); exit code 1 means something failed.

## Commands

```bash
ris-kpi run                      # ris_view -> ris_trends
ris-kpi run --keep-going         # still run ris_trends when ris_view fails

ris-kpi ris-view [--step silver-status intermediate view]    # single steps
ris-kpi ris-trends
```

`python -m ris_kpi ...` works the same way. The same steps can be called from Python (for example from an Airflow
task):

```python
from ris_kpi.pipelines import run_full
from ris_kpi.ris_view import run_ris_view
```

## Steps

| Step | Reads | Writes |
|---|---|---|
| `ris_view` 1. `silver-status` | status tables, silver defect tables | `Silver_Status_Updated/*.csv` |
| `ris_view` 2. `intermediate` | silver parent / child tables, `master_chainage`, `upc_reporting_intervals`, `Silver_Status_Updated` | `Gold_Intermediate/final_intermediate.csv` |
| `ris_view` 3. `view` | `Silver_Status_Updated` (defect counts, Closed lengths), child 10m tables (IRC counts), `project_master.xlsx`, `final_intermediate.csv` (Open lengths, `Total` rows) | `Gold_kpi_status/ris_view_dw.csv` |
| `ris_trends` | `master_{roughness,rutting}_{parent,child_10m}`, `master_chainage`, `dlm_threshold_mapping`, `project_master.xlsx` | `Gold_kpi_status/ris_trends_dw.csv` |

`ris_trends` does not use the status tables, so after a status-only change running `ris-kpi ris-view` is enough.
DB id columns (`UPC_ID`, `Survey_ID`, ...) are added when the outputs are pushed to the DB, not here.

Affected lengths in brief: Open comes from `final_intermediate` (roughness, rutting, cracking; ravelling and
pothole 0), Closed from the silver tables (breached rows), and cracking Open = Open - Closed. An intermediate row is
flagged when at least half of it lies inside breached windows. The detailed rules are in the docstrings of
`ris_view/status.py`, `defect_counts.py` and `affected_length.py`.

## Settings

All in `src/ris_kpi/config.py`: the S3 locations at the top, then one class per step: `RisView` (`KEEP_UPCS`,
project-master filter, reporting intervals, output names), `RisTrends` (`KEEP_UPCS`, pavement types,
`USE_BREACH_FLAG`).

## Local runs (development, before / after checks)

Set `RIS_KPI_STORAGE=local` to use folders in the repository instead of S3 (no AWS access needed):

- inputs: `input_data/status_tables/` (the two status CSVs), `input_data/old_silver_data/`,
  `input_data/project_master.xlsx`
- outputs: `output_data/silver_data_with_status/`, `output_data/output_kpi_data/`

Outputs must not change unless the KPI logic is meant to change. Before merging:

```bash
export RIS_KPI_STORAGE=local                       # PowerShell: $env:RIS_KPI_STORAGE = "local"
ris-kpi run && cp -r output_data output_data_before                               # on the old code
git checkout <your-branch>
ris-kpi run                                                                       # same input_data
ris-kpi compare output_data_before output_data                                    # exit 0 = identical
```

`populated_on` (the run time) is ignored. Unit tests (`pytest`) use an in-memory S3 stand-in, no AWS access.

## Layout

```
ris-kpi/
├── pyproject.toml              # dependencies, `ris-kpi` command, pytest settings
├── src/ris_kpi/
│   ├── cli.py                  # ris-kpi command
│   ├── config.py               # all settings (S3 locations at the top)
│   ├── pipelines.py            # run_full
│   ├── common/                 # io.py (read / write tables on S3 or disk), s3.py (boto3), keys.py (UPC / id /
│   │                           # date normalisation), logging.py
│   ├── ris_view/
│   │   ├── pipeline.py         # run_ris_view: the three steps below
│   │   ├── silver_status.py    # step 1      <- raw_tables.py, status.py
│   │   ├── intermediate.py     # step 2      <- reporting_intervals.py, defect_report.py, measure_windows.py,
│   │   │                       #                interval_spine.py, spine_flags.py, defect_ids.py
│   │   ├── view.py             # step 3      <- project_master.py, defect_counts.py, affected_length.py, output.py
│   │   └── loaders.py          # step-specific table loaders
│   ├── ris_trends/
│   │   ├── pipeline.py         # run_ris_trends
│   │   ├── loaders.py, filters.py, kpi_metrics.py, pci.py, categories.py, output.py
│   │   └── spark.py            # Spark rounding / null semantics
│   └── tools/compare_outputs.py
├── tests/
├── input_data/                 # local runs only, not committed
└── output_data/                # local runs only, not committed
```
