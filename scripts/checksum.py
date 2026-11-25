#!/usr/bin/env python3
"""Order-independent fingerprint of a table in warehouse.duckdb (row count + hash of sorted rows)."""
from pathlib import Path
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[1]
table = sys.argv[1] if len(sys.argv) > 1 else 'fct_event'
con = duckdb.connect(str(ROOT / 'warehouse.duckdb'), read_only=True)
n, h = con.execute(f'select count(*), md5(string_agg(md5(cast(t as varchar)), \'\' order by md5(cast(t as varchar)))) from {table} t').fetchone()
print(f'{table} {n} {h}')
