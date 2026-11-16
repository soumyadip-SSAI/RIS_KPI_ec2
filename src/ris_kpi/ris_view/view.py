"""RIS view step 3 — RIS view (modular version of code_notebooks/RIS View Pipeline_v2 in_use.ipynb).

Reads the silver defect tables with status from RisView.SILVER_STATUS_DIR (output of step 1), the child 10m tables
from RisView.SILVER_INPUT_DIR (IRC counts of ravelling / roughness / rutting), the project master and
final_intermediate (output of step 2, RisView.INTERMEDIATE_DIR), and writes ris_view_dw.csv to RisView.KPI_OUTPUT_DIR.
DB id columns are not created here; they are added when the output is pushed to Postgres.

    ris-kpi ris-view --step view        # this step only
"""
import logging

from ris_kpi.config import RisView as cfg
from ris_kpi.ris_view.affected_length import attach_defect_lengths, build_total_rows, subtract_closed_from_open
from ris_kpi.ris_view.defect_counts import CHILD_COLUMNS, combine_defects, count_defects
from ris_kpi.common.keys import filter_upcs
from ris_kpi.common.io import save_csv
from ris_kpi.ris_view.loaders import load_defect_table, load_intermediate
from ris_kpi.ris_view.output import build_ris_view_dw
from ris_kpi.ris_view.project_master import filter_project_upcs, load_project_master

log = logging.getLogger("ris_view")

DEFECT_TABLES = ["master_pothole", "master_ravelling_parent", "master_roughness_parent", "master_rutting_parent"]
# parent table (SILVER_STATUS_DIR) -> child 10m table (SILVER_INPUT_DIR) that gives its IRC counts
CHILD_TABLES = {
    "master_ravelling_parent": "master_ravelling_child_10m",
    "master_roughness_parent": "master_roughness_child_10m",
    "master_rutting_parent": "master_rutting_child_10m",
}


def run():
    """Returns ris_view_dw."""
    # --- 1. Load sources ---
    names = [cfg.CRACKING_TABLE] + DEFECT_TABLES
    tables = {name: load_defect_table(cfg.SILVER_STATUS_DIR, name) for name in names}
    children = {child: load_defect_table(cfg.SILVER_INPUT_DIR, child, columns=CHILD_COLUMNS)
                for child in CHILD_TABLES.values()}
    project_info = load_project_master(cfg.PROJECT_MASTER_PATH)
    intermediate = load_intermediate(cfg.INTERMEDIATE_DIR, cfg.INTERMEDIATE_NAME)

    # Optional UPC filter (KEEP_UPCS empty = all UPCs); every output row belongs to one UPC
    if cfg.KEEP_UPCS:
        log.info("KEEP_UPCS: %s", ", ".join(cfg.KEEP_UPCS))
        tables = {name: filter_upcs(df, cfg.KEEP_UPCS) for name, df in tables.items()}
        children = {name: filter_upcs(df, cfg.KEEP_UPCS) for name, df in children.items()}
        intermediate = filter_upcs(intermediate, cfg.KEEP_UPCS)

    # --- 2. Keep only project-master UPCs ---
    tables = filter_project_upcs(tables, project_info, cfg.FILTER_BY_PROJECT_MASTER)
    children = filter_project_upcs(children, project_info, cfg.FILTER_BY_PROJECT_MASTER)

    # --- 3. Defect rows (IRC of ravelling/roughness/rutting from child 10m) + project details
    #        -> breached-defect counts per grain ---
    children = {parent: children[child] for parent, child in CHILD_TABLES.items()}
    counts = count_defects(combine_defects(tables, children), project_info)

    # --- 4. Affected lengths per defect / status (source: LENGTH_SOURCE in ris_view/affected_length.py),
    #        'Total' rows from final_intermediate ---
    defect_rows = attach_defect_lengths(counts, tables, intermediate)
    total_rows = build_total_rows(intermediate, defect_rows)

    # --- 5. Cracking: Open affected length minus Closed, then final table -> CSV ---
    defect_rows = subtract_closed_from_open(defect_rows)
    ris_view_dw = build_ris_view_dw(defect_rows, total_rows)
    log.info("ris_view_dw — %s rows × %s cols", f"{len(ris_view_dw):,}", ris_view_dw.shape[1])

    save_csv(ris_view_dw, cfg.KPI_OUTPUT_DIR, cfg.RIS_VIEW_DW_NAME)
    return ris_view_dw
