#!/usr/bin/env python3
"""Grade the three exercises against the Python answer key. Needs the built warehouse.duckdb (make build).

A result passes only if it has the required columns, exactly one row per expected key (no duplicate, empty or
extra keys, none missing), and every value is a finite number within tolerance of the answer key.

usage: python3 exercises/grade.py [--dir FOLDER] [1|2|3 ...]   (FOLDER defaults to exercises/)
"""
from pathlib import Path
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKS = {
    '1': ('01_decision_wait.sql', 'decision_wait_daily', 'day', ['decisions', 'p50_minutes', 'p90_minutes']),
    '2': ('02_work_sessions.sql', 'work_sessions_daily', 'day', ['sessions', 'total_minutes', 'longest_minutes']),
    '3': ('03_rework_share.sql', 'rework_by_stage', 'stage', ['rework_count', 'share_pct']),
}
OUTPUT_KEY = {'day': 'date_day'}  # the answer key's field -> the column the exercise returns


def tolerance(field):
    return 0.01 if field == 'share_pct' else 0.001


def finite(value):
    """The value as a float if it is a finite number; None otherwise (NULL, NaN, infinity, text)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def compare(cols, rows, expected, key, fields):
    """(ok, reason) for a result set against the answer key rows. Pure: no database needed."""
    want = OUTPUT_KEY.get(key, key)
    missing = [c for c in [want] + fields if c not in cols]
    if missing:
        return False, f'missing columns: {missing} (got {cols})'
    if len(set(cols)) != len(cols):
        return False, f'duplicate column names: {cols}'
    seen = {}
    for r in rows:
        k = r[cols.index(want)]
        if k is None or str(k).strip() == '':
            return False, f'a row has an empty {want}'
        k = str(k)
        if k in seen:
            return False, f'{want}={k} appears more than once'
        seen[k] = r
    answer = {str(row[key]): row for row in expected}
    if set(seen) != set(answer):
        extra, absent = sorted(set(seen) - set(answer)), sorted(set(answer) - set(seen))
        return False, f'rows differ: {len(seen)} returned, {len(answer)} expected; e.g. extra {extra[:3]}, missing {absent[:3]}'
    for k, row in answer.items():
        for f in fields:
            got = seen[k][cols.index(f)]
            x = finite(got)
            if x is None:
                return False, f'{want}={k}: {f} is {got!r}, not a finite number'
            if abs(x - float(row[f])) > tolerance(f):
                return False, f'{want}={k}: {f} is {got}, expected {row[f]}'
    return True, f'{len(answer)} rows match'


def grade(con, number, folder, answer_key):
    import duckdb
    file, section, key, fields = CHECKS[number]
    sql = (folder / file).read_text()
    try:
        cur = con.execute(sql)
    except duckdb.Error as exc:
        return False, f'query failed: {exc}'
    cols = [d[0] for d in cur.description]
    return compare(cols, cur.fetchall(), answer_key[section], key, fields)


def main(argv):
    import duckdb
    folder = ROOT / 'exercises'
    if argv[:1] == ['--dir']:
        folder, argv = Path(argv[1]).resolve(), argv[2:]
    answer_key = json.loads((ROOT / 'data/expected/metrics.json').read_text())
    con = duckdb.connect(str(ROOT / 'warehouse.duckdb'), read_only=True)
    ok_all = True
    for n in (argv or sorted(CHECKS)):
        ok, why = grade(con, n, folder, answer_key)
        ok_all &= ok
        print(f'exercise {n}: {"PASS" if ok else "FAIL"} - {why}')
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
