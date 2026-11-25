"""Generator tests (standard library only): determinism, raw shape, dirt rates, and the answer key."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'generator'))
import generate as g  # noqa: E402

PARAMS = json.loads((ROOT / 'generator/params.json').read_text())


def run(params, out):
    world = g.World(params)
    world.build()
    stats = g.write_batches(world, out)
    return world, g.reference_metrics(world, stats)


def tree_hash(path):
    h = hashlib.sha256()
    for f in sorted(p for p in path.rglob('*') if p.is_file()):
        h.update(str(f.relative_to(path)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def rows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'a'
        cls.world, cls.metrics = run(PARAMS, cls.out)
        cls.events = [r for f in sorted((cls.out / 'raw/events').glob('*.csv')) for r in rows(f)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_same_params_same_bytes(self):
        other = Path(self.tmp.name) / 'b'
        run(PARAMS, other)
        self.assertEqual(tree_hash(self.out / 'raw'), tree_hash(other / 'raw'))

    def test_different_seed_changes_data(self):
        other = Path(self.tmp.name) / 'c'
        run({**PARAMS, 'seed': PARAMS['seed'] + 7}, other)
        self.assertNotEqual(tree_hash(self.out / 'raw'), tree_hash(other / 'raw'))

    def test_raw_event_columns_and_one_batch_per_load_day(self):
        files = sorted((self.out / 'raw/events').glob('batch_*.csv'))
        self.assertGreaterEqual(len(files), PARAMS['days'])
        for f in files[:3]:
            with f.open() as h:
                self.assertEqual(h.readline().strip().split(','), g.EVENT_COLUMNS)
        loaded = {r['loaded_at'] for r in rows(files[0])}
        self.assertEqual(len(loaded), 1)

    def test_dirt_is_present_at_the_configured_rates(self):
        n = self.metrics['counts']['events']
        ids = [r['event_id'] for r in self.events]
        dupes = len(ids) - len(set(ids))
        self.assertEqual(dupes, self.metrics['counts']['duplicate_rows'])
        self.assertTrue(0.005 * n < dupes < 0.02 * n, dupes)
        late = self.metrics['counts']['late_rows']
        self.assertTrue(0.01 * n < late < 0.04 * n, late)
        bad = [r for r in self.events if r['event_id'].startswith('evt_bad_')]
        self.assertEqual(len(bad), PARAMS['days'] * PARAMS['dirt']['malformed_rows_per_day'])
        self.assertTrue(all(r['event_time'] == '' or r['kind'] == '' or '+99:99' in r['event_time'] for r in bad))
        plus8 = sum(r['event_time'].endswith('+08:00') for r in self.events)
        self.assertTrue(0.25 * n < plus8 < 0.35 * n, plus8)

    def test_late_rows_land_in_a_later_batch_than_their_event_day(self):
        found = 0
        for f in sorted((self.out / 'raw/events').glob('batch_*.csv')):
            day = f.stem.removeprefix('batch_')
            for r in rows(f):
                if r['event_time'] and '+99' not in r['event_time']:
                    when = g.dt.datetime.fromisoformat(r['event_time']).astimezone(g.UTC).date().isoformat()
                    self.assertLessEqual(when, day)
                    found += when < day
        self.assertGreater(found, 0)

    def test_answer_key_uses_the_truth_not_the_dirt(self):
        truth = len(self.world.events)
        self.assertEqual(self.metrics['counts']['events'], truth)
        self.assertEqual(sum(d['events'] for d in self.metrics['event_volume_daily']), truth)
        self.assertFalse(any(e['event_id'].startswith('evt_bad_') for e in self.world.events))

    def test_every_decision_points_at_an_earlier_question_on_the_same_task(self):
        by_id = {e['event_id']: e for e in self.world.events}
        decisions = [e for e in self.world.events if e['kind'] == 'human.decision']
        self.assertGreater(len(decisions), 0)
        for d in decisions:
            ask = by_id[d['caused_by']]
            self.assertEqual((ask['kind'], ask['task_id']), ('agent.needs_decision', d['task_id']))
            self.assertLess(ask['event_time'], d['event_time'])
        self.assertEqual(sum(x['decisions'] for x in self.metrics['decision_wait_daily']), len(decisions))

    def test_task_states_end_in_done_and_rework_matches_blocked_reviews(self):
        last = {}
        for c in self.world.task_changes:
            last[c['task_id']] = c['state']
        self.assertTrue(all(s == 'done' for s in last.values()))
        blocked = sum(e['kind'] == 'review.blocked' for e in self.world.events)
        self.assertEqual(blocked, len(self.world.rework))
        self.assertEqual(sum(r['rework_count'] for r in self.metrics['rework_by_stage']), blocked)
        self.assertAlmostEqual(sum(r['share_pct'] for r in self.metrics['rework_by_stage']), 100, delta=0.05)

    def test_model_history_switches_on_the_change_day(self):
        changes = rows(self.out / 'raw/agent_model_changes.csv')
        self.assertEqual(len(changes), len(PARAMS['agents']) + len(PARAMS['model_changes']))
        start = self.world.start
        self.assertEqual(self.world.model_at('agent_04', start + g.dt.timedelta(days=19, hours=23))[1], 'model-a-large')
        self.assertEqual(self.world.model_at('agent_04', start + g.dt.timedelta(days=20))[1], 'model-a-medium')
        self.assertEqual(self.world.model_at('agent_04', start + g.dt.timedelta(days=45))[1], 'model-a-large')

    def test_quantile_matches_linear_interpolation(self):
        self.assertEqual(g.quantile([10, 20, 30, 40], 0.5), 25)
        self.assertAlmostEqual(g.quantile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9), 9.1)
        self.assertEqual(g.quantile([7], 0.9), 7)
        self.assertIsNone(g.quantile([], 0.5))

    def test_rolling_average_covers_at_most_seven_days(self):
        vol = self.metrics['event_volume_daily']
        self.assertEqual(vol[0]['rolling_7d_avg'], vol[0]['events'])
        window = [v['events'] for v in vol[3:10]]
        self.assertAlmostEqual(vol[9]['rolling_7d_avg'], round(sum(window) / 7, 3))

    def test_sessions_split_on_gaps_longer_than_the_threshold(self):
        per_day = PARAMS['work_blocks_per_day']
        days = self.metrics['work_sessions_daily']
        self.assertEqual(len(days), PARAMS['days'])
        self.assertTrue(all(d['sessions'] == per_day for d in days), [d for d in days if d['sessions'] != per_day][:2])

    def test_public_data_has_no_real_identifiers(self):
        text = ''.join(f.read_text() for f in (self.out / 'raw').rglob('*.csv'))
        # Assembled from pieces so the repo-wide privacy scan does not flag this test itself.
        for needle in ('/Us' + 'ers/', 'term_', 'run_', 'S-', '@', 'cla' + 'ude', 'co' + 'dex', 'gpt', 'opus', 'sonnet'):
            self.assertNotIn(needle, text.lower() if needle.islower() else text)


if __name__ == '__main__':
    unittest.main()
