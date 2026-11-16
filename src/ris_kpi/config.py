"""All settings for the RIS KPI pipelines, in one place, grouped by pipeline step.

Where the data lives is chosen with the RIS_KPI_STORAGE environment variable:
  s3     (default) read the inputs from S3 and write every output to S3 — the EC2 runs
  local  input_data/ and output_data/ in the repository — development / before-after checks without AWS access

AWS credentials are not set here: boto3 finds them itself (the EC2 instance role, or `aws configure` locally).
"""
import os
from pathlib import Path

STORAGE = (os.getenv("RIS_KPI_STORAGE") or "s3").strip().lower()

if STORAGE == "s3":
    S3_ROOT = "s3://dhms-new-stgae/NSV"
    # Inputs
    STATUS_DIR = f"{S3_ROOT}/DHMS/Staging/Latest"                # dlm_defect_case.csv, udm_defect_reference.csv
    SILVER_INPUT_DIR = f"{S3_ROOT}/Silver/old_silver_data_for_test"  # master_*.csv, master_chainage, ...
    PROJECT_MASTER_PATH = f"{SILVER_INPUT_DIR}/project_master.xlsx"
    # Outputs
    SILVER_STATUS_DIR = f"{S3_ROOT}/Silver_Status_Updated"       # silver tables + status columns
    INTERMEDIATE_DIR = f"{S3_ROOT}/Gold_Intermediate"            # final_intermediate.csv
    KPI_OUTPUT_DIR = f"{S3_ROOT}/Gold_kpi_status"                # ris_view_dw.csv, ris_trends_dw.csv
elif STORAGE == "local":
    # src/ris_kpi/config.py -> repository root (RIS_KPI_ROOT overrides it, e.g. for a non-editable install)
    ROOT_DIR = Path(os.getenv("RIS_KPI_ROOT") or Path(__file__).resolve().parents[2])
    INPUT_DATA_DIR = ROOT_DIR / "input_data"
    OUTPUT_DATA_DIR = ROOT_DIR / "output_data"
    # Inputs
    STATUS_DIR = INPUT_DATA_DIR / "status_tables"
    SILVER_INPUT_DIR = INPUT_DATA_DIR / "old_silver_data"
    PROJECT_MASTER_PATH = INPUT_DATA_DIR / "project_master.xlsx"
    # Outputs
    SILVER_STATUS_DIR = OUTPUT_DATA_DIR / "silver_data_with_status"
    INTERMEDIATE_DIR = OUTPUT_DATA_DIR / "output_kpi_data"
    KPI_OUTPUT_DIR = OUTPUT_DATA_DIR / "output_kpi_data"
else:
    raise ValueError(f"RIS_KPI_STORAGE must be 's3' or 'local', not {STORAGE!r}")


class RisView:
    """RIS view (ris_kpi.ris_view): silver status -> intermediate -> ris_view_dw."""
    # UPCs in '/' form (e.g. ["N/02015/03002/GJ", "N/07024/01001/GJ"]). Empty = all UPCs.
    KEEP_UPCS = []

    # --- Input ---
    SILVER_INPUT_DIR = SILVER_INPUT_DIR
    # Defect status tables, read from STATUS_DIR on every run (kept up to date there by the DB export job)
    STATUS_DIR = STATUS_DIR
    STATUS_TABLES = ["dlm_defect_case", "udm_defect_reference"]
    # Contract-module project master (.csv / .xlsx with a UPC/upc column); also gives length / state / NH
    PROJECT_MASTER_PATH = PROJECT_MASTER_PATH
    # True = keep only UPCs present in the project master | False = no project-master filter (view step)
    FILTER_BY_PROJECT_MASTER = True

    # --- Sources ---
    # Reporting intervals: file name without extension, read from SILVER_INPUT_DIR as .csv / .parquet / .xlsx
    # (replaces the Databricks table nhai_dhms.ris_kpi_output.upc_reporting_intervals)
    REPORTING_INTERVALS_TABLE = "upc_reporting_intervals"
    # Interval (m) used where a reporting interval is empty or a standard (CA/IRC) has no row
    DEFAULT_INTERVAL = 100
    # Cracking source (file name without extension). The notebooks used the 10m table master_cracking.
    CRACKING_TABLE = "master_cracking"

    # --- Output (file names without .csv) ---
    # Silver tables with defect_reference_id / current_status / final_status (input of the next two steps)
    SILVER_STATUS_DIR = SILVER_STATUS_DIR
    # Intermediate step output, input of the view step (Databricks: <OUTPUT_SCHEMA>.final_intermediate)
    INTERMEDIATE_DIR = INTERMEDIATE_DIR
    INTERMEDIATE_NAME = "final_intermediate"
    KPI_OUTPUT_DIR = KPI_OUTPUT_DIR
    RIS_VIEW_DW_NAME = "ris_view_dw"


class RisTrends:
    """RIS trends (ris_kpi.ris_trends). Reads only the silver tables, not the status tables."""
    # UPCs in '/' form. Empty = all UPCs.
    KEEP_UPCS = []
    # "Cement concrete" is read as "Cement Concrete" before filtering (PAVEMENT_TYPE_ALIASES in ris_trends/filters.py)
    KEEP_PAVEMENT_TYPES = ["Asphalt", "Cement Concrete", "Hybrid"]
    # True = Roughness_Average / Average_Rutting_Depth only from breach_flag == 1 rows
    USE_BREACH_FLAG = False

    # --- Input ---
    SILVER_INPUT_DIR = SILVER_INPUT_DIR
    # Threshold mapping (Databricks: dlm_threshold_mapping_display): file name without extension, read from
    # SILVER_INPUT_DIR as .parquet / .csv / .xlsx. Required.
    THRESHOLD_MAPPING_TABLE = "dlm_threshold_mapping"
    # True = keep only UPCs present in the project master | False = no project-master filter
    FILTER_BY_PROJECT_MASTER = True
    # Only read when the filter is on
    PROJECT_MASTER_PATH = PROJECT_MASTER_PATH

    # --- Output ---
    OUTPUT_DIR = KPI_OUTPUT_DIR
    RIS_TRENDS_OUTPUT_NAME = "ris_trends_dw"
