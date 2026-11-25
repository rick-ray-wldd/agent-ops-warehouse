#!/usr/bin/env python3
"""Grade the three exercises against the Python answer key. Needs the built warehouse.duckdb (make build).

usage: python3 exercises/grade.py [1|2|3 ...]
"""
from pathlib import Path
import json
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[1]
KEY = json.loads((ROOT / 'data/expected/metrics.json').read_text())
CHECKS = {
    '1': ('01_decision_wait.sql', 'decision_wait_daily', 'day', ['decisions', 'p50_minutes', 'p90_minutes']),
    '2': ('02_work_sessions.sql', 'work_sessions_daily', 'day', ['sessions', 'total_minutes', 'longest_minutes']),
    '3': ('03_rework_share.sql', 'rework_by_stage', 'stage', ['rework_count', 'share_pct']),
}


def grade(con, number):
    file, section, key, fields = CHECKS[number]
    sql = (ROOT / 'exercises' / file).read_text()
    try:
        cur = con.execute(sql)
    except duckdb.Error as exc:
        return False, f'query failed: {exc}'
    cols = [d[0] for d in cur.description]
    want = {'day': 'date_day'}.get(key, key)
    missing = [c for c in [want] + fields if c not in cols]
    if missing:
        return False, f'missing columns: {missing} (got {cols})'
    got = {str(r[cols.index(want)]): r for r in cur.fetchall()}
    expected = {str(row[key]): row for row in KEY[section]}
    if set(got) != set(expected):
        return False, f'rows differ: {len(got)} returned, {len(expected)} expected; e.g. extra {sorted(set(got) - set(expected))[:3]}, missing {sorted(set(expected) - set(got))[:3]}'
    for k, row in expected.items():
        for f in fields:
            a, b = got[k][cols.index(f)], row[f]
            if a is None or abs(float(a) - float(b)) > (0.01 if f == 'share_pct' else 0.001):
                return False, f'{want}={k}: {f} is {a}, expected {b}'
    return True, f'{len(expected)} rows match'


def main(argv):
    con = duckdb.connect(str(ROOT / 'warehouse.duckdb'), read_only=True)
    ok_all = True
    for n in (argv or sorted(CHECKS)):
        ok, why = grade(con, n)
        ok_all &= ok
        print(f'exercise {n}: {"PASS" if ok else "FAIL"} - {why}')
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
