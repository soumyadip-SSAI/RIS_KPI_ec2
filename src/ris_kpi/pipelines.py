"""The full KPI run, called in-process (from the CLI or from an orchestrator such as Airflow).

    run_full()   ris_view -> ris_trends

ris_view reads the defect status tables straight from S3; ris_trends uses only the silver tables.
When only defect statuses changed, run the RIS view alone (ris_kpi.ris_view.run_ris_view / `ris-kpi ris-view`).
"""
import logging
import time

from ris_kpi.ris_trends import run_ris_trends
from ris_kpi.ris_view import run_ris_view

log = logging.getLogger(__name__)

# name -> (function, steps it depends on); run in this order
STEPS = {
    # S3 status tables + old_silver_data -> silver_data_with_status -> final_intermediate -> ris_view_dw.csv
    "ris_view": (run_ris_view, []),
    # old_silver_data -> ris_trends_dw.csv
    "ris_trends": (run_ris_trends, []),
}


def run_full(only=None, keep_going=False):
    """Run the steps in order. Returns {step: (status, seconds, error)} with status OK / FAILED / SKIPPED.

    only:        run only these steps; a dependency that is not selected counts as done (its earlier output is used)
    keep_going:  after a failure, still run the steps that do not depend on the failed one
    """
    selected = [name for name in STEPS if not only or name in only]
    results = {}

    for name in selected:
        func, deps = STEPS[name]
        failed_deps = [d for d in deps if results.get(d, ("OK",))[0] != "OK"]
        stopped = any(r[0] == "FAILED" for r in results.values()) and not keep_going
        if stopped or failed_deps:
            reason = f"{', '.join(failed_deps)} did not succeed" if failed_deps else "stopped after failure"
            results[name] = ("SKIPPED", 0.0, reason)
            continue
        log.info("%s %s %s", "=" * 25, name, "=" * 25)
        start = time.time()
        try:
            func()
            results[name] = ("OK", time.time() - start, "")
        except Exception as e:
            log.exception("%s FAILED", name)
            results[name] = ("FAILED", time.time() - start, f"{type(e).__name__}: {e}")

    log.info("%s summary %s", "=" * 25, "=" * 25)
    for name, (status, seconds, error) in results.items():
        log.info("%-12s %-8s %6.1fs%s", name, status, seconds, f"  -> {error}" if error else "")
    return results
