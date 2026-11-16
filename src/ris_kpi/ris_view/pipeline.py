"""RIS view: the three steps in order. All paths and settings are in config.RisView.

    1. silver_status  status tables (S3) + old_silver_data -> silver_data_with_status
    2. intermediate   old_silver_data + silver_data_with_status -> final_intermediate.csv
    3. view           silver_data_with_status + final_intermediate.csv -> ris_view_dw.csv

A failing step raises; the steps after it are not run.
"""
import logging
import time

from ris_kpi.common.io import join
from ris_kpi.config import RisView
from ris_kpi.ris_view import intermediate, silver_status, view

log = logging.getLogger(__name__)

# CLI name -> step function, in run order
STEPS = {
    "silver-status": silver_status.run,
    "intermediate": intermediate.run,
    "view": view.run,
}


def run_ris_view(steps=None):
    """Run the given steps (default: all, in order); returns the ris_view_dw.csv path."""
    selected = [name for name in STEPS if not steps or name in steps]
    start = time.time()
    for i, name in enumerate(selected, 1):
        step_start = time.time()
        log.info("RIS view step %d/%d: %s", i, len(selected), name)
        STEPS[name]()
        log.info("RIS view step %d/%d: %s done in %.1fs", i, len(selected), name, time.time() - step_start)
    path = join(RisView.KPI_OUTPUT_DIR, f"{RisView.RIS_VIEW_DW_NAME}.csv")
    log.info("RIS view done in %.1fs — %s", time.time() - start, path)
    return path
