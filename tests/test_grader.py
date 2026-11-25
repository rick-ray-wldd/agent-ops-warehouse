"""Grader tests. The compare() cases need only the standard library; the end-to-end cases run real SQL against
the built warehouse and are skipped when DuckDB or warehouse.duckdb is not there (run_pipeline.sh runs them)."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'exercises'))
import grade  # noqa: E402

STAGES = [{'stage': 'dispatch', 'rework_count': 22, 'share_pct': 11.96},
          {'stage': 'execution', 'rework_count': 88, 'share_pct': 47.83},
          {'stage': 'review', 'rework_count': 74, 'share_pct': 40.22}]
COLS = ['stage', 'rework_count', 'share_pct']
FIELDS = ['rework_count', 'share_pct']


def rows(data=STAGES):
    return [(r['stage'], r['rework_count'], r['share_pct']) for r in data]


def check(result_rows, cols=COLS):
    return grade.compare(cols, result_rows, STAGES, 'stage', FIELDS)


class CompareTests(unittest.TestCase):
    def test_correct_result_passes(self):
        self.assertEqual(check(rows()), (True, '3 rows match'))

    def test_within_tolerance_passes_and_outside_fails(self):
        r = rows()
        self.assertTrue(check([(r[0][0], r[0][1], r[0][2] + 0.009)] + r[1:])[0])
        ok, why = check([(r[0][0], r[0][1], r[0][2] + 0.02)] + r[1:])
        self.assertFalse(ok)
        self.assertIn('share_pct', why)

    def test_duplicate_rows_fail(self):
        ok, why = check(rows() + rows())
        self.assertFalse(ok)
        self.assertIn('more than once', why)

    def test_one_duplicated_key_with_different_values_fails(self):
        ok, why = check(rows() + [('review', 0, 0.0)])
        self.assertFalse(ok)
        self.assertIn('review appears more than once', why)

    def test_empty_keys_fail(self):
        for bad in (None, '', '  '):
            ok, why = check(rows()[:2] + [(bad, 74, 40.22)])
            self.assertFalse(ok, bad)
            self.assertIn('empty', why)

    def test_non_finite_and_non_numeric_values_fail(self):
        for bad in (float('nan'), float('inf'), float('-inf'), None, 'NaN', 'abc', True):
            r = rows()
            ok, why = check(r[:2] + [(r[2][0], r[2][1], bad)])
            self.assertFalse(ok, repr(bad))
            self.assertIn('not a finite number', why)

    def test_extra_and_missing_rows_fail(self):
        self.assertFalse(check(rows() + [('human_reply', 1, 1.0)])[0])
        self.assertFalse(check(rows()[:2])[0])

    def test_missing_or_duplicate_columns_fail(self):
        self.assertIn('missing columns', check([r[:2] for r in rows()], cols=COLS[:2])[1])
        ok, why = check([r + (r[2],) for r in rows()], cols=COLS + ['share_pct'])
        self.assertFalse(ok)
        self.assertIn('duplicate column names', why)

    def test_day_keys_compare_as_dates(self):
        expected = [{'day': '2025-01-06', 'decisions': 3, 'p50_minutes': 1.0, 'p90_minutes': 2.0}]
        import datetime as dt
        ok, _ = grade.compare(['date_day', 'decisions', 'p50_minutes', 'p90_minutes'],
                              [(dt.date(2025, 1, 6), 3, 1.0, 2.0)], expected, 'day',
                              ['decisions', 'p50_minutes', 'p90_minutes'])
        self.assertTrue(ok)


try:
    import duckdb  # noqa: F401
    BUILT = (ROOT / 'warehouse.duckdb').is_file() and (ROOT / 'data/expected/metrics.json').is_file()
except ImportError:
    BUILT = False


@unittest.skipUnless(BUILT, 'needs duckdb and a built warehouse (make all)')
class EndToEndTests(unittest.TestCase):
    """The review's edge cases as real SQL (receipts GRADER-EDGE-CASES), plus a correct answer."""

    def run_sql(self, number, sql):
        import duckdb
        file = grade.CHECKS[number][0]
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / file).write_text(sql)
            con = duckdb.connect(str(ROOT / 'warehouse.duckdb'), read_only=True)
            try:
                return grade.grade(con, number, Path(d), json.loads((ROOT / 'data/expected/metrics.json').read_text()))
            finally:
                con.close()

    def test_correct_results_pass(self):
        self.assertTrue(self.run_sql('3', 'select * from mart_rework_by_stage')[0])
        self.assertTrue(self.run_sql('1', 'select date_day, decisions, p50_minutes, p90_minutes from mart_decision_wait_daily')[0])
        self.assertTrue(self.run_sql('2', 'select date_day, sessions, total_minutes, longest_minutes from mart_work_sessions_daily')[0])

    def test_review_case_duplicate_rows_fails(self):
        ok, why = self.run_sql('3', 'select * from mart_rework_by_stage union all select * from mart_rework_by_stage')
        self.assertFalse(ok)
        self.assertIn('more than once', why)
        ok, _ = self.run_sql('1', 'select * from mart_decision_wait_daily union all select * from mart_decision_wait_daily')
        self.assertFalse(ok)

    def test_review_case_nan_value_fails(self):
        ok, why = self.run_sql('3', "select stage, rework_count, cast('NaN' as double) as share_pct from mart_rework_by_stage")
        self.assertFalse(ok)
        self.assertIn('not a finite number', why)

    def test_null_and_infinite_values_fail(self):
        self.assertFalse(self.run_sql('3', 'select stage, rework_count, null::double as share_pct from mart_rework_by_stage')[0])
        self.assertFalse(self.run_sql('1', "select date_day, decisions, cast('inf' as double) as p50_minutes, p90_minutes from mart_decision_wait_daily")[0])

    def test_null_key_fails(self):
        ok, why = self.run_sql('3', 'select null as stage, rework_count, share_pct from mart_rework_by_stage')
        self.assertFalse(ok)
        self.assertIn('empty', why)


if __name__ == '__main__':
    unittest.main()
