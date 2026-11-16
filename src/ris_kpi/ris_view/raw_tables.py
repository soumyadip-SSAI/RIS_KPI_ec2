"""Defect status tables (dlm_defect_case, udm_defect_reference), read on every run from RisView.STATUS_DIR
(on S3, written there by a separate DB export job). Nothing is kept locally.
"""
import logging

import pandas as pd

from ris_kpi.common import s3
from ris_kpi.common.io import find_table_file, local_file, read_text_csv, suffix_of

log = logging.getLogger(__name__)

# Columns the RIS view reads from each table; a source without them fails before any work is done
REQUIRED_COLUMNS = {
    "dlm_defect_case": ["defect_reference_id", "current_status", "defect_type", "record_level"],
    "udm_defect_reference": ["id", "defect_collection", "defect_id"],
}


def read_db_table(location):
    """All columns as text, empty cells as null (as the original DB fetch returned them)."""
    if suffix_of(location) == ".parquet":
        with local_file(location) as path:
            df = pd.read_parquet(path)
        return df.astype("string").astype(object).where(df.notna(), None)
    return read_text_csv(location, empty_as_null=True)


def load_db_tables(status_dir, tables):
    """{table: DataFrame} for <status_dir>/<table>.csv|.parquet."""
    out = {}
    for table in tables:
        location = find_table_file(status_dir, table)
        df = read_db_table(location)
        missing = [c for c in REQUIRED_COLUMNS.get(table, []) if c not in df.columns]
        if missing:
            raise ValueError(f"{table} ({location}) has no column(s) {', '.join(missing)}")
        meta = s3.head(location) if s3.is_s3_uri(location) else None
        written = f" (last written {meta['LastModified']:%Y-%m-%d %H:%M %Z})" if meta else ""
        log.info("Loaded %-22s %8s rows from %s%s", table, f"{len(df):,}", location, written)
        out[table] = df
    return out
