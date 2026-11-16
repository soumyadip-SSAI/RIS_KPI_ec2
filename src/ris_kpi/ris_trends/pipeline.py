"""RIS Trends KPI (modular version of code_notebooks/RIS_Trends_v6 in_use.ipynb). All paths and settings are in
config.RisTrends.

    ris-kpi ris-trends

Reads the silver tables from RisTrends.SILVER_INPUT_DIR and writes RisTrends.OUTPUT_DIR/ris_trends_dw.csv.
DB id columns (UPC_ID, Survey_ID, Survey_Source_ID) are not created here; they are added on push.
"""
import logging
import time

from ris_kpi.common.io import save_csv
from ris_kpi.config import RisTrends as cfg
from ris_kpi.ris_trends.categories import build_category_table, merge_categories
from ris_kpi.ris_trends.filters import filter_contract_upcs, filter_pavement_types, filter_upcs, log_table_summary
from ris_kpi.ris_trends.loaders import load_contract_upcs, load_silver_tables, load_threshold_mapping
from ris_kpi.ris_trends.kpi_metrics import build_ris_trends
from ris_kpi.ris_trends.output import finalize_ris_trends
from ris_kpi.ris_trends.pci import attach_pci

log = logging.getLogger(__name__)


def run_ris_trends():
    """Returns the ris_trends_dw.csv path."""
    start = time.time()
    # --- 1. Load & filter silver tables ---
    tables = load_silver_tables(cfg.SILVER_INPUT_DIR)
    tables = filter_upcs(tables, cfg.KEEP_UPCS)
    tables = filter_pavement_types(tables, cfg.KEEP_PAVEMENT_TYPES)
    log_table_summary(tables)

    # --- 2. Reference data ---
    cm_upcs = load_contract_upcs(cfg.PROJECT_MASTER_PATH, cfg.FILTER_BY_PROJECT_MASTER)
    thresholds = load_threshold_mapping(cfg.SILVER_INPUT_DIR, cfg.THRESHOLD_MAPPING_TABLE)

    # --- 3. Roughness_Average / Average_Rutting_Depth per grain ---
    ris_trends_df = build_ris_trends(
        tables["master_roughness_parent"], tables["master_rutting_parent"], cfg.USE_BREACH_FLAG
    )

    # --- 4. PCI_Value from 1 km chainage buckets ---
    ris_trends_df = attach_pci(
        ris_trends_df,
        tables["master_chainage"],
        [tables["master_roughness_parent"], tables["master_rutting_parent"]],
    )

    # --- 5. Project-master filter ---
    ris_trends_df = filter_contract_upcs(ris_trends_df, cm_upcs)

    # --- 6. CA / IRC condition categories (3 rows per grain) ---
    cat_df = build_category_table(tables, thresholds)
    ris_trends_df = merge_categories(ris_trends_df, cat_df, cm_upcs)

    # --- 7. Final table -> CSV ---
    ris_trends_dw = finalize_ris_trends(ris_trends_df)
    log.info("ris_trends_dw finalised — %s rows × %s cols", f"{len(ris_trends_dw):,}", ris_trends_dw.shape[1])

    path = save_csv(ris_trends_dw, cfg.OUTPUT_DIR, cfg.RIS_TRENDS_OUTPUT_NAME)
    log.info("RIS trends done in %.1fs — %s", time.time() - start, path)
    return path
