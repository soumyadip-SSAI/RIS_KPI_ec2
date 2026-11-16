"""RIS view step 1 — silver status update (modular version of code_notebooks/silver_status_update.ipynb).

Reads udm_defect_reference and dlm_defect_case from RisView.STATUS_DIR (S3), adds
defect_reference_id / current_status / final_status to the silver defect tables in RisView.SILVER_INPUT_DIR and
writes them to RisView.SILVER_STATUS_DIR.

    ris-kpi ris-view --step silver-status        # this step only
"""
import logging

from ris_kpi.config import RisView as cfg
from ris_kpi.common.keys import filter_upcs
from ris_kpi.common.io import save_csv
from ris_kpi.ris_view.loaders import load_silver_table
from ris_kpi.ris_view.raw_tables import load_db_tables
from ris_kpi.ris_view.status import SILVER_KEYS, STATUS_TABLES, add_status, case_status, log_closed_case_check

log = logging.getLogger("silver_table_update")


def run():
    """Returns {table: silver table with status}."""
    # --- 1. Status tables (from S3, written there by the DB export job) ---
    db = load_db_tables(cfg.STATUS_DIR, cfg.STATUS_TABLES)
    udm_defect_reference, dlm_defect_case = db["udm_defect_reference"], db["dlm_defect_case"]
    cases = case_status(dlm_defect_case)
    if not cfg.KEEP_UPCS:
        log.info("KEEP_UPCS empty — all UPCs kept")

    # --- 2. Silver tables + status columns -> SILVER_STATUS_DIR ---
    outputs = {}
    for table, defect_collection in STATUS_TABLES.items():
        silver = filter_upcs(load_silver_table(cfg.SILVER_INPUT_DIR, table), cfg.KEEP_UPCS)
        outputs[table] = add_status(silver, defect_collection, udm_defect_reference, cases,
                                    silver_key=SILVER_KEYS.get(table, "id"))
        save_csv(outputs[table], cfg.SILVER_STATUS_DIR, table)

    # --- 3. Check: CLOSED / CANCELLED cases found in udm_defect_reference ---
    log_closed_case_check(udm_defect_reference, dlm_defect_case)
    return outputs
