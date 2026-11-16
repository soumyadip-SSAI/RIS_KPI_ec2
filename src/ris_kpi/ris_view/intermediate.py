"""RIS view step 2 — affected-length intermediate (modular version of
code_notebooks/Affected length intermediate logic v3 in_use.ipynb, on the smallest-reporting-interval grain).

Reads the silver tables and the reporting intervals from RisView.SILVER_INPUT_DIR and the silver defect ids /
statuses from RisView.SILVER_STATUS_DIR (output of step 1), and writes final_intermediate.csv to
RisView.INTERMEDIATE_DIR: one row per
smallest-reporting-interval window of each upc / zone / phase / cycle, with defect flags, affected lengths, ids
and statuses.

    ris-kpi ris-view --step intermediate        # this step only
"""
import logging

from ris_kpi.config import RisView as cfg
from ris_kpi.ris_view.defect_ids import attach_segment_ids
from ris_kpi.ris_view.defect_report import SOURCE_TABLES, SRC_COLS, build_defect_report, prepare_source
from ris_kpi.common.keys import filter_upcs
from ris_kpi.ris_view.interval_spine import build_interval_spine, flag_interval_spine
from ris_kpi.common.io import save_csv
from ris_kpi.ris_view.loaders import load_table
from ris_kpi.ris_view.reporting_intervals import load_reporting_intervals

log = logging.getLogger("intermediate_logic")

# id columns of final_intermediate (statuses follow in the same order)
ID_COLUMNS = ["roughness_parent_defect_id", "rutting_parent_defect_id", "cracking_defect_id"]


def run():
    """Returns final_intermediate."""
    # --- 1. Load sources ---
    # Roughness / rutting parent and child tables are optional: a missing one is treated as empty and routing
    # falls back to the next source. Cracking uses only the child 10m table (CRACKING_TABLE)
    sources = {key: prepare_source(load_table(cfg.SILVER_INPUT_DIR, name, optional=True, columns=SRC_COLS))
               for key, name in SOURCE_TABLES.items()}
    sources["cracking"] = prepare_source(load_table(cfg.SILVER_INPUT_DIR, cfg.CRACKING_TABLE))
    chainage = load_table(cfg.SILVER_INPUT_DIR, "master_chainage")
    ri = load_reporting_intervals(cfg.SILVER_INPUT_DIR, cfg.REPORTING_INTERVALS_TABLE, cfg.DEFAULT_INTERVAL)

    # Optional UPC filter (KEEP_UPCS empty = all UPCs); every row grain includes upc, so UPCs are independent
    if cfg.KEEP_UPCS:
        log.info("KEEP_UPCS: %s", ", ".join(cfg.KEEP_UPCS))
        sources = {key: filter_upcs(df, cfg.KEEP_UPCS) for key, df in sources.items()}
        chainage = filter_upcs(chainage, cfg.KEEP_UPCS)
        ri = filter_upcs(ri, cfg.KEEP_UPCS)
        log.info("master_chainage rows after KEEP_UPCS: %s", f"{len(chainage):,}")

    # --- 2. Metric per reporting-interval window, flagged against the threshold
    #        (parent / child 100m as-is, else the child measures inputs averaged per window, then the formula) ---
    defect_report = build_defect_report(sources, ri)

    # --- 3. Rows on the smallest reporting interval per upc / zone / phase / cycle -> flags, affected lengths ---
    final = flag_interval_spine(build_interval_spine(chainage, ri, cfg.DEFAULT_INTERVAL), defect_report)

    # --- 4. Roughness / rutting parent and cracking ids + statuses (tables from step 1);
    #        cracking_status: Open if any cracking child in the row is Open, Closed if all are Closed ---
    final = attach_segment_ids(final, cfg.SILVER_STATUS_DIR, cfg.CRACKING_TABLE, ID_COLUMNS,
                               rollup_status=["cracking_defect_id"])
    save_csv(final, cfg.INTERMEDIATE_DIR, cfg.INTERMEDIATE_NAME)
    return final
